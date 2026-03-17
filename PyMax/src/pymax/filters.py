# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from PyMax.src.pymax.static.enum import MessageStatus, AttachType
from PyMax.src.pymax.types import Message

T_co = TypeVar("T_co")


class BaseFilter(ABC, Generic[T_co]):
    event_type: type[T_co]

    @abstractmethod
    def __call__(self, event: T_co) -> bool: ...

    def __and__(self, other: BaseFilter[T_co]) -> BaseFilter[T_co]:
        return AndFilter(self, other)

    def __or__(self, other: BaseFilter[T_co]) -> BaseFilter[T_co]:
        return OrFilter(self, other)

    def __invert__(self) -> BaseFilter[T_co]:
        return NotFilter(self)


class AndFilter(BaseFilter[T_co]):
    def __init__(self, *filters: BaseFilter[T_co]) -> None:
        self.filters = filters
        self.event_type = filters[0].event_type

    def __call__(self, event: T_co) -> bool:
        return all(f(event) for f in self.filters)


class OrFilter(BaseFilter[T_co]):
    def __init__(self, *filters: BaseFilter[T_co]) -> None:
        self.filters = filters
        self.event_type = filters[0].event_type

    def __call__(self, event: T_co) -> bool:
        return any(f(event) for f in self.filters)


class NotFilter(BaseFilter[T_co]):
    def __init__(self, base_filter: BaseFilter[T_co]) -> None:
        self.base_filter = base_filter
        self.event_type = base_filter.event_type

    def __call__(self, event: T_co) -> bool:
        return not self.base_filter(event)


class ChatFilter(BaseFilter[Message]):
    event_type = Message

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id

    def __call__(self, message: Message) -> bool:
        return message.chat_id == self.chat_id


class TextFilter(BaseFilter[Message]):
    event_type = Message

    def __init__(self, text: str) -> None:
        self.text = text

    def __call__(self, message: Message) -> bool:
        return self.text in message.text


class SenderFilter(BaseFilter[Message]):
    event_type = Message

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    def __call__(self, message: Message) -> bool:
        return message.sender == self.user_id


class StatusFilter(BaseFilter[Message]):
    event_type = Message

    def __init__(self, status: MessageStatus) -> None:
        self.status = status

    def __call__(self, message: Message) -> bool:
        return message.status == self.status


class TextContainsFilter(BaseFilter[Message]):
    event_type = Message

    def __init__(self, substring: str) -> None:
        self.substring = substring

    def __call__(self, message: Message) -> bool:
        return self.substring in message.text


class RegexTextFilter(BaseFilter[Message]):
    """
    Фильтр сообщений по регулярному выражению.

    Позволяет фильтровать входящие сообщения, проверяя, соответствует ли текст
    сообщения заданному регулярному выражению.

    Наследуется от BaseFilter и работает с событиями типа Message.
    """
    event_type = Message

    def __init__(self, pattern: str) -> None:
        """
        Инициализирует фильтр с заданным регулярным выражением.

        :param pattern: Строка с регулярным выражением для поиска в тексте сообщения.
        :type pattern: str
        """
        self.pattern = pattern
        self.regex = re.compile(pattern)

    def __call__(self, message: Message) -> bool:
        return bool(self.regex.search(message.text))


class MediaFilter(BaseFilter[Message]):
    """
    Фильтр для сообщений, содержащих медиавложения.

    Проверяет, есть ли в сообщении любые вложения (фото, видео, файлы и т.д.).
    Возвращает True, если список вложений существует и не пустой.

    Наследуется от BaseFilter и работает с событиями типа Message.
    """
    event_type = Message

    def __call__(self, message: Message) -> bool:
        """
        Проверяет, содержит ли сообщение медиавложения.

        :param message: Объект сообщения для проверки.
        :type message: Message
        :return: True, если в сообщении есть вложения, иначе False.
        :rtype: bool
        """
        return message.attaches is not None and len(message.attaches) > 0


