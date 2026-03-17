# -*- coding: utf-8 -*-
"""
Mixin для работы с каналами.

Содержит ChannelMixin для управления каналами и участниками:
- Получение информации о канале по имени/ссылке
- Присоединение к каналу
- Загрузка списка участников
- Поиск участников по строке

Пример использования:
    channel = await client.resolve_channel_by_name("news")
    await client.join_channel("https://max.ru/join/abc123")
    members, marker = await client.load_members(channel.id)
"""
from PyMax.src.pymax.types import Channel, Member
from PyMax.src.pymax.exceptions import ResponseStructureError
from PyMax.src.pymax.payloads import (
    ResolveLinkPayload, JoinChatPayload, GetGroupMembersPayload, SearchGroupMembersPayload
)

from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.constant import DEFAULT_MARKER_VALUE, DEFAULT_CHAT_MEMBERS_LIMIT
from PyMax.src.pymax.static.enum import Opcode
from PyMax.src.pymax.utils import MixinsUtils


class ChannelMixin(ClientProtocol):
    """
    Mixin для работы с каналами.
    
    Наследуется от ClientProtocol и предоставляет методы для:
    - Поиска каналов по имени (через resolve ссылки)
    - Присоединения к каналам по ссылкам-приглашениям
    - Загрузки списка участников канала с пагинацией
    - Поиска участников по строке
    
    :cvar DEFAULT_MARKER_VALUE: Значение маркера по умолчанию для пагинации.
    :cvar DEFAULT_CHAT_MEMBERS_LIMIT: Лимит участников для загрузки по умолчанию.
    """
    
    async def resolve_channel_by_name(self, name: str) -> Channel | None:
        """
        Получает информацию о канале по его имени (через resolve ссылки).
        
        Метод преобразует имя канала в ссылку вида https://max.ru/{name}
        и запрашивает информацию о канале через API.
        Если канал найден, он автоматически добавляется в список self.channels.

        :param name: Имя канала (без @, например "news").
        :type name: str
        :return: Объект Channel с информацией о канале или None, если канал не найден.
        :rtype: Channel | None
        :raises ResponseStructureError: Если структура ответа некорректна.
        :raises Exception: Если сервер вернул ошибку.
        
        Пример:
            >>> channel = await client.resolve_channel_by_name("tech_news")
            >>> if channel:
            ...     print(f"Канал найден: {channel.title}")
        """
        # Формируем ссылку на канал и создаём payload
        payload = ResolveLinkPayload(link=f"https://max.ru/{name}", ).model_dump(by_alias=True)

        # Отправляем запрос на получение информации о ссылке
        data = await self._send_and_wait(opcode=Opcode.LINK_INFO, payload=payload)
        
        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Создаём объект Channel из данных ответа
        channel = Channel.from_dict(data.get("payload", {}).get("chat", {}))
        
        # Добавляем канал в список, если его там ещё нет
        if channel not in self.channels:
            self.channels.append(channel)
        
        return channel

    async def join_channel(self, link: str) -> Channel | None:
        """
        Присоединяется к каналу по ссылке-приглашению.
        
        Метод отправляет запрос на присоединение к каналу по указанной ссылке.
        Если присоединение успешно, канал добавляется в список self.channels.

        :param link: Ссылка-приглашение на канал (например, "https://max.ru/join/abc123").
        :type link: str
        :return: Объект канала, если присоединение прошло успешно, иначе None.
        :rtype: Channel | None
        :raises Exception: Если сервер вернул ошибку.
        
        Пример:
            >>> channel = await client.join_channel("https://max.ru/join/abc123xyz")
            >>> if channel:
            ...     print(f"Присоединился к каналу: {channel.title}")
        """
        # Создаём payload для присоединения к чату
        payload = JoinChatPayload(
            link=link,
        ).model_dump(by_alias=True)

        # Отправляем запрос на присоединение
        data = await self._send_and_wait(opcode=Opcode.CHAT_JOIN, payload=payload)
        
        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Создаём объект Channel из данных ответа
        channel = Channel.from_dict(data.get("payload", {}).get("chat", {}))
        
        # Добавляем канал в список, если его там ещё нет
        if channel not in self.channels:
            self.channels.append(channel)
        
        return channel

    async def _query_members(self, payload: GetGroupMembersPayload | SearchGroupMembersPayload) -> tuple[list[Member], int | None]:
        """
        Внутренний метод для запроса участников канала/чата.
        
        Отправляет запрос на получение списка участников и обрабатывает ответ.
        Используется методами load_members() и find_members().
        
        :param payload: Payload для запроса участников (GetGroupMembersPayload или SearchGroupMembersPayload).
        :type payload: GetGroupMembersPayload | SearchGroupMembersPayload
        :return: Кортеж из списка участников и маркера для следующей страницы (или None).
        :rtype: tuple[list[Member], int | None]
        :raises ResponseStructureError: Если структура ответа некорректна.
        :raises Exception: Если сервер вернул ошибку.
        """
        # Отправляем запрос на получение участников чата
        data = await self._send_and_wait(
            opcode=Opcode.CHAT_MEMBERS,
            payload=payload.model_dump(by_alias=True, exclude_none=True),  # Исключаем None значения
        )
        
        response_payload = data.get("payload", {})
        
        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)
        
        # Извлекаем маркер для пагинации
        marker = response_payload.get("marker")
        
        # Преобразуем маркер в int, если он в строковом формате
        if isinstance(marker, str):
            marker = int(marker)
        elif isinstance(marker, int):
            pass  # Оставляем как есть
        elif marker is None:
            # Маркер может отсутствовать, если это последняя страница
            pass
        else:
            raise ResponseStructureError("Invalid marker type in response")
        
        # Извлекаем список участников
        members = response_payload.get("members")
        member_list = []
        
        # Проверяем тип данных и создаём список объектов Member
        if isinstance(members, list):
            for item in members:
                if not isinstance(item, dict):
                    raise ResponseStructureError("Invalid member structure in response")
                member_list.append(Member.from_dict(item))
        else:
            raise ResponseStructureError("Invalid members type in response")
        
        return member_list, marker

    async def load_members(self, chat_id: int, marker: int | None = DEFAULT_MARKER_VALUE, count: int = DEFAULT_CHAT_MEMBERS_LIMIT,) -> tuple[list[Member], int | None]:
        """
        Загружает список участников канала/чата с поддержкой пагинации.
        
        Метод получает участников чата порциями (по умолчанию 100 человек).
        Для получения следующей порции используйте маркер из предыдущего ответа.
        
        :param chat_id: Идентификатор канала/чата.
        :type chat_id: int
        :param marker: Маркер для пагинации. По умолчанию DEFAULT_MARKER_VALUE (загрузка с начала).
                       Используйте маркер из предыдущего ответа для загрузки следующей страницы.
        :type marker: int | None, optional
        :param count: Количество участников для загрузки. По умолчанию DEFAULT_CHAT_MEMBERS_LIMIT (100).
        :type count: int, optional
        :return: Кортеж из списка участников и маркера для следующей страницы (или None, если это последняя страница).
        :rtype: tuple[list[Member], int | None]
        :raises ResponseStructureError: Если структура ответа некорректна.
        
        Пример:
            >>> # Загрузка первой страницы
            >>> members, marker = await client.load_members(chat_id=12345)
            >>> print(f"Загружено {len(members)} участников")
            >>> # Загрузка следующей страницы
            >>> if marker:
            ...     next_members, next_marker = await client.load_members(chat_id=12345, marker=marker)
        """
        # Создаём payload для получения участников
        payload = GetGroupMembersPayload(chat_id=chat_id, marker=marker, count=count)
        
        # Вызываем внутренний метод для запроса
        return await self._query_members(payload)

    async def find_members(self, chat_id: int, query: str) -> tuple[list[Member], int | None]:
        """
        Поиск участников канала/чата по строке (имя, фамилия).
        
        Метод выполняет поиск участников по заданной строке.
        Возвращает участников, чьи имена содержат искомую строку.
        
        .. warning::
            Веб-клиент всегда возвращает только определённое количество пользователей.
            Пагинация для поиска не реализована!

        :param chat_id: Идентификатор канала/чата.
        :type chat_id: int
        :param query: Строка для поиска участников (часть имени или фамилии).
        :type query: str
        :return: Кортеж из списка участников и маркера (всегда None для поиска).
        :rtype: tuple[list[Member], int | None]
        :raises ResponseStructureError: Если структура ответа некорректна.
        
        Пример:
            >>> # Поиск участников с "alex" в имени
            >>> members, _ = await client.find_members(chat_id=12345, query="alex")
            >>> for member in members:
            ...     print(f"Найден: {member.contact.names[0].name}")
        """
        # Создаём payload для поиска участников
        payload = SearchGroupMembersPayload(chat_id=chat_id, query=query)
        
        # Вызываем внутренний метод для запроса
        return await self._query_members(payload)
