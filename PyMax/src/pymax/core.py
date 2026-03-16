from __future__ import annotations

import asyncio
import contextlib
import socket
import ssl
import time
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, Literal, Callable
from uuid import UUID

import websockets
from loguru import logger
from typing_extensions import override

from PyMax.src.pymax.crud import Database
from PyMax.src.pymax.exceptions import WebSocketNotConnectedError, SocketNotConnectedError
from PyMax.src.pymax.filters import BaseFilter
from PyMax.src.pymax.interfaces import BaseClient
from PyMax.src.pymax.mixins.api import ApiMixin
from PyMax.src.pymax.mixins.auth import AuthMixin
from PyMax.src.pymax.mixins.handler import HandlerMixin
from PyMax.src.pymax.mixins.scheduler import SchedulerMixin
from PyMax.src.pymax.mixins.socket import SocketMixin
from PyMax.src.pymax.mixins.telemetry import TelemetryMixin
from PyMax.src.pymax.mixins.user import UserMixin
from PyMax.src.pymax.mixins.websocket import WebSocketMixin
from PyMax.src.pymax.payloads import UserAgentPayload
from PyMax.src.pymax.static.constant import HOST, PORT, WEBSOCKET_URI, SESSION_STORAGE_DB
from PyMax.src.pymax.types import Chat, Dialog, Channel, Me, User, Message, ReactionInfo


