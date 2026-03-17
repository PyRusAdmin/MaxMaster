# -*- coding: utf-8 -*-
"""
Модуль для работы с файлами (фото, видео, документы).

Содержит классы для загрузки и чтения файлов.
"""
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from aiofiles import open as aio_open
from aiohttp import ClientSession
from typing_extensions import override


class BaseFile(ABC):
    """
    Базовый класс для работы с файлами.

    Поддерживает загрузку из URL, пути или raw данных.
    """

    def __init__(self, raw: bytes | None = None, *, url: str | None = None, path: str | None = None) -> None:
        """
        Инициализирует файл.

        :param raw: Raw данные файла.
        :type raw: bytes | None
        :param url: URL для загрузки файла.
        :type url: str | None
        :param path: Путь к файлу.
        :type path: str | None
        :raises ValueError: Если не указан ни URL, ни путь.
        """
        self.raw = raw
        self.url = url
        self.path = path

        if self.url is None and self.path is None:
            raise ValueError("Either url or path must be provided.")

        if self.url and self.path:
            raise ValueError("Only one of url or path must be provided.")

    @abstractmethod
    async def read(self) -> bytes:
        """
        Читает содержимое файла.

        :return: Raw данные файла.
        :rtype: bytes
        """
        if self.raw is not None:
            return self.raw

        if self.url:
            async with (
                ClientSession() as session,
                session.get(self.url) as response,
            ):
                response.raise_for_status()
                return await response.read()
        elif self.path:
            async with aio_open(self.path, "rb") as f:
                return await f.read()
        else:
            raise ValueError("Either url or path must be provided.")


class Photo(BaseFile):
    """
    Класс для работы с фотографиями.

    Поддерживает форматы: JPG, JPEG, PNG, GIF, WEBP, BMP.
    """
    ALLOWED_EXTENSIONS: ClassVar[set[str]] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
    }

    def __init__(self, raw: bytes | None = None, *, url: str | None = None, path: str | None = None, name: str | None = None) -> None:
        """
        Инициализирует фотографию.

        :param raw: Raw данные изображения.
        :type raw: bytes | None
        :param url: URL для загрузки изображения.
        :type url: str | None
        :param path: Путь к файлу изображения.
        :type path: str | None
        :param name: Имя файла.
        :type name: str | None
        """
        if path:
            self.file_name = Path(path).name
        elif url:
            self.file_name = Path(url).name
        elif name:
            self.file_name = name
        else:
            self.file_name = ""

        super().__init__(raw=raw, url=url, path=path)

    def validate_photo(self) -> tuple[str, str] | None:
        """
        Проверяет корректность фотографии (расширение и MIME-тип).

        :return: Кортеж (расширение, MIME-тип) или None.
        :rtype: tuple[str, str] | None
        :raises ValueError: Если формат файла недопустим.
        """
        if self.path:
            extension = Path(self.path).suffix.lower()
            if extension not in self.ALLOWED_EXTENSIONS:
                raise ValueError(
                    f"Invalid photo extension: {extension}. Allowed: {self.ALLOWED_EXTENSIONS}"
                )

            return (extension[1:], ("image/" + extension[1:]).lower())
        elif self.url:
            extension = Path(self.url).suffix.lower()
            if extension not in self.ALLOWED_EXTENSIONS:
                raise ValueError(
                    f"Invalid photo extension in URL: {extension}. Allowed: {self.ALLOWED_EXTENSIONS}"
                )

            mime_type = mimetypes.guess_type(self.url)[0]

            if not mime_type or not mime_type.startswith("image/"):
                raise ValueError(f"URL does not appear to be an image: {self.url}")

            return (extension[1:], mime_type)
        return None

    @override
    async def read(self) -> bytes:
        """
        Читает содержимое фотографии.

        :return: Raw данные изображения.
        :rtype: bytes
        """
        return await super().read()


class Video(BaseFile):
    """
    Класс для работы с видеофайлами.
    """

    def __init__(self, raw: bytes | None = None, *, url: str | None = None, path: str | None = None) -> None:
        """
        Инициализирует видео.

        :param raw: Raw данные видео.
        :type raw: bytes | None
        :param url: URL для загрузки видео.
        :type url: str | None
        :param path: Путь к файлу видео.
        :type path: str | None
        """
        self.file_name: str = ""
        if path:
            self.file_name = Path(path).name
        elif url:
            self.file_name = Path(url).name

        if not self.file_name:
            raise ValueError("Either url or path must be provided.")
        super().__init__(raw=raw, url=url, path=path)

    @override
    async def read(self) -> bytes:
        """
        Читает содержимое видео.

        :return: Raw данные видео.
        :rtype: bytes
        """
        return await super().read()


class File(BaseFile):
    """
    Класс для работы с файлами (документы).
    """

    def __init__(self, raw: bytes | None = None, *, url: str | None = None, path: str | None = None) -> None:
        """
        Инициализирует файл.

        :param raw: Raw данные файла.
        :type raw: bytes | None
        :param url: URL для загрузки файла.
        :type url: str | None
        :param path: Путь к файлу.
        :type path: str | None
        """
        self.file_name: str = ""
        if path:
            self.file_name = Path(path).name
        elif url:
            self.file_name = Path(url).name

        if not self.file_name:
            raise ValueError("Either url or path must be provided.")

        super().__init__(raw=raw, url=url, path=path)

    @override
    async def read(self) -> bytes:
        """
        Читает содержимое файла.

        :return: Raw данные файла.
        :rtype: bytes
        """
        return await super().read()
