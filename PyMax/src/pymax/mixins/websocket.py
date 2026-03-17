# -*- coding: utf-8 -*-
"""
Mixin для работы с WebSocket подключением.

Предоставляет базовый функционал для установки, поддержания и управления WebSocket соединением
с сервером мессенджера Max. Включает в себя:
- Подключение к WebSocket серверу
- Обработку входящих сообщений в асинхронном режиме
- Отправку сообщений с ожиданием ответа
- Управление очередями входящих/исходящих сообщений
- Обработку разрывов соединения и переподключение

Пример использования:
    class MyClient(WebSocketMixin, OtherMixin):
        async def main(self):
            await self.connect()
            # Работа с WebSocket

Автор: MaxMaster Team
Версия: 0.0.1
"""
import asyncio
import json
from typing import Any

import websockets
from loguru import logger

from typing_extensions import override

from PyMax.src.pymax.exceptions import WebSocketNotConnectedError
from PyMax.src.pymax.interfaces import BaseTransport
from PyMax.src.pymax.payloads import UserAgentPayload
from PyMax.src.pymax.static.constant import (
    WEBSOCKET_ORIGIN,
    RECV_LOOP_BACKOFF_DELAY,
    DEFAULT_TIMEOUT,
)
from PyMax.src.pymax.static.enum import Opcode
from PyMax.src.pymax.types import Chat


