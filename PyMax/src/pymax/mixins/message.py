# -*- coding: utf-8 -*-
"""
Mixin для работы с сообщениями.

Содержит функционал для отправки, редактирования, удаления сообщений,
а также для загрузки и обработки вложений (фото, видео, файлы).
"""
import asyncio
import time
from http import HTTPStatus
from pathlib import Path

import aiohttp
from aiofiles import open as aio_open
from aiohttp import ClientSession, TCPConnector
from loguru import logger

from PyMax.src.pymax.files import File, Video, Photo
from PyMax.src.pymax.exceptions import Error
from PyMax.src.pymax.formatting import Formatting
from PyMax.src.pymax.payloads import (
    UploadPayload, AttachPhotoPayload, AttachFilePayload, VideoAttachPayload, ReadMessagesPayload,
    RemoveReactionPayload, GetReactionsPayload, AddReactionPayload, ReactionInfoPayload, GetFilePayload,
    GetVideoPayload, FetchHistoryPayload, PinMessagePayload, DeleteMessagePayload, EditMessagePayload, MessageElement,
    SendMessagePayloadMessage, SendMessagePayload, ReplyLink
)
from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.constant import DEFAULT_TIMEOUT
from PyMax.src.pymax.static.enum import Opcode, AttachType, ReadAction
from PyMax.src.pymax.types import Attach, Message, ReadState, ReactionInfo, FileRequest, VideoRequest
from PyMax.src.pymax.utils import MixinsUtils