class MaxClient(AuthMixin, ApiMixin, HandlerMixin, SchedulerMixin, TelemetryMixin, UserMixin, WebSocketMixin,
                BaseClient):
    """
    Основной клиент для работы с WebSocket API сервиса Max.

    :param phone: Номер телефона для авторизации.
    :type phone: str
    :param uri: URI WebSocket сервера.
    :type uri: str, optional
    :param session_name: Название сессии для хранения базы данных.
    :type session_name: str, optional
    :param work_dir: Рабочая директория для хранения базы данных.
    :type work_dir: str, optional
    :param headers: Заголовки для подключения к WebSocket.
    :type headers: UserAgentPayload
    :param token: Токен авторизации. Если не передан, будет выполнен процесс логина по номеру телефона.
    :type token: str | None, optional
    :param host: Хост API сервера.
    :type host: str, optional
    :param port: Порт API сервера.
    :type port: int, optional
    :param registration: Флаг регистрации нового пользователя.
    :type registration: bool, optional
    :param first_name: Имя пользователя для регистрации. Требуется, если registration=True.
    :type first_name: str, optional
    :param last_name: Фамилия пользователя для регистрации.
    :type last_name: str | None, optional
    :param send_fake_telemetry: Флаг отправки фейковой телеметрии.
    :type send_fake_telemetry: bool, optional
    :param proxy: Прокси для подключения к WebSocket (см. https://websockets.readthedocs.io/en/stable/topics/proxies.html).
    :type proxy: str | Literal[True] | None, optional
    :param reconnect: Флаг автоматического переподключения при потере соединения.
    :type reconnect: bool, optional

    :raises InvalidPhoneError: Если формат номера телефона неверный.
    """
    allowed_device_types: set[str] = {"WEB"}

    def __init__(self, phone: str, uri: str = WEBSOCKET_URI, session_name: str = SESSION_STORAGE_DB,
                 headers: UserAgentPayload | None = None, token: str | None = None, send_fake_telemetry: bool = True,
                 host: str = HOST, port: int = PORT, proxy: str | Literal[True] | None = None,
                 work_dir: str = ".", registration: bool = False, first_name: str = "",
                 last_name: str | None = None, device_id: UUID | None = None, reconnect: bool = True,
                 reconnect_delay: float = 1.0, ) -> None:
        """
        Инициализирует клиент MaxClient.

        :param phone: Номер телефона для авторизации.
        :type phone: str
        :param uri: URI WebSocket сервера.
        :type uri: str
        :param session_name: Название сессии для хранения базы данных.
        :type session_name: str
        :param headers: Заголовки для подключения к WebSocket.
        :type headers: UserAgentPayload | None
        :param token: Токен авторизации.
        :type token: str | None
        :param send_fake_telemetry: Флаг отправки фейковой телеметрии.
        :type send_fake_telemetry: bool
        :param host: Хост API сервера.
        :type host: str
        :param port: Порт API сервера.
        :type port: int
        :param proxy: Прокси для подключения к WebSocket.
        :type proxy: str | Literal[True] | None
        :param work_dir: Рабочая директория для хранения базы данных.
        :type work_dir: str
        :param registration: Флаг регистрации нового пользователя.
        :type registration: bool
        :param first_name: Имя пользователя для регистрации.
        :type first_name: str
        :param last_name: Фамилия пользователя для регистрации.
        :type last_name: str | None
        :param device_id: ID устройства.
        :type device_id: UUID | None
        :param reconnect: Флаг автоматического переподключения.
        :type reconnect: bool
        :param reconnect_delay: Задержка между переподключениями в секундах.
        :type reconnect_delay: float
        """
        self.uri: str = uri
        self.phone: str = phone  # Номер телефона аккаунта Max

        self.host: str = host
        self.port: int = port
        self.registration: bool = registration
        self.first_name: str = first_name
        self.last_name: str | None = last_name
        self.proxy: str | Literal[True] | None = proxy
        self.reconnect: bool = reconnect
        self.reconnect_delay: float = reconnect_delay

        self.is_connected: bool = False

        self.chats: list[Chat] = []
        self.dialogs: list[Dialog] = []
        self.channels: list[Channel] = []
        self.me: Me | None = None
        self.contacts: list[User] = []
        self._users: dict[int, User] = {}

        self._work_dir: str = work_dir  # Рабочая директория для хранения базы данных с аккаунтами Max
        self._database_path: Path = Path(work_dir) / session_name
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database_path.touch(exist_ok=True)
        self._database = Database(self._work_dir)

        self._incoming: asyncio.Queue[dict[str, Any]] | None = None
        self._outgoing: asyncio.Queue[dict[str, Any]] | None = None
        self._recv_task: asyncio.Task[Any] | None = None
        self._outgoing_task: asyncio.Task[Any] | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._file_upload_waiters: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._stop_event = asyncio.Event()

        self._seq: int = 0
        self._error_count: int = 0
        self._circuit_breaker: bool = False
        self._last_error_time: float = 0.0

        self._device_id = device_id if device_id is not None else self._database.get_device_id()
        self._file_upload_waiters: dict[int, asyncio.Future[dict[str, Any]]] = {}

        self._token = self._database.get_auth_token() or token
        if headers is None:
            headers = self._default_headers()
        self.user_agent = headers
        self._validate_device_type()
        self._send_fake_telemetry: bool = send_fake_telemetry
        self._session_id: int = int(time.time() * 1000)
        self._action_id: int = 1
        self._current_screen: str = "chats_list_tab"

        self._on_message_handlers: list[
            tuple[Callable[[Message], Any], BaseFilter[Message] | None]
        ] = []
        self._on_message_edit_handlers: list[
            tuple[Callable[[Message], Any], BaseFilter[Message] | None]
        ] = []
        self._on_message_delete_handlers: list[
            tuple[Callable[[Message], Any], BaseFilter[Message] | None]
        ] = []
        self._on_start_handler: Callable[[], Any | Awaitable[Any]] | None = None
        self._on_stop_handler: Callable[[], Any | Awaitable[Any]] | None = None
        self._on_reaction_change_handlers: list[Callable[[str, int, ReactionInfo], Any]] = []
        self._on_chat_update_handlers: list[Callable[[Chat], Any | Awaitable[Any]]] = []
        self._on_raw_receive_handlers: list[Callable[[dict[str, Any]], Any | Awaitable[Any]]] = []
        self._scheduled_tasks: list[tuple[Callable[[], Any | Awaitable[Any]], float]] = []

        self._ssl_context = ssl.create_default_context()
        self._ssl_context.set_ciphers("DEFAULT")
        self._ssl_context.check_hostname = True
        self._ssl_context.verify_mode = ssl.CERT_REQUIRED
        self._ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        self._ssl_context.load_default_certs()
        self._socket: socket.socket | None = None
        self._ws: websockets.ClientConnection | None = None

        self._setup_logger()
        logger.debug(
            "Initialized MaxClient uri=%s work_dir=%s",
            self.uri,
            self._work_dir,
        )

    @staticmethod
    def _default_headers() -> UserAgentPayload:
        """
        Возвращает заголовки по умолчанию для подключения.

        :return: Заголовки пользователя для устройства WEB.
        :rtype: UserAgentPayload
        """
        return UserAgentPayload(device_type="WEB")

    def _validate_device_type(self) -> None:
        """
        Проверяет, поддерживается ли тип устройства.

        :raises ValueError: Если тип устройства не поддерживается.
        """
        if self.user_agent.device_type not in self.allowed_device_types:
            raise ValueError(
                f"{self.__class__.__name__} does not support "
                f"device_type={self.user_agent.device_type}"
            )

    async def _wait_forever(self) -> None:
        """
        Ожидает закрытия WebSocket соединения.

        :return: None
        """
        try:
            await self.ws.wait_closed()
        except asyncio.CancelledError:
            logger.debug("wait_closed отменили")
        except WebSocketNotConnectedError:
            logger.info("WebSocket не подключён, выход из wait_forever")

    async def close(self) -> None:
        """
        Закрывает клиент и освобождает ресурсы.

        :return: None
        """
        try:
            logger.info("Closing client")
            self._stop_event.set()
        except Exception as e:
            logger.exception(e)

    async def _post_login_tasks(self, sync: bool = True) -> None:
        """
        Выполняет пост-логин задачи: синхронизация, ping, телеметрия.

        :param sync: Флаг выполнения синхронизации.
        :type sync: bool
        :return: None
        """
        if sync:
            await self._sync()

        logger.debug("is_connected=%s before starting ping", self.is_connected)
        ping_task = asyncio.create_task(self._send_interactive_ping())
        ping_task.add_done_callback(self._log_task_exception)
        self._background_tasks.add(ping_task)

        start_scheduled_task = asyncio.create_task(self._start_scheduled_tasks())
        start_scheduled_task.add_done_callback(self._log_task_exception)

        if self._send_fake_telemetry:
            telemetry_task = asyncio.create_task(self._start())
            telemetry_task.add_done_callback(self._log_task_exception)
            self._background_tasks.add(telemetry_task)

        if self._on_start_handler:
            logger.debug("Calling on_start handler")
            result = self._on_start_handler()
            if asyncio.iscoroutine(result):
                await self._safe_execute(result, context="on_start handler")

    async def login_with_code(self, temp_token: str, code: str, start: bool = False) -> None:
        """
        Завершает кастомный login flow: отправляет код, сохраняет токен и запускает пост-логин задачи.

        :param temp_token: Временный токен, полученный из request_code.
        :type temp_token: str
        :param code: Код верификации (6 цифр).
        :type code: str
        :param start: Флаг запуска пост-логин задач и ожидания навсегда. Если False, только сохраняет токен.
        :type start: bool, optional
        :return: None
        :rtype: None
        """
        resp = await self._send_code(code, temp_token)

        login_attrs = resp.get("tokenAttrs", {}).get("LOGIN", {})
        password_challenge = resp.get("passwordChallenge")

        if password_challenge and not login_attrs:
            token = await self._two_factor_auth(password_challenge)
        else:
            token = login_attrs.get("token")

        if not token:
            raise ValueError("Login response did not contain tokenAttrs.LOGIN.token")
        self._token = token
        self._database.update_auth_token(self._device_id, token)
        if start:
            while True:
                try:
                    await self._post_login_tasks()
                    await self._wait_forever()
                except Exception as e:
                    logger.exception(e)
                finally:
                    await self._cleanup_client()

                logger.info("Reconnecting after post-login tasks failure")
                await asyncio.sleep(self.reconnect_delay)
        else:
            logger.info("Login successful, token saved to database, exiting...")

    async def start(self) -> None:
        """
        Запускает клиент, подключается к WebSocket, авторизует
        пользователя (если нужно) и запускает фоновый цикл.
        Теперь включает безопасный reconnect-loop, если self.reconnect=True.

        :return: None
        :rtype: None
        """
        logger.info("Запуск клиента")
        while not self._stop_event.is_set():
            try:
                await self.connect(self.user_agent)

                if self.registration:
                    if not self.first_name:
                        raise ValueError("Для регистрации требуется имя")
                    await self._register(self.first_name, self.last_name)

                if self._token and self._database.get_auth_token() is None:
                    self._database.update_auth_token(self._device_id, self._token)

                if self._token is None:
                    await self._login()

                await self._sync(self.user_agent)
                await self._post_login_tasks(sync=False)

                wait_task = asyncio.create_task(self._wait_forever())
                stop_task = asyncio.create_task(self._stop_event.wait())

                done, pending = await asyncio.wait(
                    [wait_task, stop_task], return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

            except asyncio.CancelledError:
                logger.info("Задача клиента отменена, останавливается")
                break
            except Exception as e:
                logger.exception(e)
            finally:
                await self._cleanup_client()

            if not self.reconnect or self._stop_event.is_set():
                logger.info("Восстановление подключения отключено или запрошено остановка — выход из start()")
                break

            logger.info("Включено повторное подключение — перезагрузка клиента")
            await asyncio.sleep(self.reconnect_delay)

        logger.info("Клиент ушёл чисто")


class SocketMaxClient(SocketMixin, MaxClient):
    """
    Клиент для работы с Max API через сокеты (Android, iOS, Desktop).

    Наследуется от MaxClient, переопределяет методы для работы с TCP сокетами.
    Поддерживаемые типы устройств: ANDROID, IOS, DESKTOP.
    """
    allowed_device_types = {"ANDROID", "IOS", "DESKTOP"}

    @staticmethod
    def _default_headers() -> UserAgentPayload:
        """
        Возвращает заголовки по умолчанию для DESKTOP устройства.

        :return: Заголовки пользователя для устройства DESKTOP.
        :rtype: UserAgentPayload
        """
        return UserAgentPayload(device_type="DESKTOP")

    @override
    async def _wait_forever(self):
        """
        Ожидает закрытия socket соединения.

        :return: None
        """
        if self._recv_task:
            try:
                await self._recv_task
            except asyncio.CancelledError:
                logger.debug("Разъём recv_task отключён")
            except Exception as e:
                logger.exception("Разъём recv_task вышел из строя: %s", e)

    @override
    async def _cleanup_client(self):
        """
        Очищает ресурсы клиента: отменяет задачи, закрывает сокет.

        :return: None
        """
        for task in list(self._background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception(e)
            self._background_tasks.discard(task)

        if self._recv_task:
            self._recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._recv_task
            self._recv_task = None

        if self._outgoing_task:
            self._outgoing_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._outgoing_task
            self._outgoing_task = None

        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(SocketNotConnectedError())
        self._pending.clear()

        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                logger.exception(e)
            self._socket = None

        self.is_connected = False
        logger.info("Запуск клиента() очищен (розетка)")