class FileFilter(BaseFilter[Message]):
    """
    Фильтр для сообщений, содержащих файловые вложения.

    Проверяет, есть ли в сообщении вложения типа FILE.
    Возвращает True, если хотя бы одно вложение является файлом.

    Наследуется от BaseFilter и работает с событиями типа Message.
    """
    event_type = Message

    def __call__(self, message: Message) -> bool:
        """
        Проверяет, содержит ли сообщение файловые вложения.

        :param message: Объект сообщения для проверки.
        :type message: Message
        :return: True, если в сообщении есть вложение типа FILE, иначе False.
        :rtype: bool
        """
        if message.attaches is None:
            return False
        return any(attach.type == AttachType.FILE for attach in message.attaches)


class Filters:
    """
    Фабричный класс для создания предопределённых фильтров сообщений.

    Предоставляет статические методы для удобного создания различных фильтров,
    таких как фильтрация по чату, тексту, отправителю, статусу и типу вложений.
    """

    @staticmethod
    def chat(chat_id: int) -> BaseFilter[Message]:
        """
        Создаёт фильтр по идентификатору чата.

        :param chat_id: ID чата, для которого нужно фильтровать сообщения.
        :type chat_id: int
        :return: Фильтр, пропускающий сообщения из указанного чата.
        :rtype: BaseFilter[Message]
        """
        return ChatFilter(chat_id)

    @staticmethod
    def text(text: str) -> BaseFilter[Message]:
        """
        Создаёт фильтр по точному совпадению текста сообщения.

        :param text: Текст, который должен полностью содержаться в сообщении.
        :type text: str
        :return: Фильтр, пропускающий сообщения с указанным текстом.
        :rtype: BaseFilter[Message]
        """
        return TextFilter(text)

    @staticmethod
    def sender(user_id: int) -> BaseFilter[Message]:
        """
        Создаёт фильтр по отправителю сообщения.

        :param user_id: ID пользователя, который должен быть отправителем.
        :type user_id: int
        :return: Фильтр, пропускающий сообщения от указанного пользователя.
        :rtype: BaseFilter[Message]
        """
        return SenderFilter(user_id)

    @staticmethod
    def status(status: MessageStatus) -> BaseFilter[Message]:
        """
        Создаёт фильтр по статусу сообщения.

        :param status: Статус сообщения (например, EDITED, REMOVED).
        :type status: MessageStatus
        :return: Фильтр, пропускающий сообщения с указанным статусом.
        :rtype: BaseFilter[Message]
        """
        return StatusFilter(status)

    @staticmethod
    def text_contains(substring: str) -> BaseFilter[Message]:
        """
        Создаёт фильтр по наличию подстроки в тексте сообщения.

        :param substring: Подстрока, которую нужно искать в тексте.
        :type substring: str
        :return: Фильтр, пропускающий сообщения, содержащие указанную подстроку.
        :rtype: BaseFilter[Message]
        """
        return TextContainsFilter(substring)

    @staticmethod
    def text_matches(pattern: str) -> BaseFilter[Message]:
        """
        Создаёт фильтр по регулярному выражению для текста сообщения.

        :param pattern: Регулярное выражение для поиска в тексте.
        :type pattern: str
        :return: Фильтр, пропускающий сообщения, соответствующие регулярному выражению.
        :rtype: BaseFilter[Message]
        """
        return RegexTextFilter(pattern)

    @staticmethod
    def has_media() -> BaseFilter[Message]:
        """
        Создаёт фильтр для сообщений, содержащих любые вложения.

        :return: Фильтр, пропускающий сообщения с медиавложениями.
        :rtype: BaseFilter[Message]
        """
        return MediaFilter()

    @staticmethod
    def has_file() -> BaseFilter[Message]:
        """
        Создаёт фильтр для сообщений, содержащих файловые вложения.

        :return: Фильтр, пропускающий сообщения с вложениями типа FILE.
        :rtype: BaseFilter[Message]
        """
        return FileFilter()
