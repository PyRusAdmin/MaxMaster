# -*- coding: utf-8 -*-
"""
Mixin для работы с Socket подключением.

Предоставляет базовый функционал для установки, поддержания и управления TCP socket соединением
с сервером мессенджера Max. Использует SSL/TLS шифрование, сжатие LZ4 и сериализацию MessagePack.

Включает в себя:
- Подключение к TCP серверу через SSL/TLS
- Упаковку/распаковку бинарных пакетов (заголовок + payload)
- Сжатие данных алгоритмом LZ4
- Сериализацию/десериализацию MessagePack
- Обработку входящих сообщений в асинхронном режиме
- Отправку сообщений с ожиданием ответа
- Автоматическое переподключение при разрыве соединения

Структура пакета:
    +-----+-----+-----+-----+-----+----------+----------+
    | ver | cmd | seq | op  | len | payload  |
    +-----+-----+-----+-----+-----+----------+----------+
    | 1B  | 2B  | 1B  | 2B  | 4B  | перемен. |
    +-----+-----+-----+-----+-----+----------+----------+
    Итого заголовок: 10 байт

Пример использования:
    class MyClient(SocketMixin, OtherMixin):
        async def main(self):
            await self.connect()
            # Работа с Socket

Автор: MaxMaster Team
Версия: 0.0.1
"""
import asyncio
import socket
import ssl
import sys
from typing import Any

import lz4.block
import msgpack

from typing_extensions import override

from PyMax.src.pymax.exceptions import SocketNotConnectedError, SocketSendError
from PyMax.src.pymax.interfaces import BaseTransport
from loguru import logger

from PyMax.src.pymax.payloads import UserAgentPayload
from PyMax.src.pymax.static.constant import RECV_LOOP_BACKOFF_DELAY, DEFAULT_TIMEOUT
from PyMax.src.pymax.static.enum import Opcode
from PyMax.src.pymax.types import Chat


