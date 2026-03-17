# -*- coding: utf-8 -*-
"""
Базовые интерфейсы (абстрактные классы) для клиента Max API.

Содержит базовые классы для реализации клиентов и транспорта:
- BaseClient: базовый класс клиента с общей функциональностью
- BaseTransport: базовый класс транспорта для отправки/получения данных

Автор: MaxMaster Team
Версия: 0.0.1
"""
import asyncio
import contextlib
import json
import time
import traceback
from abc import abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from typing_extensions import Self

from PyMax.src.pymax.exceptions import WebSocketNotConnectedError, SocketNotConnectedError
from PyMax.src.pymax.filters import BaseFilter
from PyMax.src.pymax.payloads import UserAgentPayload, BaseWebSocketMessage, SyncPayload
from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.constant import DEFAULT_TIMEOUT, DEFAULT_PING_INTERVAL
from PyMax.src.pymax.static.enum import Opcode, MessageStatus, ChatType
from PyMax.src.pymax.types import Message, ReactionCounter, ReactionInfo, Chat, Dialog, Channel, User, Me
from PyMax.src.pymax.utils import MixinsUtils


class BaseClient(ClientProtocol):
    """
    Базовый класс клиента Max API.

    Предоставляет общую функциональность для всех клиентов:
    - Безопасное выполнение корутин с обработкой исключений
    - Создание фоновых задач с отслеживанием
    - Очистка ресурсов при закрытии
    - Контекстный менеджер для автоматического управления
    - Методы для отладки и инспекции состояния

    Наследуется от ClientProtocol и реализует общую логику,
    специфичные методы реализуются в наследующих классах.

    Атрибуты:
        _background_tasks: Множество фоновых задач asyncio.
        _recv_task: Задача получения сообщений.
        _outgoing_task: Задача отправки сообщений.
        _pending: Словарь ожидающих ответов.
        is_connected: Флаг состояния подключения.
        me: Информация о текущем пользователе.
        dialogs: Список диалогов.
        chats: Список чатов.
        channels: Список каналов.
        _users: Кэш пользователей.
        _scheduled_tasks: Список запланированных задач.
    """

    async def _safe_execute(self, coro: Awaitable[Any], context: str = "unknown") -> Any:
        """
        Безопасно выполняет корутину с обработкой всех исключений.

        Обёртывает корутину в try-except, логирует исключения и продолжает выполнение.
        Используется для выполнения обработчиков событий и других задач, где исключения
        не должны прерывать основной поток выполнения.

        :param coro: Корутина для выполнения.
        :type coro: Awaitable[Any]
        :param context: Контекст выполнения для логирования (например, "handler").
        :type context: str
        :return: Результат выполнения корутины или None при ошибке.
        :rtype: Any

        Пример:
            await self._safe_execute(my_coro(), context="my_handler")
        """
        try:
            return await coro
        except Exception as e:
            logger.error(f"Unhandled exception in {context}: {e}\n{traceback.format_exc()}")

    def _create_safe_task(
        self,
        coro: Awaitable[Any],
        name: str | None = None,
    ) -> asyncio.Task[Any | None]:
        """
        Создаёт фоновую задачу с обработкой исключений.

        Метод оборачивает переданную корутину в обёртку, которая перехватывает все исключения
        (кроме отмены), логирует их и повторно поднимает. Задача добавляется в множество
        фоновых задач клиента для отслеживания и корректной очистки при завершении.

        :param coro: Корутина, которую необходимо выполнить в фоне.
        :type coro: Awaitable[Any]
        :param name: Опциональное имя задачи для идентификации в логах.
        :type name: str | None
        :return: Объект задачи asyncio.Task.
        :rtype: asyncio.Task[Any | None]

        Пример:
            task = self._create_safe_task(self.my_async_func(), name="my_task")
            # Задача будет автоматически отслеживаться и очищаться

        Примечание:
            Задача добавляется в _background_tasks для отслеживания.
            При отмене задачи (CancelledError) исключение не логируется.
        """
        async def runner():
            try:
                return await coro
            except asyncio.CancelledError:
                raise
            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"Unhandled exception in task {name or coro}: {e}\n{tb}")
                raise

        task = asyncio.create_task(runner(), name=name)
        self._background_tasks.add(task)
        return task

    async def _cleanup_client(self) -> None:
        """
        Очищает ресурсы клиента: отменяет задачи, закрывает соединение.

        Выполняет следующие действия:
        1. Отменяет все фоновые задачи из _background_tasks
        2. Отменяет задачи получения и отправки сообщений
        3. Устанавливает ошибку во все ожидающие Future в _pending
        4. Закрывает WebSocket соединение
        5. Сбрасывает флаг is_connected

        :return: None

        Пример:
            try:
                await client.start()
            finally:
                await client._cleanup_client()

        Примечание:
            Метод вызывается автоматически при остановке клиента.
            Все исключения при очистке логируются, но не пробрасываются.
        """
        # Отмена всех фоновых задач
        for task in list(self._background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug("Background task raised during cancellation", exc_info=True)
            self._background_tasks.discard(task)

        # Отмена задачи получения сообщений
        if self._recv_task:
            self._recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._recv_task
            self._recv_task = None

        # Отмена задачи отправки сообщений
        if self._outgoing_task:
            self._outgoing_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._outgoing_task
            self._outgoing_task = None

        # Установка ошибки в ожидающие Future
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(WebSocketNotConnectedError())
        self._pending.clear()

        # Закрытие WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                logger.debug("Error closing ws during cleanup", exc_info=True)
            self._ws = None

        # Сброс состояния подключения
        self.is_connected = False
        logger.info("Client start() cleaned up")

    async def idle(self) -> None:
        """
        Поддерживает клиента в «ожидающем» состоянии до закрытия или прерывания.

        Блокирует выполнение бесконечно долго, пока не будет отменена задача
        или не произойдёт другое прерывающее событие.

        :return: Никогда не возвращает значение; функция блокирует выполнение.
        :rtype: None

        Пример:
            await client.connect()
            await client.idle()  # Блокировка до отмены
        """
        await asyncio.Event().wait()

    def inspect(self) -> None:
        """
        Выводит в лог текущий статус клиента для отладки.

        Логирует следующую информацию:
        - Статус подключения
        - Информация о текущем пользователе (me)
        - Количество диалогов, чатов, каналов
        - Количество закэшированных пользователей
        - Количество фоновых и запланированных задач

        Пример:
            client.inspect()
            # Вывод в лог:
            # Pymax
            # ---------
            # Connected: True
            # Me: John (12345)
            # Dialogs: 10
            # ...

        Примечание:
            Используйте для отладки и мониторинга состояния клиента.
        """
        logger.info("Pymax")
        logger.info("---------")
        logger.info(f"Connected: {self.is_connected}")
        if self.me is not None:
            logger.info(f"Me: {self.me.names[0].first_name} ({self.me.id})")
        else:
            logger.info("Me: N/A")
        logger.info(f"Dialogs: {len(self.dialogs)}")
        logger.info(f"Chats: {len(self.chats)}")
        logger.info(f"Channels: {len(self.channels)}")
        logger.info(f"Users cached: {len(self._users)}")
        logger.info(f"Background tasks: {len(self._background_tasks)}")
        logger.info(f"Scheduled tasks: {len(self._scheduled_tasks)}")
        logger.info("---------")

    async def __aenter__(self) -> Self:
        """
        Контекстный менеджер: вход.

        Создаёт задачу для запуска клиента и ожидает подключения.

        :return: Экземпляр клиента.
        :rtype: Self

        Пример:
            async with MaxClient(phone="79991234567") as client:
                # Клиент автоматически подключён
                pass
        """
        self._create_safe_task(self.start(), name="start")
        while not self.is_connected:
            await asyncio.sleep(0.05)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """
        Контекстный менеджер: выход.

        Закрывает клиента при выходе из контекста.

        :param exc_type: Тип исключения (если было).
        :param exc: Исключение (если было).
        :param tb: Traceback исключения.
        :return: None
        """
        await self.close()

    @abstractmethod
    async def login_with_code(
        self,
        temp_token: str,
        code: str,
        start: bool = False,
    ) -> None:
        """
        Завершает вход, отправляя код верификации.

        :param temp_token: Временный токен из request_code.
        :type temp_token: str
        :param code: Код верификации (6 цифр).
        :type code: str
        :param start: Флаг запуска пост-логин задач.
        :type start: bool
        """
        pass

    @abstractmethod
    async def _post_login_tasks(self, sync: bool = True) -> None:
        """
        Выполняет задачи после входа: синхронизация, ping, телеметрия.

        :param sync: Флаг выполнения синхронизации.
        :type sync: bool
        """
        pass

    @abstractmethod
    async def _wait_forever(self) -> None:
        """
        Ожидает закрытия соединения.

        :return: None
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        Запускает клиент.

        :return: None
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Закрывает клиента.

        :return: None
        """
        pass


class BaseTransport(ClientProtocol):
    """
    Базовый класс транспорта для обмена данными с сервером.

    Предоставляет базовую функциональность для отправки и получения данных:
    - Создание сообщений протокола
    - Отправка с ожиданием ответа
    - Обработка входящих сообщений
    - Управление очередями
    - Синхронизация данных

    Наследуется от ClientProtocol и реализует общую логику транспорта.
    Специфичные методы (connect, _send_and_wait, _recv_loop) реализуются
    в наследующих классах (WebSocketMixin, SocketMixin).

    Атрибуты:
        _seq: Счётчик sequence numbers.
        _pending: Словарь ожидающих ответов {seq: Future}.
        _incoming: Очередь входящих сообщений.
        _outgoing: Очередь исходящих сообщений.
        _file_upload_waiters: Словарь ожидающих загрузки файлов.
        _on_message_handlers: Обработчики сообщений.
        _on_raw_receive_handlers: Обработчики сырых данных.
    """

    @abstractmethod
    async def connect(
        self,
        user_agent: UserAgentPayload | None = None,
    ) -> dict[str, Any] | None:
        """
        Подключается к серверу.

        :param user_agent: Заголовки пользователя.
        :return: Результат handshake.
        """
        ...

    @abstractmethod
    async def _send_and_wait(
        self,
        opcode: Opcode,
        payload: dict[str, Any],
        cmd: int = 0,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """
        Отправляет сообщение и ожидает ответ.

        :param opcode: Код операции.
        :param payload: Данные сообщения.
        :param cmd: Код команды.
        :param timeout: Таймаут ожидания.
        :return: Ответ от сервера.
        """
        ...

    @abstractmethod
    async def _recv_loop(self) -> None:
        """
        Цикл получения сообщений.

        :return: None
        """
        ...

    def _make_message(
        self,
        opcode: Opcode,
        payload: dict[str, Any],
        cmd: int = 0,
    ) -> dict[str, Any]:
        """
        Создаёт сообщение протокола для отправки.

        Увеличивает счётчик _seq и создаёт сообщение с уникальным sequence number.

        :param opcode: Код операции (Opcode enum).
        :type opcode: Opcode
        :param payload: Данные сообщения (словарь).
        :type payload: dict[str, Any]
        :param cmd: Код команды (по умолчанию 0).
        :type cmd: int
        :return: Словарь сообщения в формате протокола.
        :rtype: dict[str, Any]

        Пример:
            msg = self._make_message(Opcode.REQUEST, {"action": "get_users"})
            # {"ver": 11, "cmd": 0, "seq": 1, "opcode": 1, "payload": {...}}

        Примечание:
            Версия протокола по умолчанию: 11.
        """
        self._seq += 1

        msg = BaseWebSocketMessage(
            ver=11,
            cmd=cmd,
            seq=self._seq,
            opcode=opcode.value,
            payload=payload,
        ).model_dump(by_alias=True)

        logger.debug("make_message opcode=%s cmd=%s seq=%s", opcode, cmd, self._seq)
        return msg

    async def _send_interactive_ping(self) -> None:
        """
        Отправляет интерактивный ping для поддержания соединения.

        Бесконечный цикл отправки ping сообщений с интервалом DEFAULT_PING_INTERVAL.
        Завершается при разрыве соединения.

        :return: None

        Пример:
            # Запускается автоматически в фоновой задаче
            await self._send_interactive_ping()

        Примечание:
            Использует _send_and_wait с opcode=Opcode.PING.
        """
        while self.is_connected:
            try:
                await self._send_and_wait(
                    opcode=Opcode.PING,
                    payload={"interactive": True},
                    cmd=0,
                )
                logger.debug("Interactive ping sent successfully")
            except SocketNotConnectedError:
                logger.debug("Socket disconnected, exiting ping loop")
                break
            except Exception:
                logger.warning("Interactive ping failed")
            await asyncio.sleep(DEFAULT_PING_INTERVAL)

    async def _handshake(self, user_agent: UserAgentPayload) -> dict[str, Any]:
        """
        Выполняет handshake с сервером для авторизации.

        Отправляет SESSION_INIT сообщение с deviceId и userAgent.
        При ошибке вызывает MixinsUtils.handle_error().

        :param user_agent: Заголовки пользователя для идентификации.
        :type user_agent: UserAgentPayload
        :return: Ответ сервера на handshake.
        :rtype: dict[str, Any]

        Пример:
            resp = await self._handshake(user_agent)
            # resp содержит данные сессии

        Примечание:
            Вызывается автоматически после подключения.
        """
        logger.debug(
            "Sending handshake with user_agent keys=%s",
            user_agent.model_dump(by_alias=True).keys(),
        )

        user_agent_json = user_agent.model_dump(by_alias=True)
        resp = await self._send_and_wait(
            opcode=Opcode.SESSION_INIT,
            payload={"deviceId": str(self._device_id), "userAgent": user_agent_json},
        )

        if resp.get("payload", {}).get("error"):
            MixinsUtils.handle_error(resp)

        logger.info("Handshake completed")
        return resp

    async def _process_message_handler(
        self,
        handler: Callable[[Message], Any],
        filter: BaseFilter[Message] | None,
        message: Message,
    ) -> None:
        """
        Обрабатывает сообщение через обработчик с применением фильтра.

        Если фильтр установлен и возвращает True, вызывает обработчик.
        Если результат — корутина, создаёт безопасную задачу.

        :param handler: Функция-обработчик сообщения.
        :type handler: Callable[[Message], Any]
        :param filter: Фильтр для проверки сообщения (опционально).
        :type filter: BaseFilter[Message] | None
        :param message: Объект сообщения для обработки.
        :type message: Message
        :return: None
        """
        result = None
        if filter:
            if filter(message):
                result = handler(message)
            else:
                return
        else:
            result = handler(message)
        if asyncio.iscoroutine(result):
            self._create_safe_task(result, name=f"handler-{handler.__name__}")

    def _parse_json(self, raw: Any) -> dict[str, Any] | None:
        """
        Парсит JSON из сырых данных.

        :param raw: Сырые данные для парсинга.
        :type raw: Any
        :return: Словарь с данными или None при ошибке.
        :rtype: dict[str, Any] | None
        """
        try:
            return json.loads(raw)
        except Exception:
            logger.warning("JSON parse error", exc_info=True)
            return None

    def _handle_pending(self, seq: int | None, data: dict) -> bool:
        """
        Обрабатывает ожидающий запрос по sequence number.

        Если seq найден в _pending, устанавливает результат Future.

        :param seq: Sequence number из ответа.
        :type seq: int | None
        :param data: Данные ответа.
        :type data: dict
        :return: True если запрос найден и обработан, иначе False.
        :rtype: bool
        """
        if isinstance(seq, int):
            fut = self._pending.get(seq)
            if fut and not fut.done():
                fut.set_result(data)
                logger.debug("Matched response for pending seq=%s", seq)
                return True
        return False

    async def _handle_incoming_queue(self, data: dict[str, Any]) -> None:
        """
        Добавляет данные в очередь входящих сообщений.

        :param data: Данные для добавления в очередь.
        :type data: dict[str, Any]
        :return: None
        """
        if self._incoming:
            try:
                self._incoming.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(
                    "Incoming queue full; dropping message seq=%s", data.get("seq")
                )

    async def _handle_file_upload(self, data: dict[str, Any]) -> None:
        """
        Обрабатывает уведомление о загрузке файла.

        Если данные содержат fileId или videoId, устанавливает результат
        в соответствующий Future из _file_upload_waiters.

        :param data: Данные уведомления о загрузке.
        :type data: dict[str, Any]
        :return: None
        """
        if data.get("opcode") != Opcode.NOTIF_ATTACH:
            return
        payload = data.get("payload", {})
        for key in ("fileId", "videoId"):
            id_ = payload.get(key)
            if id_ is not None:
                fut = self._file_upload_waiters.pop(id_, None)
                if fut and not fut.done():
                    fut.set_result(data)
                    logger.debug("Fulfilled file upload waiter for %s=%s", key, id_)

    async def _send_notification_response(
        self,
        chat_id: int,
        message_id: str,
    ) -> None:
        """
        Отправляет подтверждение получения уведомления о сообщении.

        :param chat_id: ID чата.
        :type chat_id: int
        :param message_id: ID сообщения.
        :type message_id: str
        :return: None
        """
        if self._socket is not None and self.is_connected:
            return
        await self._send_and_wait(
            opcode=Opcode.NOTIF_MESSAGE,
            payload={"chatId": chat_id, "messageId": message_id},
            cmd=0,
        )
        logger.debug(
            "Sent NOTIF_MESSAGE_RECEIVED for chat_id=%s message_id=%s", chat_id, message_id
        )

    async def _handle_message_notifications(self, data: dict) -> None:
        """
        Обрабатывает уведомления о сообщениях (новые, редактированные, удалённые).

        :param data: Данные уведомления.
        :type data: dict
        :return: None
        """
        if data.get("opcode") != Opcode.NOTIF_MESSAGE.value:
            return
        payload = data.get("payload", {})
        msg = Message.from_dict(payload)
        if not msg:
            return

        if msg.chat_id and msg.id:
            await self._send_notification_response(msg.chat_id, str(msg.id))

        handlers_map = {
            MessageStatus.EDITED: self._on_message_edit_handlers,
            MessageStatus.REMOVED: self._on_message_delete_handlers,
        }
        if msg.status and msg.status in handlers_map:
            for handler, filter in handlers_map[msg.status]:
                await self._process_message_handler(handler, filter, msg)
        if msg.status is None:
            for handler, filter in self._on_message_handlers:
                await self._process_message_handler(handler, filter, msg)

    async def _handle_reactions(self, data: dict) -> None:
        """
        Обрабатывает уведомления об изменении реакций.

        :param data: Данные уведомления о реакциях.
        :type data: dict
        :return: None
        """
        if data.get("opcode") != Opcode.NOTIF_MSG_REACTIONS_CHANGED:
            return

        payload = data.get("payload", {})
        chat_id = payload.get("chatId")
        message_id = payload.get("messageId")

        if not (chat_id and message_id):
            return

        total_count = payload.get("totalCount")
        your_reaction = payload.get("yourReaction")
        counters = [ReactionCounter.from_dict(c) for c in payload.get("counters", [])]

        reaction_info = ReactionInfo(
            total_count=total_count,
            your_reaction=your_reaction,
            counters=counters,
        )

        for handler in self._on_reaction_change_handlers:
            try:
                result = handler(message_id, chat_id, reaction_info)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Error in on_reaction_change_handler: %s", e)

    async def _handle_chat_updates(self, data: dict) -> None:
        """
        Обрабатывает уведомления об обновлении чатов.

        :param data: Данные уведомления о чате.
        :type data: dict
        :return: None
        """
        if data.get("opcode") != Opcode.NOTIF_CHAT:
            return

        payload = data.get("payload", {})
        chat_data = payload.get("chat", {})
        chat = Chat.from_dict(chat_data)
        if not chat:
            return

        for handler in self._on_chat_update_handlers:
            try:
                result = handler(chat)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Error in on_chat_update_handler: %s", e)

    async def _handle_raw_receive(self, data: dict[str, Any]) -> None:
        """
        Обрабатывает сырые входящие данные через обработчики.

        :param data: Сырые данные.
        :type data: dict[str, Any]
        :return: None
        """
        for handler in self._on_raw_receive_handlers:
            try:
                result = handler(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Error in on_raw_receive_handler: %s", e)

    async def _dispatch_incoming(self, data: dict[str, Any]) -> None:
        """
        Диспетчеризирует входящие данные по обработчикам.

        Вызывает следующие обработчики:
        1. _handle_raw_receive — обработка сырых данных
        2. _handle_file_upload — обработка загрузки файлов
        3. _handle_message_notifications — обработка уведомлений о сообщениях
        4. _handle_reactions — обработка реакций
        5. _handle_chat_updates — обработка обновлений чатов

        :param data: Входящие данные.
        :type data: dict[str, Any]
        :return: None
        """
        await self._handle_raw_receive(data)
        await self._handle_file_upload(data)
        await self._handle_message_notifications(data)
        await self._handle_reactions(data)
        await self._handle_chat_updates(data)

    def _log_task_exception(self, fut: asyncio.Future[Any]) -> None:
        """
        Логирует исключение из завершённой задачи.

        :param fut: Future задачи для проверки.
        :type fut: asyncio.Future[Any]
        :return: None
        """
        try:
            fut.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Error retrieving task exception: %s", e)

    async def _queue_message(
        self,
        opcode: int,
        payload: dict[str, Any],
        cmd: int = 0,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        """
        Добавляет сообщение в очередь исходящих сообщений.

        :param opcode: Код операции.
        :type opcode: int
        :param payload: Данные сообщения.
        :type payload: dict[str, Any]
        :param cmd: Код команды.
        :type cmd: int
        :param timeout: Таймаут ожидания.
        :type timeout: float
        :param max_retries: Максимальное количество попыток.
        :type max_retries: int
        :return: None
        """
        if self._outgoing is None:
            logger.warning("Outgoing queue not initialized")
            return

        message = {
            "opcode": opcode,
            "payload": payload,
            "cmd": cmd,
            "timeout": timeout,
            "retry_count": 0,
            "max_retries": max_retries,
        }

        await self._outgoing.put(message)
        logger.debug("Message queued for sending")

    async def _outgoing_loop(self) -> None:
        """
        Цикл отправки сообщений из очереди.

        Бесконечный цикл, который:
        1. Получает сообщения из очереди
        2. Отправляет через _send_and_wait
        3. При ошибке повторяет попытку с задержкой
        4. Использует circuit breaker при множественных ошибках

        :return: None
        """
        while self.is_connected:
            try:
                if self._outgoing is None:
                    await asyncio.sleep(0.1)
                    continue

                if self._circuit_breaker:
                    if time.time() - self._last_error_time > 60:
                        self._circuit_breaker = False
                        self._error_count = 0
                        logger.info("Circuit breaker reset")
                    else:
                        await asyncio.sleep(5)
                        continue

                message = await self._outgoing.get()
                if not message:
                    continue

                retry_count = message.get("retry_count", 0)
                max_retries = message.get("max_retries", 3)

                try:
                    await self._send_and_wait(
                        opcode=message["opcode"],
                        payload=message["payload"],
                        cmd=message.get("cmd", 0),
                        timeout=message.get("timeout", DEFAULT_TIMEOUT),
                    )
                    logger.debug("Message sent successfully from queue")
                    self._error_count = max(0, self._error_count - 1)
                except Exception as e:
                    self._error_count += 1
                    self._last_error_time = time.time()

                    if self._error_count > 10:
                        self._circuit_breaker = True
                        logger.warning(
                            "Circuit breaker activated due to %d consecutive errors",
                            self._error_count,
                        )
                        await self._outgoing.put(message)
                        continue

                    retry_delay = self._get_retry_delay(e, retry_count)
                    logger.warning(
                        "Failed to send message from queue: %s (delay: %ds)",
                        e,
                        retry_delay,
                    )

                    if retry_count < max_retries:
                        message["retry_count"] = retry_count + 1
                        await asyncio.sleep(retry_delay)
                        await self._outgoing.put(message)
                    else:
                        logger.error(
                            "Message failed after %d retries, dropping",
                            max_retries,
                        )

            except Exception:
                logger.exception("Error in outgoing loop")
                await asyncio.sleep(1)

    def _get_retry_delay(self, error: Exception, retry_count: int) -> float:
        """
        Вычисляет задержку перед повторной попыткой отправки.

        :param error: Исключение, вызвавшее ошибку.
        :type error: Exception
        :param retry_count: Количество попыток.
        :type retry_count: int
        :return: Задержка в секундах.
        :rtype: float
        """
        if isinstance(error, (ConnectionError, OSError)):
            return 1.0
        elif isinstance(error, TimeoutError):
            return 5.0
        elif isinstance(error, WebSocketNotConnectedError):
            return 2.0
        else:
            return float(2 ** retry_count)

    async def _sync(self, user_agent: UserAgentPayload | None = None) -> None:
        """
        Выполняет начальную синхронизацию данных с сервером.

        Загружает:
        - Список чатов (диалоги, чаты, каналы)
        - Список контактов
        - Информацию о текущем пользователе (me)

        :param user_agent: Заголовки пользователя (опционально).
        :type user_agent: UserAgentPayload | None
        :return: None

        Пример:
            await client._sync()  # Синхронизация данных
        """
        logger.info("Starting initial sync")

        if user_agent is None:
            user_agent = self.headers or UserAgentPayload()

        payload = SyncPayload(
            interactive=True,
            token=self._token,
            chats_sync=0,
            contacts_sync=0,
            presence_sync=0,
            drafts_sync=0,
            chats_count=40,
            user_agent=user_agent,
        ).model_dump(by_alias=True)
        try:
            data = await self._send_and_wait(opcode=Opcode.LOGIN, payload=payload)
            raw_payload = data.get("payload", {})

            if error := raw_payload.get("error"):
                MixinsUtils.handle_error(data)

            # Парсинг чатов
            for raw_chat in raw_payload.get("chats", []):
                try:
                    if raw_chat.get("type") == ChatType.DIALOG.value:
                        self.dialogs.append(Dialog.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHAT.value:
                        self.chats.append(Chat.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHANNEL.value:
                        self.channels.append(Channel.from_dict(raw_chat))
                except Exception:
                    logger.exception("Error parsing chat entry")

            # Парсинг контактов
            for raw_user in raw_payload.get("contacts", []):
                try:
                    user = User.from_dict(raw_user)
                    if user:
                        self.contacts.append(user)
                except Exception:
                    logger.exception("Error parsing contact entry")

            # Парсинг профиля
            if raw_payload.get("profile", {}).get("contact"):
                self.me = Me.from_dict(raw_payload.get("profile", {}).get("contact", {}))

            logger.info(
                "Sync completed: dialogs=%d chats=%d channels=%d",
                len(self.dialogs),
                len(self.chats),
                len(self.channels),
            )

        except Exception as e:
            logger.exception("Sync failed")
            self.is_connected = False
            if self._ws:
                await self._ws.close()
            self._ws = None
            raise

    async def _get_chat(self, chat_id: int) -> Chat | None:
        """
        Ищет чат по ID в списке чатов.

        :param chat_id: ID чата для поиска.
        :type chat_id: int
        :return: Объект Chat или None если не найден.
        :rtype: Chat | None
        """
        for chat in self.chats:
            if chat.id == chat_id:
                return chat
        return None