class MessageMixin(ClientProtocol):
    """Mixin для работы с сообщениями.

    Предоставляет асинхронные методы для полного цикла работы с сообщениями:
    - Отправка и редактирование текстовых сообщений с поддержкой форматирования
    - Загрузка и вложение файлов, фото и видео
    - Управление сообщениями (удаление, закрепление)
    - Работа с историей сообщений
    - Управление реакциями
    - Отметка сообщений как прочитанных

    Класс использует протокол ClientProtocol и взаимодействует с сервером
    через WebSocket-соединение, обеспечивая асинхронную обработку операций.

    Attributes:
        CHUNK_SIZE (int): Размер чанка для потоковой загрузки файлов (6 МБ по умолчанию).
        _file_upload_waiters (dict): Словарь ожидания подтверждения загрузки файлов.
    """
    CHUNK_SIZE = 6 * 1024 * 1024

    async def _upload_file(self, file: File) -> Attach | None:
        """Загружает файл на сервер.

        Метод выполняет поэтапную загрузку файла:
        1. Запрашивает URL для загрузки у сервера
        2. Потоково отправляет файл по чанкам
        3. Ожидает подтверждения обработки от сервера

        Args:
            file (File): Объект файла для загрузки, содержащий путь или байты.

        Returns:
            Attach | None: Объект вложения с file_id при успешной загрузке, иначе None.

        Raises:
            Exception: При ошибках сети, чтения файла или других непредвиденных ошибках.

        Note:
            - Использует CHUNK_SIZE для потоковой передачи
            - Регистрирует waiter для ожидания подтверждения от сервера
            - Автоматически удаляет waiter при таймауте или ошибке
        """
        try:
            logger.info("Uploading file")

            payload = UploadPayload().model_dump(by_alias=True)
            data = await self._send_and_wait(
                opcode=Opcode.FILE_UPLOAD,
                payload=payload,
            )
            if data.get("payload", {}).get("error"):
                MixinsUtils.handle_error(data)

            url = data.get("payload", {}).get("info", [None])[0].get("url", None)
            file_id = data.get("payload", {}).get("info", [None])[0].get("fileId", None)
            if not url or not file_id:
                logger.error("No upload URL or file ID received")
                return None

            logger.debug("Получил URL загрузки и file_id=%s", file_id)

            if file.path:
                file_size = Path(file.path).stat().st_size
                logger.info("Размер файла по пути: %.2f MB", file_size / (1024 * 1024))
            else:
                file_bytes = await file.read()
                file_size = len(file_bytes)
                logger.info("Размер файла по URL: %.2f MB", file_size / (1024 * 1024))

            connector = TCPConnector(limit=0)
            timeout = aiohttp.ClientTimeout(total=None, sock_read=None, sock_connect=30)

            headers = {
                "Content-Disposition": f"attachment; filename={file.file_name}",
                "Content-Length": str(file_size),
                "Content-Range": f"0-{file_size - 1}/{file_size}",
            }

            loop = asyncio.get_running_loop()
            fut: asyncio.Future[dict] = loop.create_future()
            self._file_upload_waiters[int(file_id)] = fut

            async def file_generator():
                bytes_sent = 0
                chunk_num = 0
                logger.debug("Запуск потоковой передачи файлов из: %s", file.path)
                async with aio_open(file.path, "rb") as f:
                    while True:
                        chunk = await f.read(self.CHUNK_SIZE)
                        if not chunk:
                            logger.info(
                                "Трансляция файлов завершена: %d bytes in %d chunks",
                                bytes_sent,
                                chunk_num,
                            )
                            break

                        yield chunk

                        bytes_sent += len(chunk)
                        chunk_num += 1
                        if chunk_num % 10 == 0:
                            logger.info(
                                "Прогресс загрузки: %.1f MB in %d chunks",
                                bytes_sent / (1024 * 1024),
                                chunk_num,
                            )
                        if chunk_num % 4 == 0:
                            await asyncio.sleep(0)

            async def bytes_generator(b: bytes):
                bytes_sent = 0
                chunk_num = 0
                for i in range(0, len(b), self.CHUNK_SIZE):
                    chunk = b[i: i + self.CHUNK_SIZE]
                    yield chunk
                    bytes_sent += len(chunk)
                    chunk_num += 1
                    if chunk_num % 10 == 0:
                        logger.info(
                            "Прогресс загрузки: %.1f MB in %d chunks",
                            bytes_sent / (1024 * 1024),
                            chunk_num,
                        )
                    if chunk_num % 4 == 0:
                        await asyncio.sleep(0)

            if file.path:
                data_to_send = file_generator()
            else:
                data_to_send = bytes_generator(file_bytes)

            logger.info("Загрузка стартового файла: %s", file.file_name)

            async with (
                ClientSession(connector=connector, timeout=timeout) as session,
                session.post(url=url, headers=headers, data=data_to_send) as response,
            ):
                logger.debug("Server response status: %d", response.status)
                if response.status != HTTPStatus.OK:
                    logger.error("Upload failed with status %s", response.status)
                    self._file_upload_waiters.pop(int(file_id), None)
                    return None

                logger.debug(
                    "Файл успешно отправлен. Жду подтверждения от сервера (timeout=%d seconds, fileId=%s)",
                    DEFAULT_TIMEOUT,
                    file_id,
                )
                try:
                    await asyncio.wait_for(fut, timeout=DEFAULT_TIMEOUT)
                    logger.info("Загрузка файла успешно завершена (fileId=%s)", file_id)
                    return Attach(_type=AttachType.FILE, file_id=file_id)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Время истекло в ожидании уведомления о обработке файла fileId=%s",
                        file_id,
                    )
                    self._file_upload_waiters.pop(int(file_id), None)
                    return None

        except Exception:
            logger.exception("Upload file failed")
            raise

    async def _upload_video(self, video: Video) -> Attach | None:
        """Загружает видео на сервер.

        Метод загружает видеофайл на сервер с поддержкой больших файлов:
        1. Получает URL и токен для загрузки
        2. Отправляет видео одним запросом (не потоково)
        3. Ожидает подтверждения обработки

        Args:
            video (Video): Объект видео для загрузки.

        Returns:
            Attach | None: Объект вложения с video_id и token при успехе, иначе None.

        Raises:
            Exception: При ошибках сети, памяти (malloc failure) или других ошибках.
            OSError: При ошибках операционной системы, связанных с памятью.

        Note:
            - Использует увеличенный таймаут (15 минут) для больших видео
            - Обрабатывает специфические ошибки памяти при загрузке
            - Требует достаточного объема оперативной памяти для буферизации видео
        """
        try:
            logger.info("Загрузка видео")
            payload = UploadPayload().model_dump(by_alias=True)
            data = await self._send_and_wait(
                opcode=Opcode.VIDEO_UPLOAD,
                payload=payload,
            )

            if data.get("payload", {}).get("error"):
                MixinsUtils.handle_error(data)

            url = data.get("payload", {}).get("info", [None])[0].get("url", None)
            video_id = data.get("payload", {}).get("info", [None])[0].get("videoId", None)
            if not url or not video_id:
                logger.error("Не получено URL для загрузки или видео ID")
                return None

            token = data.get("payload", {}).get("info", [None])[0].get("token", None)
            if not token:
                logger.error("Токен загрузки не получен")
                return None

            file_bytes = await video.read()
            file_size = len(file_bytes)

            # Настройки для ClientSession
            connector = TCPConnector(limit=0)
            timeout = aiohttp.ClientTimeout(total=900, sock_read=60)  # 15 минут на видео

            headers = {
                "Content-Disposition": f"attachment; filename={video.file_name}",
                "Content-Range": f"0-{file_size - 1}/{file_size}",
                "Content-Length": str(file_size),
                "Connection": "keep-alive",
            }

            loop = asyncio.get_running_loop()
            fut: asyncio.Future[dict] = loop.create_future()
            try:
                self._file_upload_waiters[int(video_id)] = fut
            except Exception:
                logger.exception("Не смог зарегистрировать загрузку файла, официант")

            try:
                async with ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.post(
                            url=url,
                            headers=headers,
                            data=file_bytes,
                    ) as response:
                        if response.status != HTTPStatus.OK:
                            logger.error("Загрузка не получилась с статусом %s", response.status)
                            self._file_upload_waiters.pop(int(video_id), None)
                            return None

                        try:
                            await asyncio.wait_for(fut, timeout=DEFAULT_TIMEOUT)
                            return Attach(_type=AttachType.VIDEO, video_id=video_id, token=token)
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Время задержка в ожидании уведомления о обработке видео videoId=%s",
                                video_id,
                            )
                            self._file_upload_waiters.pop(int(video_id), None)
                            return None
            except OSError as e:
                if "malloc failure" in str(e) or "BUF" in str(e):
                    logger.exception(
                        "Ошибка памяти при загрузке видео. Файл слишком большой или недостаточно памяти. Попробуйте загружать меньшие файлы или освободить память."
                    )
                    self._file_upload_waiters.pop(int(video_id), None)
                raise

        except Exception:
            logger.exception("Загрузка видео не получилась")
            raise

    async def _upload_photo(self, photo: Photo) -> Attach | None:
        """Загружает фотографию на сервер.

        Метод загружает изображение в формате multipart/form-data:
        1. Получает URL для загрузки
        2. Валидирует формат изображения
        3. Отправляет фото с правильным content-type
        4. Извлекает токен из ответа

        Args:
            photo (Photo): Объект фотографии для загрузки.

        Returns:
            Attach | None: Объект вложения с photo_token при успехе, иначе None.

        Raises:
            Exception: При ошибках сети, валидации фото или других ошибках.

        Note:
            - Поддерживает различные форматы изображений (определяются автоматически)
            - Использует стандартный таймаут для HTTP-запросов
            - Возвращает None при неудачной валидации или отсутствии токена
        """
        try:
            logger.info("Загрузка фотографии")
            payload = UploadPayload().model_dump(by_alias=True)

            data = await self._send_and_wait(
                opcode=Opcode.PHOTO_UPLOAD,
                payload=payload,
            )

            if data.get("payload", {}).get("error"):
                MixinsUtils.handle_error(data)

            url = data.get("payload", {}).get("url")
            if not url:
                logger.error("No upload URL received")
                return None

            photo_data = photo.validate_photo()
            if not photo_data:
                logger.error("Проверка фото не прошла")
                return None

            form = aiohttp.FormData()
            form.add_field(
                name="file",
                value=await photo.read(),
                filename=f"image.{photo_data[0]}",
                content_type=photo_data[1],
            )

            async with (
                ClientSession() as session,
                session.post(
                    url=url,
                    data=form,
                ) as response,
            ):
                if response.status != HTTPStatus.OK:
                    logger.error(f"Загрузка не получилась с статусом {response.status}")
                    return None

                result = await response.json()

                if not result.get("photos"):
                    logger.error("No photos in response")
                    return None

                photo_data = next(iter(result["photos"].values()), None)
                if not photo_data or "token" not in photo_data:
                    logger.error("No token in response")
                    return None

                return Attach(
                    _type=AttachType.PHOTO,
                    photo_token=photo_data["token"],
                )

        except Exception as e:
            logger.exception("Upload photo failed: %s", str(e))
            return None

    async def _upload_attachment(self, attach: Photo | File | Video) -> dict | None:
        """Загружает вложение и возвращает соответствующий payload.

        Метод определяет тип вложения и вызывает соответствующий метод загрузки:
        - Photo -> _upload_photo
        - File -> _upload_file
        - Video -> _upload_video

        Args:
            attach (Photo | File | Video): Объект вложения для загрузки.

        Returns:
            dict | None: Словарь с данными вложения в формате payload при успехе, иначе None.

        Note:
            - Автоматически выбирает метод загрузки по типу вложения
            - Возвращает None при неудачной загрузке любого типа вложения
            - Логгирует ошибку при неудачной загрузке
        """
        if isinstance(attach, Photo):
            uploaded = await self._upload_photo(attach)
            if uploaded and uploaded.photo_token:
                return AttachPhotoPayload(photo_token=uploaded.photo_token).model_dump(
                    by_alias=True
                )
        elif isinstance(attach, File):
            uploaded = await self._upload_file(attach)
            if uploaded and uploaded.file_id:
                return AttachFilePayload(file_id=uploaded.file_id).model_dump(by_alias=True)
        elif isinstance(attach, Video):
            uploaded = await self._upload_video(attach)
            if uploaded and uploaded.video_id and uploaded.token:
                return VideoAttachPayload(
                    video_id=uploaded.video_id, token=uploaded.token
                ).model_dump(by_alias=True)
        logger.error(f"Attachment upload failed for {attach}")
        return None

    async def send_message(
            self,
            text: str,
            chat_id: int,
            notify: bool = True,
            attachment: Photo | File | Video | None = None,
            attachments: list[Photo | File | Video] | None = None,
            reply_to: int | None = None,
            use_queue: bool = False,
    ) -> Message | None:
        """Отправляет текстовое сообщение в чат с опциональными вложениями.

        Метод поддерживает отправку сообщений с различными типами вложений
        и возможностью ответа на существующее сообщение. При наличии markdown-разметки
        автоматически извлекает элементы форматирования.

        Args:
            text (str): Текст сообщения. Может содержать markdown-разметку.
            chat_id (int): Идентификатор чата для отправки.
            notify (bool, optional): Флаг уведомления участников чата. Defaults to True.
            attachment (Photo | File | Video | None, optional): Одиночное вложение. Defaults to None.
            attachments (list[Photo | File | Video] | None, optional): Список вложений. Defaults to None.
            reply_to (int | None, optional): ID сообщения, на которое идет ответ. Defaults to None.
            use_queue (bool, optional): Использовать очередь отправки. Defaults to False.

        Returns:
            Message | None: Объект отправленного сообщения или None при использовании очереди.

        Raises:
            Error: При ошибках загрузки вложений или отправки сообщения.

        Note:
            - Если указаны и attachment, и attachments, используется только attachments
            - При использовании очереди возвращается None
            - Автоматически обрабатывает markdown-разметку в тексте
        """

        logger.info("Sending message to chat_id=%s notify=%s", chat_id, notify)
        if attachments and attachment:
            logger.warning("Both photo and photos provided; using photos")
            attachment = None

        attaches = []
        if attachment:
            logger.info("Uploading attachment for message")
            result = await self._upload_attachment(attachment)
            if not result:
                raise Error("upload_failed", "Failed to upload attachment", "Upload Error")
            attaches.append(result)

        elif attachments:
            logger.info("Uploading multiple attachments for message")
            for p in attachments:
                result = await self._upload_attachment(p)
                if result:
                    attaches.append(result)
                else:
                    raise Error("upload_failed", "Failed to upload attachment", "Upload Error")

            if not attaches:
                raise Error("upload_failed", "All attachments failed to upload", "Upload Error")

        elements = []
        clean_text = None
        raw_elements, parsed_text = Formatting.get_elements_from_markdown(text)
        if raw_elements:
            clean_text = parsed_text
        elements = [
            MessageElement(type=e.type, length=e.length, from_=e.from_) for e in raw_elements
        ]

        payload = SendMessagePayload(
            chat_id=chat_id,
            message=SendMessagePayloadMessage(
                text=clean_text if clean_text else text,
                cid=int(time.time() * 1000),
                elements=elements,
                attaches=attaches,
                link=(ReplyLink(message_id=str(reply_to)) if reply_to else None),
            ),
            notify=notify,
        ).model_dump(by_alias=True)

        if use_queue:
            await self._queue_message(opcode=Opcode.MSG_SEND, payload=payload)
            logger.debug("Message queued for sending")
            return None

        data = await self._send_and_wait(opcode=Opcode.MSG_SEND, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        msg = Message.from_dict(data["payload"]) if data.get("payload") else None
        logger.debug("send_message result: %r", msg)
        if not msg:
            raise Error("no_message", "Message data missing in response", "Message Error")

        return msg

    async def edit_message(
            self,
            chat_id: int,
            message_id: int,
            text: str,
            attachment: Photo | File | Video | None = None,
            attachments: list[Photo | Video | File] | None = None,
            use_queue: bool = False,
    ) -> Message | None:
        """Редактирует существующее сообщение.

        Метод позволяет изменить текст и/или вложения сообщения. Поддерживает
        markdown-форматирование и добавление новых вложений.

        Args:
            chat_id (int): Идентификатор чата.
            message_id (int): Идентификатор редактируемого сообщения.
            text (str): Новый текст сообщения с возможной markdown-разметкой.
            attachment (Photo | File | Video | None, optional): Новое одиночное вложение. Defaults to None.
            attachments (list[Photo | Video | File] | None, optional): Новый список вложений. Defaults to None.
            use_queue (bool, optional): Использовать очередь отправки. Defaults to False.

        Returns:
            Message | None: Объект отредактированного сообщения или None при использовании очереди.

        Raises:
            Error: При ошибках загрузки вложений или редактирования сообщения.

        Note:
            - Если указаны и attachment, и attachments, используется только attachments
            - При использовании очереди возвращается None
            - Автоматически обрабатывает markdown-разметку в тексте
        """
        logger.info("Editing message chat_id=%s message_id=%s", chat_id, message_id)

        if attachments and attachment:
            logger.warning("Both photo and photos provided; using photos")
            attachment = None

        attaches = []
        if attachment:
            logger.info("Uploading attachment for message")
            result = await self._upload_attachment(attachment)
            if not result:
                raise Error("upload_failed", "Failed to upload attachment", "Upload Error")
            attaches.append(result)

        elif attachments:
            logger.info("Uploading multiple attachments for message")
            for p in attachments:
                result = await self._upload_attachment(p)
                if result:
                    attaches.append(result)
                else:
                    raise Error("upload_failed", "Failed to upload attachment", "Upload Error")

            if not attaches:
                raise Error("upload_failed", "All attachments failed to upload", "Upload Error")

        elements = []
        clean_text = None
        raw_elements = Formatting.get_elements_from_markdown(text)[0]
        if raw_elements:
            clean_text = Formatting.get_elements_from_markdown(text)[1]
        elements = [
            MessageElement(type=e.type, length=e.length, from_=e.from_) for e in raw_elements
        ]

        payload = EditMessagePayload(
            chat_id=chat_id,
            message_id=message_id,
            text=clean_text if clean_text else text,
            elements=elements,
            attaches=attaches,
        ).model_dump(by_alias=True)

        if use_queue:
            await self._queue_message(opcode=Opcode.MSG_EDIT, payload=payload)
            logger.debug("Edit message queued for sending")
            return None

        data = await self._send_and_wait(opcode=Opcode.MSG_EDIT, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        msg = Message.from_dict(data["payload"]) if data.get("payload") else None
        logger.debug("edit_message result: %r", msg)
        if not msg:
            raise Error("no_message", "Message data missing in response", "Message Error")

        return msg

    async def delete_message(
            self,
            chat_id: int,
            message_ids: list[int],
            for_me: bool,
            use_queue: bool = False,
    ) -> bool:
        """Удаляет одно или несколько сообщений в чате.

        Метод предоставляет возможность удаления сообщений либо только для
        текущего пользователя, либо для всех участников чата.

        Args:
            chat_id (int): Идентификатор чата.
            message_ids (list[int]): Список ID сообщений для удаления.
            for_me (bool): Флаг удаления только для себя (если True) или для всех.
            use_queue (bool, optional): Использовать очередь отправки. Defaults to False.

        Returns:
            bool: True при успешном удалении, иначе False.

        Note:
            - При for_me=True сообщение удаляется только из локального интерфейса
            - При for_me=False сообщение удаляется для всех участников чата
            - Поддерживает удаление нескольких сообщений за один вызов
        """
        logger.info(
            "Deleting messages chat_id=%s ids=%s for_me=%s",
            chat_id,
            message_ids,
            for_me,
        )

        payload = DeleteMessagePayload(
            chat_id=chat_id, message_ids=message_ids, for_me=for_me
        ).model_dump(by_alias=True)

        if use_queue:
            await self._queue_message(opcode=Opcode.MSG_DELETE, payload=payload)
            logger.debug("Delete message queued for sending")
            return True

        data = await self._send_and_wait(opcode=Opcode.MSG_DELETE, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug("delete_message success")
        return True

    async def pin_message(self, chat_id: int, message_id: int, notify_pin: bool) -> bool:
        """Закрепляет сообщение в чате.

        Метод фиксирует сообщение в верхней части чата, делая его более заметным.
        Поддерживает отправку уведомления о закреплении всем участникам чата.

        Args:
            chat_id (int): Идентификатор чата.
            message_id (int): Идентификатор сообщения для закрепления.
            notify_pin (bool): Флаг отправки уведомления о закреплении.

        Returns:
            bool: True при успешном закреплении, иначе False.

        Note:
            - Только один пользователь может закрепить сообщение
            - Уведомление видно всем участникам чата при notify_pin=True
            - Закрепленные сообщения обычно отображаются в специальном разделе чата
        """
        payload = PinMessagePayload(
            chat_id=chat_id,
            notify_pin=notify_pin,
            pin_message_id=message_id,
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.CHAT_UPDATE, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug("pin_message success")
        return True

    async def fetch_history(
            self,
            chat_id: int,
            from_time: int | None = None,
            forward: int = 0,
            backward: int = 200,
    ) -> list[Message] | None:
        """Получает историю сообщений из чата.

        Метод загружает сообщения из чата в указанном временном диапазоне,
        позволяя получать как новые, так и старые сообщения относительно
        заданной временной метки.

        Args:
            chat_id (int): Идентификатор чата.
            from_time (int | None, optional): Временная метка начала выборки в мс.
                Если None, используется текущее время. Defaults to None.
            forward (int, optional): Количество сообщений в будущем (после from_time).
                Defaults to 0.
            backward (int, optional): Количество сообщений в прошлом (до from_time).
                Defaults to 200.

        Returns:
            list[Message] | None: Список объектов сообщений или None при ошибке.

        Note:
            - Максимальное количество возвращаемых сообщений: forward + backward
            - Сообщения сортируются по времени (от старых к новым)
            - При from_time=None выборка идет от текущего времени
            - Используется для первоначальной загрузки истории и подгрузки старых сообщений
        """
        if from_time is None:
            from_time = int(time.time() * 1000)

        logger.info(
            "Fetching history chat_id=%s from=%s forward=%s backward=%s",
            chat_id,
            from_time,
            forward,
            backward,
        )

        payload = FetchHistoryPayload(
            chat_id=chat_id,
            from_time=from_time,
            forward=forward,
            backward=backward,
        ).model_dump(by_alias=True)

        logger.debug("Payload dict keys: %s", list(payload.keys()))

        data = await self._send_and_wait(opcode=Opcode.CHAT_HISTORY, payload=payload, timeout=10)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        messages = [Message.from_dict(msg) for msg in data["payload"].get("messages", [])]
        logger.debug("History fetched: %d messages", len(messages))
        return messages

    async def get_video_by_id(
            self,
            chat_id: int,
            message_id: int,
            video_id: int,
    ) -> VideoRequest | None:
        """Получает информацию о видео по его идентификатору.

        Метод запрашивает у сервера данные о видеофайле, включая URL для просмотра
        и другую метаинформацию, необходимую для воспроизведения.

        Args:
            chat_id (int): Идентификатор чата, содержащего сообщение с видео.
            message_id (int): Идентификатор сообщения, содержащего видео.
            video_id (int): Идентификатор видеофайла.

        Returns:
            VideoRequest | None: Объект с информацией о видео или None при ошибке.

        Raises:
            Error: При отсутствии данных о видео в ответе сервера.

        Note:
            - Используется для получения URL и метаданных видео перед воспроизведением
            - Поддерживает работу как с подключенным, так и с отключенным состоянием
            - Возвращает объект VideoRequest с полной информацией для воспроизведения
        """
        logger.info("Getting video_id=%s message_id=%s", video_id, message_id)

        if self.is_connected and self._socket is not None:
            payload = GetVideoPayload(
                chat_id=chat_id, message_id=message_id, video_id=video_id
            ).model_dump(by_alias=True)
        else:
            payload = GetVideoPayload(
                chat_id=chat_id,
                message_id=str(message_id),
                video_id=video_id,
            ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.VIDEO_PLAY, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        video = VideoRequest.from_dict(data["payload"]) if data.get("payload") else None
        logger.debug("result: %r", video)
        if not video:
            raise Error("no_video", "Video data missing in response", "Video Error")

        return video

    async def get_file_by_id(
            self,
            chat_id: int,
            message_id: int,
            file_id: int,
    ) -> FileRequest | None:
        """Получает информацию о файле по его идентификатору.

        Метод запрашивает у сервера данные о файле, включая URL для скачивания
        и другую метаинформацию, необходимую для загрузки.

        Args:
            chat_id (int): Идентификатор чата, содержащего сообщение с файлом.
            message_id (int): Идентификатор сообщения, содержащего файл.
            file_id (int): Идентификатор файла.

        Returns:
            FileRequest | None: Объект с информацией о файле или None при ошибке.

        Raises:
            Error: При отсутствии данных о файле в ответе сервера.

        Note:
            - Используется для получения URL и метаданных файла перед скачиванием
            - Поддерживает работу как с подключенным, так и с отключенным состоянием
            - Возвращает объект FileRequest с полной информацией для загрузки
        """
        logger.info("Getting file_id=%s message_id=%s", file_id, message_id)
        if self.is_connected and self._socket is not None:
            payload = GetFilePayload(
                chat_id=chat_id, message_id=message_id, file_id=file_id
            ).model_dump(by_alias=True)
        else:
            payload = GetFilePayload(
                chat_id=chat_id,
                message_id=str(message_id),
                file_id=file_id,
            ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.FILE_DOWNLOAD, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        file = FileRequest.from_dict(data["payload"]) if data.get("payload") else None
        logger.debug(" result: %r", file)
        if not file:
            raise Error("no_file", "File data missing in response", "File Error")

        return file

    async def add_reaction(
            self,
            chat_id: int,
            message_id: str,
            reaction: str,
    ) -> ReactionInfo | None:
        """Добавляет реакцию к сообщению.

        Метод устанавливает указанную реакцию (эмодзи) на сообщение,
        отображая реакцию для других участников чата.

        Args:
            chat_id (int): Идентификатор чата.
            message_id (str): Идентификатор сообщения.
            reaction (str): Эмодзи-реакция для добавления.

        Returns:
            ReactionInfo | None: Объект с информацией о реакции или None при ошибке.

        Note:
            - Реакция отображается под сообщением для всех участников чата
            - Пользователь может иметь только одну реакцию на сообщение
            - При повторном вызове с другой реакцией предыдущая заменяется
            - Поддерживает любые валидные эмодзи в качестве реакции
        """
        try:
            logger.info(
                "Adding reaction to message chat_id=%s message_id=%s reaction=%s",
                chat_id,
                message_id,
                reaction,
            )

            payload = AddReactionPayload(
                chat_id=chat_id,
                message_id=message_id,
                reaction=ReactionInfoPayload(id=reaction),
            ).model_dump(by_alias=True)

            data = await self._send_and_wait(opcode=Opcode.MSG_REACTION, payload=payload)

            if data.get("payload", {}).get("error"):
                MixinsUtils.handle_error(data)

            logger.debug("add_reaction success")
            return (
                ReactionInfo.from_dict(data["payload"]["reactionInfo"])
                if data.get("payload")
                else None
            )
        except Exception:
            logger.exception("Add reaction failed")
            return None

    async def get_reactions(
            self, chat_id: int, message_ids: list[str]
    ) -> dict[str, ReactionInfo] | None:
        """Получает реакции на указанные сообщения.

        Метод запрашивает информацию о реакциях для списка сообщений,
        возвращая данные о текущих реакциях на каждом сообщении.

        Args:
            chat_id (int): Идентификатор чата.
            message_ids (list[str]): Список идентификаторов сообщений.

        Returns:
            dict[str, ReactionInfo] | None: Словарь с ID сообщений и объектами ReactionInfo
                или None при ошибке.

        Note:
            - Возвращает только текущие активные реакции
            - Каждый элемент словаря содержит полную информацию о реакции
            - Используется для синхронизации состояния реакций в интерфейсе
            - Поддерживает получение реакций для нескольких сообщений за один запрос
        """
        logger.info(
            "Getting reactions for messages chat_id=%s message_ids=%s",
            chat_id,
            message_ids,
        )

        payload = GetReactionsPayload(chat_id=chat_id, message_ids=message_ids).model_dump(
            by_alias=True
        )

        data = await self._send_and_wait(opcode=Opcode.MSG_GET_REACTIONS, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        reactions = {}
        for msg_id, reaction_data in data.get("payload", {}).get("messagesReactions", {}).items():
            reactions[msg_id] = ReactionInfo.from_dict(reaction_data)

        logger.debug("get_reactions success")
        return reactions

    async def remove_reaction(
            self,
            chat_id: int,
            message_id: str,
    ) -> ReactionInfo | None:
        """Удаляет реакцию с сообщения.

        Метод убирает реакцию текущего пользователя с указанного сообщения,
        скрывая реакцию от других участников чата.

        Args:
            chat_id (int): Идентификатор чата.
            message_id (str): Идентификатор сообщения.

        Returns:
            ReactionInfo | None: Объект с информацией об удаленной реакции или None при ошибке.

        Raises:
            Error: При отсутствии данных о реакции в ответе сервера.

        Note:
            - Удаляет только реакцию текущего пользователя
            - Сообщение может сохранять реакции от других пользователей
            - После удаления реакция больше не отображается под сообщением
            - Возвращает информацию об удаленной реакции для возможного восстановления
        """
        logger.info(
            "Removing reaction from message chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )

        payload = RemoveReactionPayload(chat_id=chat_id, message_id=message_id, ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.MSG_CANCEL_REACTION, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug("remove_reaction success")
        if not data.get("payload"):
            raise Error("no_reaction", "Reaction data missing in response", "Reaction Error")

        reaction = ReactionInfo.from_dict(data["payload"]["reactionInfo"])
        if not reaction:
            raise Error(
                "invalid_reaction",
                "Invalid reaction data in response",
                "Reaction Error",
            )

        return reaction

    async def read_message(self, message_id: int, chat_id: int) -> ReadState:
        """Отмечает сообщение как прочитанное.

        Метод обновляет состояние прочтения для указанного сообщения,
        устанавливая отметку времени прочтения и обновляя индикаторы
        непрочитанных сообщений в чате.

        Args:
            message_id (int): Идентификатор сообщения для отметки.
            chat_id (int): Идентификатор чата, содержащего сообщение.

        Returns:
            ReadState: Объект с информацией о состоянии прочтения.

        Note:
            - Синхронизирует состояние прочтения с сервером
            - Обновляет локальные индикаторы непрочитанных сообщений
            - Используется для поддержания согласованности между устройствами
            - Вызывается автоматически при открытии чата или прокрутке к сообщению
        """
        logger.info("Marking message as read chat_id=%s message_id=%s", chat_id, message_id)

        payload = ReadMessagesPayload(
            type=ReadAction.READ_MESSAGE,
            chat_id=chat_id,
            message_id=str(message_id),
            mark=int(time.time() * 1000),
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.CHAT_MARK, payload=payload)

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug("read_message success")
        return ReadState.from_dict(data["payload"])