class SocketMixin(BaseTransport):
    """
    Mixin для работы с TCP Socket подключением.

    Предоставляет базовый класс для работы с TCP socket соединением поверх SSL/TLS.
    Наследуется от BaseTransport и реализует транспортный уровень для обмена бинарными сообщениями.
    Использует сжатие LZ4 и сериализацию MessagePack для эффективной передачи данных.

    Атрибуты:
        _socket: Экземпляр SSL сокета (ssl.SSLSocket)
        is_connected: Флаг состояния подключения (bool)
        _incoming: Очередь входящих сообщений (asyncio.Queue)
        _outgoing: Очередь исходящих сообщений (asyncio.Queue)
        _pending: Словарь ожидающих ответов на запросы {seq: Future}
        _recv_task: Задача асинхронного получения сообщений (asyncio.Task)
        _outgoing_task: Задача асинхронной отправки сообщений (asyncio.Task)
        _ssl_context: SSL контекст для безопасного соединения
        host: Хост сервера для подключения
        port: Порт сервера для подключения
        user_agent: Пользовательский агент для handshake
        chats: Список доступных чатов

    Зависимости:
        Требуется наличие у наследующего класса:
        - host: строка с адресом хоста
        - port: целое число порта
        - _ssl_context: SSL контекст для подключения
        - user_agent: данные пользователя
        - chats: список объектов Chat
        - _handshake(): метод для выполнения handshake после подключения
        - _handle_pending(): метод обработки ожидающих ответов
        - _handle_incoming_queue(): метод обработки входящей очереди
        - _dispatch_incoming(): метод диспетчеризации входящих сообщений
        - _make_message(): метод создания сообщения для отправки

    Примечание:
        На Python 3.12 возможны проблемы с SSL соединением.
    """

    @property
    def sock(self) -> socket.socket:
        """
        Возвращает активное SSL socket соединение.

        Проверяет наличие соединения и его статус. Если соединение отсутствует
        или не активно, выбрасывает SocketNotConnectedError.

        :return: Активный экземпляр ssl.SSLSocket.
        :raises SocketNotConnectedError: Если соединение не установлено.

        Пример:
            connection = self.sock  # Получение соединения
            self.sock.sendall(data)  # Отправка данных
        """
        if self._socket is None or not self.is_connected:
            logger.critical("Socket not connected when access attempted")
            raise SocketNotConnectedError()
        return self._socket

    def _unpack_packet(self, data: bytes) -> dict[str, Any] | None:
        """
        Распаковывает бинарный пакет в словарь данных.

        Разбирает заголовок пакета (10 байт) и payload, при необходимости
        распаковывает сжатые LZ4 данные и десериализует MessagePack.

        Структура заголовка (10 байт):
            - ver (1 байт): версия протокола
            - cmd (2 байта): код команды
            - seq (1 байт): sequence number (порядковый номер)
            - opcode (2 байта): код операции
            - packed_len (4 байта): длина packed_len (1 байт флаг сжатия + 3 байта длина payload)

        :param data: Сырые бинарные данные пакета.
        :type data: bytes
        :return: Словарь с разобранными данными пакета или None при ошибке.
        :rtype: dict[str, Any] | None

        Пример:
            packet_data = self._unpack_packet(raw_bytes)
            if packet_data:
                opcode = packet_data["opcode"]
                payload = packet_data["payload"]

        Примечание:
            Флаг сжатия находится в старшем бите packed_len.
            При ошибке распаковки LZ4 возвращает None.
        """
        # Разбор заголовка пакета по байтам
        ver = int.from_bytes(data[0:1], "big")  # Версия протокола (1 байт)
        cmd = int.from_bytes(data[1:3], "big")  # Код команды (2 байта)
        seq = int.from_bytes(data[3:4], "big")  # Sequence number (1 байт)
        opcode = int.from_bytes(data[4:6], "big")  # Код операции (2 байта)
        packed_len = int.from_bytes(data[6:10], "big", signed=False)  # Длина + флаг сжатия (4 байта)

        # Извлечение флага сжатия и длины payload из packed_len
        comp_flag = packed_len >> 24  # Старший байт - флаг сжатия
        payload_length = packed_len & 0xFFFFFF  # Оставшиеся 3 байта - длина payload
        payload_bytes = data[10: 10 + payload_length]  # Извлечение байт payload

        payload = None
        if payload_bytes:
            # Если установлен флаг сжатия - распаковываем LZ4
            if comp_flag != 0:
                # TODO: надо выяснить правильный размер распаковки
                # uncompressed_size = int.from_bytes(payload_bytes[0:4], "big")
                compressed_data = payload_bytes
                try:
                    payload_bytes = lz4.block.decompress(
                        compressed_data,
                        uncompressed_size=99999,  # Максимальный размер распакованных данных
                    )
                except lz4.block.LZ4BlockError:
                    # Ошибка распаковки - некорректные данные
                    return None
            # Десериализация MessagePack
            payload = msgpack.unpackb(payload_bytes, raw=False, strict_map_key=False)

        return {
            "ver": ver,
            "cmd": cmd,
            "seq": seq,
            "opcode": opcode,
            "payload": payload,
        }

    def _pack_packet(
            self,
            ver: int,
            cmd: int,
            seq: int,
            opcode: int,
            payload: dict[str, Any],
    ) -> bytes:
        """
        Упаковывает данные в бинарный пакет для отправки.

        Создаёт бинарный пакет с заголовком (10 байт) и сериализованным payload.
        Сериализует данные через MessagePack. Сжатие LZ4 не применяется (только флаг).

        Структура заголовка (10 байт):
            - ver (1 байт): версия протокола
            - cmd (2 байта): код команды
            - seq (1 байт): sequence number (mod 256)
            - opcode (2 байта): код операции
            - payload_len (4 байта): длина payload (24 бита) + флаг сжатия (8 бит)

        :param ver: Версия протокола (0-255).
        :param cmd: Код команды (0-65535).
        :param seq: Sequence number (порядковый номер сообщения).
        :param opcode: Код операции (0-65535).
        :param payload: Словарь с данными для отправки.
        :return: Бинарные данные пакета (заголовок + payload).
        :rtype: bytes

        Пример:
            packet = self._pack_packet(
                ver=1,
                cmd=100,
                seq=42,
                opcode=Opcode.REQUEST,
                payload={"action": "get_users"}
            )
            sock.sendall(packet)

        Примечание:
            seq автоматически приводится к mod 256 (1 байт).
            Флаг сжатия всегда 0 (данные не сжимаются при отправке).
        """
        # Кодирование полей заголовка в байты
        ver_b = ver.to_bytes(1, "big")  # Версия (1 байт)
        cmd_b = cmd.to_bytes(2, "big")  # Команда (2 байта)
        seq_b = (seq % 256).to_bytes(1, "big")  # Sequence (1 байт, mod 256)
        opcode_b = opcode.to_bytes(2, "big")  # Opcode (2 байта)

        # Сериализация payload через MessagePack
        payload_bytes: bytes | None = msgpack.packb(payload)
        if payload_bytes is None:
            payload_bytes = b""

        # Вычисление длины payload с флагом сжатия (старший байт = 0)
        payload_len = len(payload_bytes) & 0xFFFFFF  # 24 бита для длины
        logger.debug("Packing message: payload size=%d bytes", len(payload_bytes))
        payload_len_b = payload_len.to_bytes(4, "big")  # Длина (4 байта)

        # Сборка полного пакета
        return ver_b + cmd_b + seq_b + opcode_b + payload_len_b + payload_bytes

    async def connect(
        self,
        user_agent: UserAgentPayload | None = None,
    ) -> dict[str, Any]:
        """
        Устанавливает SSL socket соединение с сервером и выполняет handshake.

        Создаёт TCP соединение, оборачивает его в SSL, настраивает keep-alive,
        инициализирует очереди сообщений, запускает фоновые задачи для приёма/отправки
        данных и выполняет процедуру handshake для авторизации на сервере.

        Процесс подключения:
        1. Проверяет версию Python (предупреждение для 3.12)
        2. Создаёт TCP соединение через socket.create_connection()
        3. Оборачивает в SSL через _ssl_context.wrap_socket()
        4. Настраивает SO_KEEPALIVE для поддержания соединения
        5. Инициализирует очереди и запускает фоновые задачи
        6. Выполняет handshake через _handshake()

        :param user_agent: Пользовательский агент для handshake.
                           Содержит заголовки для идентификации клиента.
                           Если None, используется UserAgentPayload по умолчанию.
        :type user_agent: UserAgentPayload | None
        :return: Результат выполнения handshake (словарь с данными).
        :rtype: dict[str, Any]

        Пример:
            await client.connect()  # Подключение с агентом по умолчанию

            custom_agent = UserAgentPayload(device_type="WEB")
            await client.connect(user_agent=custom_agent)  # Кастомный агент

        Примечание:
            На Python 3.12 возможны проблемы с SSL соединением.
            Метод использует run_in_executor для неблокирующего создания сокета.
        """
        # Создаём пользовательский агент по умолчанию, если не передан
        if user_agent is None:
            user_agent = UserAgentPayload()

        # Предупреждение о возможных проблемах на Python 3.12
        if sys.version_info[:2] == (3, 12):
            logger.warning(
                """
===============================================================
         ⚠️⚠️ \033[0;31mWARNING: Python 3.12 detected!\033[0m ⚠️⚠️
Socket connections may be unstable, SSL issues are possible.
===============================================================
    """
            )

        logger.info("Connecting to socket %s:%s", self.host, self.port)
        loop = asyncio.get_running_loop()

        # Создание TCP соединения в executor (неблокирующая операция)
        raw_sock = await loop.run_in_executor(
            None, lambda: socket.create_connection((self.host, self.port))
        )

        # Оборачиваем в SSL сокет
        self._socket = self._ssl_context.wrap_socket(raw_sock, server_hostname=self.host)
        # Включаем keep-alive для поддержания соединения
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # Инициализация состояния подключения
        self.is_connected = True
        self._incoming = asyncio.Queue()  # Очередь входящих сообщений
        self._outgoing = asyncio.Queue()  # Очередь исходящих сообщений
        self._pending = {}  # Словарь ожидающих ответов {seq: Future}

        # Запуск фоновых задач для обработки сообщений
        self._recv_task = asyncio.create_task(self._recv_loop())  # Задача приёма
        self._outgoing_task = asyncio.create_task(self._outgoing_loop())  # Задача отправки

        logger.info("Socket connected, starting handshake")
        # Выполняем процедуру handshake для авторизации
        return await self._handshake(user_agent)

    def _recv_exactly(self, sock: socket.socket, n: int) -> bytes:
        """
        Получает ровно n байт из сокета.

        Блокирующая функция, которая читает из сокета до тех пор,
        пока не будет получено ровно n байт или соединение не закроется.

        :param sock: Socket для чтения данных.
        :param n: Количество байт для получения.
        :return: Байты данных (ровно n байт или меньше при закрытии соединения).
        :rtype: bytes

        Пример:
            header = self._recv_exactly(sock, 10)  # Чтение 10 байт заголовка
            payload = self._recv_exactly(sock, payload_length)  # Чтение payload

        Примечание:
            Может блокироваться до получения всех данных.
            Используется в _parse_header и _recv_data.
        """
        buf = bytearray()
        # Читаем до тех пор, пока не наберём n байт
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))  # Чтение доступных данных
            if not chunk:
                # Соединение закрыто - возвращаем что есть
                return bytes(buf)
            buf.extend(chunk)  # Добавляем прочитанное в буфер
        return bytes(buf)

    async def _parse_header(
        self,
        loop: asyncio.AbstractEventLoop,
        sock: socket.socket,
    ) -> bytes | None:
        """
        Асинхронно читает заголовок пакета (10 байт) из сокета.

        Использует _recv_exactly для получения ровно 10 байт заголовка.
        При закрытии соединения обновляет состояние подключения.

        :param loop: Event loop для выполнения в executor.
        :param sock: Socket для чтения данных.
        :return: Байты заголовка (10 байт) или None при закрытии соединения.
        :rtype: bytes | None

        Пример:
            header = await self._parse_header(loop, sock)
            if header:
                payload_length = int.from_bytes(header[6:10], "big")

        Примечание:
            Запускается в executor для неблокирующего чтения.
            При ошибке закрывает сокет и устанавливает is_connected = False.
        """
        # Чтение 10 байт заголовка в executor (неблокирующая операция)
        header = await loop.run_in_executor(
            None, lambda: self._recv_exactly(sock=sock, n=10)
        )

        # Проверка корректности заголовка
        if not header or len(header) < 10:
            logger.info("Socket connection closed; exiting recv loop")
            self.is_connected = False  # Обновляем состояние подключения
            try:
                sock.close()  # Закрываем сокет
            except Exception:
                return None

        return header

    async def _recv_data(
        self,
        loop: asyncio.AbstractEventLoop,
        header: bytes,
        sock: socket.socket,
    ) -> list[dict[str, Any]] | None:
        """
        Асинхронно читает payload пакета и распаковывает данные.

        Извлекает длину payload из заголовка, читает данные из сокета,
        объединяет с заголовком и распаковывает через _unpack_packet.
        Поддерживает пакеты с массивом payload объектов.

        :param loop: Event loop для выполнения в executor.
        :param header: Заголовок пакета (10 байт).
        :param sock: Socket для чтения данных.
        :return: Список словарей с данными пакета или None при ошибке.
        :rtype: list[dict[str, Any]] | None

        Пример:
            datas = await self._recv_data(loop, header, sock)
            for data in datas:
                await self._dispatch_incoming(data)

        Примечание:
            Читает payload частями по 8192 байта.
            Если payload содержит массив - возвращает список пакетов.
        """
        # Извлечение длины payload из заголовка
        packed_len = int.from_bytes(header[6:10], "big", signed=False)
        payload_length = packed_len & 0xFFFFFF  # 24 бита для длины
        remaining = payload_length  # Оставшееся количество байт для чтения
        payload = bytearray()  # Буфер для payload

        # Чтение payload частями
        while remaining > 0:
            min_read = min(remaining, 8192)  # Читаем не более 8192 байт за раз
            chunk = await loop.run_in_executor(
                None, lambda: self._recv_exactly(sock, min_read)
            )
            if not chunk:
                logger.error("Connection closed while reading payload")
                break
            payload.extend(chunk)  # Добавляем прочитанное в буфер
            remaining -= len(chunk)  # Уменьшаем счётчик оставшихся байт

        # Проверка полноты полученных данных
        if remaining > 0:
            logger.error("Incomplete payload received; skipping packet")
            return None

        # Объединение заголовка и payload
        raw = header + payload
        if len(raw) < 10 + payload_length:
            logger.error(
                "Incomplete packet: expected %d bytes, got %d",
                10 + payload_length,
                len(raw),
            )
            await asyncio.sleep(RECV_LOOP_BACKOFF_DELAY)  # Задержка перед повторной попыткой
            return None

        # Распаковка пакета
        data = self._unpack_packet(raw)
        if not data:
            logger.warning("Failed to unpack packet, skipping")
            return None

        # Обработка payload как списка или одиночного объекта
        payload_objs = data.get("payload")
        return (
            [{**data, "payload": obj} for obj in payload_objs]
            if isinstance(payload_objs, list)
            else [data]
        )

    async def _recv_loop(self) -> None:
        """
        Асинхронный цикл получения входящих сообщений.

        Работает в фоновом режиме и непрерывно получает сообщения от Socket сервера.
        Обрабатывает входящие данные:
        1. Читает заголовок пакета (10 байт)
        2. Читает payload по длине из заголовка
        3. Распаковывает пакет через _unpack_packet
        4. Проверяет наличие seq для ожидающих запросов
        5. Если seq найден в _pending — устанавливает результат Future
        6. Если seq не найден — добавляет в очередь и диспетчеризирует

        Цикл завершается при разрыве соединения или отмене задачи.
        При ошибке выполняется повторная попытка с задержкой (backoff).

        :raises asyncio.CancelledError: Пробрасывается при отмене задачи.

        Пример:
            # Запускается автоматически при connect()
            # Не требует ручного вызова

        Примечание:
            Метод работает бесконечно до разрыва соединения.
            Обрабатывает пакеты с массивом payload объектов.
        """
        # Проверяем наличие socket соединения
        if self._socket is None:
            logger.warning("Recv loop started without socket instance")
            return

        sock = self._socket
        loop = asyncio.get_running_loop()

        # Бесконечный цикл получения сообщений
        while True:
            try:
                # Чтение заголовка пакета
                header = await self._parse_header(loop, sock)

                # Если заголовок не получен - соединение закрыто
                if not header:
                    break

                # Чтение и распаковка payload
                datas = await self._recv_data(loop, header, sock)

                # Если данные не получены - переходим к следующему
                if not datas:
                    continue

                # Обработка каждого пакета из списка
                for data_item in datas:
                    seq = data_item.get("seq")

                    # Проверка ожидающих запросов (seq mod 256)
                    if self._handle_pending(seq % 256 if seq is not None else None, data_item):
                        continue  # Если обработано как ожидающий ответ — переходим к следующему

                    # Обработка данных как входящего сообщения
                    if self._incoming is not None:
                        await self._handle_incoming_queue(data_item)

                    # Диспетчеризация сообщения обработчикам
                    await self._dispatch_incoming(data_item)

            except asyncio.CancelledError:
                # Обработка отмены задачи
                logger.debug("Recv loop cancelled")
                raise
            except Exception:
                # Обработка непредвиденных ошибок с логированием
                logger.exception("Error in recv_loop; backing off briefly")
                # Задержка перед повторной попыткой (backoff)
                await asyncio.sleep(RECV_LOOP_BACKOFF_DELAY)

    @override
    async def _send_and_wait(
        self,
        opcode: Opcode,
        payload: dict[str, Any],
        cmd: int = 0,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """
        Отправляет сообщение и ожидает ответ от сервера.

        Создаёт сообщение с уникальным sequence number, упаковывает в бинарный пакет,
        отправляет через SSL socket и ожидает ответа в течение указанного таймаута.
        Использует asyncio.Future для асинхронного ожидания ответа.
        При разрыве соединения пытается автоматически переподключиться.

        Процесс отправки:
        1. Проверяет наличие подключения
        2. Создаёт сообщение через _make_message() с уникальным seq
        3. Упаковывает сообщение через _pack_packet()
        4. Создаёт Future для ожидания ответа
        5. Сохраняет Future в _pending по ключу seq (mod 256)
        6. Отправляет пакет через socket.sendall()
        7. Ожидает ответа через asyncio.wait_for()
        8. Возвращает полученные данные или выбрасывает ошибку
        9. При ошибке соединения - пытается переподключиться

        :param opcode: Код операции сообщения (Opcode enum).
                       Определяет тип сообщения (например, запрос, ответ, событие).
        :param payload: Словарь с данными сообщения (тело запроса).
        :param cmd: Код команды (опционально, по умолчанию 0).
                    Используется для дополнительных указаний серверу.
        :param timeout: Таймаут ожидания ответа в секундах.
                        По умолчанию DEFAULT_TIMEOUT из конфигурации.
        :return: Словарь с данными ответа от сервера.
        :rtype: dict[str, Any]
        :raises SocketNotConnectedError: Если соединение не активно или потеряно.
        :raises SocketSendError: Если истёк таймаут или произошла ошибка отправки.

        Пример:
            response = await self._send_and_wait(
                opcode=Opcode.REQUEST,
                payload={"action": "get_users"},
                timeout=10.0
            )

        Примечание:
            Метод автоматически очищает _pending после завершения (finally).
            При разрыве соединения пытается автоматически переподключиться.
            seq ключ в _pending используется mod 256 (1 байт).
        """
        # Проверка наличия подключения
        if not self.is_connected or self._socket is None:
            raise SocketNotConnectedError

        # Получаем активное socket соединение (проверяет is_connected)
        sock = self.sock
        # Создаём сообщение с уникальным sequence number
        msg = self._make_message(opcode, payload, cmd)
        # Получаем текущий event loop
        loop = asyncio.get_running_loop()
        # Создаём Future для ожидания ответа
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        # Получаем ключ seq для сопоставления ответа (mod 256)
        seq_key = msg["seq"] % 256

        # Проверяем наличие старого ожидающего запроса с тем же seq
        old_fut = self._pending.get(seq_key)
        if old_fut and not old_fut.done():
            old_fut.cancel()  # Отменяем старый Future

        # Сохраняем Future в словарь ожидающих ответов
        self._pending[seq_key] = fut

        try:
            # Логирование отправки сообщения
            logger.debug(
                "Sending frame opcode=%s cmd=%s seq=%s",
                opcode,
                cmd,
                msg["seq"],
            )

            # Упаковка сообщения в бинарный пакет
            packet = self._pack_packet(
                msg["ver"],
                msg["cmd"],
                msg["seq"],
                msg["opcode"],
                msg["payload"],
            )

            # Отправка пакета через socket (в executor для неблокирующей отправки)
            await loop.run_in_executor(None, lambda: sock.sendall(packet))

            # Ожидание ответа с таймаутом
            data = await asyncio.wait_for(fut, timeout=timeout)

            # Логирование полученного ответа
            logger.debug(
                "Received frame for seq=%s opcode=%s",
                data.get("seq"),
                data.get("opcode"),
            )
            return data

        except (ssl.SSLEOFError, ssl.SSLError, ConnectionError) as conn_err:
            # Обработка разрыва SSL/TLS соединения
            logger.warning("Connection lost, reconnecting...")
            self.is_connected = False  # Обновляем состояние подключения

            # Попытка переподключения
            try:
                await self.connect(self.user_agent)
            except Exception as exc:
                logger.exception("Reconnect failed")
                raise exc from conn_err

            raise SocketNotConnectedError from conn_err

        except asyncio.TimeoutError:
            # Обработка истечения таймаута ожидания
            logger.exception("Send and wait failed (opcode=%s, seq=%s)", opcode, msg["seq"])
            raise SocketSendError from None

        except Exception as exc:
            # Обработка прочих ошибок отправки/ожидания
            logger.exception("Send and wait failed (opcode=%s, seq=%s)", opcode, msg["seq"])
            raise SocketSendError from exc

        finally:
            # Очищаем словарь ожидающих (гарантированно выполняется)
            self._pending.pop(msg["seq"] % 256, None)

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