class WebSocketMixin(BaseTransport):
    """
    Mixin для работы с WebSocket подключением.

    Предоставляет базовый класс для работы с WebSocket соединением.
    Наследуется от BaseTransport и реализует транспортный уровень для обмена сообщениями.

    Атрибуты:
        _ws: Экземпляр WebSocket соединения (websockets.ClientConnection)
        is_connected: Флаг состояния подключения (bool)
        _incoming: Очередь входящих сообщений (asyncio.Queue)
        _outgoing: Очередь исходящих сообщений (asyncio.Queue)
        _pending: Словарь ожидающих ответов на запросы {seq: Future}
        _recv_task: Задача асинхронного получения сообщений (asyncio.Task)
        _outgoing_task: Задача асинхронной отправки сообщений (asyncio.Task)
        uri: URI WebSocket сервера для подключения
        proxy: Прокси для подключения (опционально)
        chats: Список доступных чатов

    Зависимости:
        Требуется наличие у наследующего класса:
        - uri: строка с адресом WebSocket сервера
        - proxy: опциональная строка прокси
        - chats: список объектов Chat
        - _handshake(): метод для выполнения handshake после подключения
        - _parse_json(): метод парсинга JSON из сырых данных
        - _handle_pending(): метод обработки ожидающих ответов
        - _handle_incoming_queue(): метод обработки входящей очереди
        - _dispatch_incoming(): метод диспетчеризации входящих сообщений
        - _make_message(): метод создания сообщения для отправки
    """

    @property
    def ws(self) -> websockets.ClientConnection:
        """
        Возвращает активное WebSocket соединение.

        Проверяет наличие соединения и его статус. Если соединение отсутствует
        или не активно, выбрасывает WebSocketNotConnectedError.

        :return: Активный экземпляр websockets.ClientConnection.
        :raises WebSocketNotConnectedError: Если соединение не установлено.

        Пример:
            connection = self.ws  # Получение соединения
            await self.ws.send("message")  # Отправка сообщения
        """
        if self._ws is None or not self.is_connected:
            logger.critical("WebSocket not connected when access attempted")
            raise WebSocketNotConnectedError
        return self._ws

    async def connect(self, user_agent: UserAgentPayload | None = None) -> dict[str, Any] | None:
        """
        Устанавливает соединение WebSocket с сервером и выполняет handshake.

        Создаёт новое WebSocket соединение, инициализирует очереди сообщений,
        запускает фоновые задачи для приёма/отправки данных и выполняет
        процедуру handshake для авторизации на сервере.

        Процесс подключения:
        1. Создаёт UserAgentPayload по умолчанию, если не передан
        2. Подключается к WebSocket серверу через websockets.connect()
        3. Инициализирует очереди входящих/исходящих сообщений
        4. Запускает фоновые задачи _recv_loop() и _outgoing_loop()
        5. Выполняет handshake через _handshake()

        :param user_agent: Пользовательский агент для handshake.
                           Содержит заголовки для идентификации клиента.
                           Если None, используется UserAgentPayload по умолчанию.
        :type user_agent: UserAgentPayload | None
        :return: Результат выполнения handshake (словарь с данными или None).
        :rtype: dict[str, Any] | None

        Пример:
            await client.connect()  # Подключение с агентом по умолчанию

            custom_agent = UserAgentPayload(device_type="WEB")
            await client.connect(user_agent=custom_agent)  # Кастомный агент

        Примечание:
            Если соединение уже активно, метод завершается с предупреждением.
        """
        # Создаём пользовательский агент по умолчанию, если не передан
        if user_agent is None:
            user_agent = UserAgentPayload()

        logger.info("Connecting to WebSocket %s", self.uri)

        # Проверяем, не подключено ли уже соединение
        if self._ws is not None or self.is_connected:
            logger.warning("WebSocket уже подключен")
            return

        # Устанавливаем WebSocket соединение с сервером
        self._ws = await websockets.connect(
            self.uri,  # URI сервера
            origin=WEBSOCKET_ORIGIN,  # Origin заголовок для CORS
            user_agent_header=user_agent.header_user_agent,  # Заголовки User-Agent
            proxy=self.proxy,  # Прокси для подключения (если указан)
        )

        # Инициализация состояния подключения
        self.is_connected = True
        self._incoming = asyncio.Queue()  # Очередь входящих сообщений
        self._outgoing = asyncio.Queue()  # Очередь исходящих сообщений
        self._pending = {}  # Словарь ожидающих ответов {seq: Future}

        # Запуск фоновых задач для обработки сообщений
        self._recv_task = asyncio.create_task(self._recv_loop())  # Задача приёма
        self._outgoing_task = asyncio.create_task(self._outgoing_loop())  # Задача отправки

        logger.info("WebSocket подключён, запуск handshake")
        # Выполняем процедуру handshake для авторизации
        return await self._handshake(user_agent)

    async def _recv_loop(self) -> None:
        """
        Асинхронный цикл получения входящих сообщений.

        Работает в фоновом режиме и непрерывно получает сообщения от WebSocket сервера.
        Обрабатывает входящие данные:
        1. Получает сырые данные из WebSocket
        2. Парсит JSON
        3. Проверяет наличие seq (sequence number) для ожидающих запросов
        4. Если seq найден в _pending — устанавливает результат Future
        5. Если seq не найден — добавляет в очередь и диспетчеризирует

        Цикл завершается при разрыве соединения (ConnectionClosed).
        При ошибке выполняется повторная попытка с задержкой (backoff).

        :raises WebSocketNotConnectedError: Устанавливает в ожидающие Future при разрыве.

        Пример:
            # Запускается автоматически при connect()
            # Не требует ручного вызова

        Примечание:
            Метод работает бесконечно до разрыва соединения.
            При ошибке парсинга JSON продолжает работу (возвращает None).
        """
        # Проверяем наличие WebSocket соединения
        if self._ws is None:
            logger.warning("Recv loop started without websocket instance")
            return

        logger.debug("Receive loop started")

        # Бесконечный цикл получения сообщений
        while True:
            try:
                # Получение сырых данных из WebSocket
                raw = await self._ws.recv()
                # Парсинг JSON данных
                data = self._parse_json(raw)

                # Пропускаем некорректные данные
                if data is None:
                    continue

                # Получаем sequence number для сопоставления с ожидающими запросами
                seq = data.get("seq")
                # Проверяем, есть ли ожидающий запрос с таким seq
                if self._handle_pending(seq, data):
                    continue  # Если обработано как ожидающий ответ — переходим к следующему

                # Обработка данных как входящего сообщения
                await self._handle_incoming_queue(data)
                # Диспетчеризация сообщения обработчикам
                await self._dispatch_incoming(data)

            except websockets.exceptions.ConnectionClosed as e:
                # Обработка разрыва соединения
                logger.info(f"WebSocket соединение закрыто с ошибкой: {e.code}, {e.reason}; выход из цикла приёма")
                # Устанавливаем ошибку во все ожидающие Future
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(WebSocketNotConnectedError)
                self._pending.clear()  # Очищаем словарь ожидающих

                # Обновляем состояние подключения
                self.is_connected = False
                self._ws = None
                self._recv_task = None

                break  # Выход из цикла получения
            except Exception:
                # Обработка непредвиденных ошибок с логированием
                logger.exception("Ошибка в recv_loop; кратковременная задержка")
                # Задержка перед повторной попыткой (backoff)
                await asyncio.sleep(RECV_LOOP_BACKOFF_DELAY)

    @override
    async def _send_and_wait(self, opcode: Opcode, payload: dict[str, Any], cmd: int = 0, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """
        Отправляет сообщение и ожидает ответ от сервера.

        Создаёт сообщение с уникальным sequence number, отправляет его через
        WebSocket и ожидает ответа в течение указанного таймаута.
        Использует asyncio.Future для асинхронного ожидания ответа.

        Процесс отправки:
        1. Создаёт сообщение через _make_message() с уникальным seq
        2. Создаёт Future для ожидания ответа
        3. Сохраняет Future в _pending по ключу seq
        4. Отправляет сообщение в WebSocket
        5. Ожидает ответа через asyncio.wait_for()
        6. Возвращает полученные данные или выбрасывает ошибку

        :param opcode: Код операции сообщения (Opcode enum).
                       Определяет тип сообщения (например, запрос, ответ, событие).
        :param payload: Словарь с данными сообщения (тело запроса).
        :param cmd: Код команды (опционально, по умолчанию 0).
                    Используется для дополнительных указаний серверу.
        :param timeout: Таймаут ожидания ответа в секундах.
                        По умолчанию DEFAULT_TIMEOUT из конфигурации.
        :return: Словарь с данными ответа от сервера.
        :rtype: dict[str, Any]
        :raises RuntimeError: Если истёк таймаут или произошла ошибка отправки.

        Пример:
            response = await self._send_and_wait(
                opcode=Opcode.REQUEST,
                payload={"action": "get_users"},
                timeout=10.0
            )

        Примечание:
            Метод автоматически очищает _pending после завершения (finally).
            При повторной отправке с тем же seq старый Future отменяется.
        """
        # Получаем активное WebSocket соединение (проверяет is_connected)
        ws = self.ws
        # Создаём сообщение с уникальным sequence number
        msg = self._make_message(opcode, payload, cmd)
        # Получаем текущий event loop
        loop = asyncio.get_running_loop()
        # Создаём Future для ожидания ответа
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        # Получаем ключ seq для сопоставления ответа
        seq_key = msg["seq"]

        # Проверяем наличие старого ожидающего запроса с тем же seq
        old_fut = self._pending.get(seq_key)
        if old_fut and not old_fut.done():
            old_fut.cancel()  # Отменяем старый Future

        # Сохраняем Future в словарь ожидающих ответов
        self._pending[seq_key] = fut

        try:
            # Логирование отправки сообщения
            logger.debug("Отправка фрейма opcode=%s cmd=%s seq=%s", opcode, cmd, msg["seq"])
            # Отправка JSON сообщения в WebSocket
            await ws.send(json.dumps(msg))
            # Ожидание ответа с таймаутом
            data = await asyncio.wait_for(fut, timeout=timeout)
            # Логирование полученного ответа
            logger.debug("Получен фрейм seq=%s opcode=%s", data.get("seq"), data.get("opcode"))
            return data
        except asyncio.TimeoutError:
            # Обработка истечения таймаута ожидания
            logger.exception("Отправка и ожидание не удались (opcode=%s, seq=%s)", opcode, msg["seq"])
            raise RuntimeError("Отправка и ожидание не удались")
        except Exception:
            # Обработка прочих ошибок отправки/ожидания
            logger.exception("Отправка и ожидание не удались (opcode=%s, seq=%s)", opcode, msg["seq"])
            raise RuntimeError("Отправка и ожидание не удались")
        finally:
            # Очищаем словарь ожидающих (гарантированно выполняется)
            self._pending.pop(seq_key, None)

    @override
    async def _get_chat(self, chat_id: int) -> Chat | None:
        """
        Ищет чат по его идентификатору в списке доступных чатов.

        Выполняет линейный поиск чата в списке self.chats.
        Возвращает первый найденный чат с совпадающим ID.

        :param chat_id: Уникальный идентификатор чата для поиска.
        :type chat_id: int
        :return: Объект Chat с указанным ID, или None если не найден.
        :rtype: Chat | None

        Пример:
            chat = await self._get_chat(12345)
            if chat:
                print(f"Найден чат: {chat.title}")
            else:
                print("Чат не найден")

        Примечание:
            Метод выполняет линейный поиск O(n).
            Для частого поиска рекомендуется использовать кэширование.
        """
        # Линейный поиск чата по списку
        for chat in self.chats:
            if chat.id == chat_id:
                return chat
        return None
