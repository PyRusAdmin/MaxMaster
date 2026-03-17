# -*- coding: utf-8 -*-
"""
Mixin для работы с группами.

Содержит GroupMixin для создания, управления группами и участниками.
"""
import time

from PyMax.src.pymax.exceptions import Error
from PyMax.src.pymax.payloads import (
    CreateGroupPayload, CreateGroupMessage, CreateGroupAttach, RemoveUsersPayload, ChangeGroupSettingsPayload,
    ChangeGroupSettingsOptions, ChangeGroupProfilePayload, InviteUsersPayload, ReworkInviteLinkPayload,
    GetChatInfoPayload, LeaveChatPayload, FetchChatsPayload, JoinChatPayload
)
from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.enum import Opcode
from PyMax.src.pymax.types import Message, Chat
from PyMax.src.pymax.utils import MixinsUtils


class GroupMixin(ClientProtocol):
    """
    Mixin, предоставляющий функциональность для работы с групповыми чатами.

    Содержит методы для создания групп, управления участниками, изменения настроек,
    обработки ссылок-приглашений и синхронизации состояния чатов.

    Attributes:
        chats (list[Chat]): Кэш чатов, доступных клиенту.
        _send_and_wait (callable): Асинхронный метод для отправки команд и ожидания ответа.
    """

    async def create_group(self, name: str, participant_ids: list[int] | None = None, notify: bool = True) -> tuple[
                                                                                                                  Chat, Message] | None:
        """
        Создает новую группу с указанными участниками.

        Метод формирует и отправляет payload для создания группы, ожидает ответ от сервера,
        обрабатывает возможные ошибки и обновляет локальный кэш чатов.

        Args:
            name (str): Название создаваемой группы.
            participant_ids (list[int] | None, optional): Список ID участников для добавления. По умолчанию — None.
            notify (bool, optional): Флаг, указывающий, нужно ли уведомлять участников. По умолчанию — True.

        Returns:
            tuple[Chat, Message] | None: Кортеж из объекта чата и сообщения о создании, или None при ошибке.

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Формируем payload для создания группы с уникальным cid
        payload = CreateGroupPayload(
            message=CreateGroupMessage(
                cid=int(time.time() * 1000),  # Уникальный идентификатор команды
                attaches=[
                    CreateGroupAttach(
                        _type="CONTROL",
                        title=name,
                        user_ids=(participant_ids if participant_ids else []),
                    )
                ],
            ),
            notify=notify,
        ).model_dump(by_alias=True)

        # Отправляем команду на сервер и ожидаем ответ
        data = await self._send_and_wait(opcode=Opcode.MSG_SEND, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата и сообщения из ответа
        chat = Chat.from_dict(data["payload"]["chat"])
        message = Message.from_dict(data["payload"])

        # Обновляем локальный кэш чатов
        if chat:
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)  # Добавляем новый чат в кэш
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat  # Обновляем существующий чат

        return chat, message

    async def invite_users_to_group(self, chat_id: int, user_ids: list[int], show_history: bool = True) -> Chat | None:
        """
        Приглашает пользователей в существующую группу.

        Отправляет запрос на добавление пользователей в группу, обновляет информацию о чате
        и синхронизирует её с локальным кэшем.

        Args:
            chat_id (int): Идентификатор группы.
            user_ids (list[int]): Список ID пользователей для приглашения.
            show_history (bool, optional): Разрешить ли новым участникам видеть историю чата. По умолчанию — True.

        Returns:
            Chat | None: Объект обновлённого чата или None при ошибке.

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Формируем payload для приглашения пользователей
        payload = InviteUsersPayload(
            chat_id=chat_id,
            user_ids=user_ids,
            show_history=show_history,
            operation="add",
        ).model_dump(by_alias=True)

        # Отправляем команду на обновление состава участников
        data = await self._send_and_wait(opcode=Opcode.CHAT_MEMBERS_UPDATE, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа
        chat = Chat.from_dict(data["payload"]["chat"])

        # Обновляем локальный кэш чатов
        if chat:
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

        return chat

    async def invite_users_to_channel(self, chat_id: int, user_ids: list[int],
                                      show_history: bool = True) -> Chat | None:
        """
        Приглашает пользователей в канал

        :param: chat_id (int): ID канала.
        :param: user_ids (list[int]): Список идентификаторов пользователей.
        :param: show_history (bool, optional): Флаг оповещения. Defaults to True.
        :return: Chat | None: Объект Chat или None при ошибке.
        """
        return await self.invite_users_to_group(chat_id, user_ids, show_history)

    async def remove_users_from_group(self, chat_id: int, user_ids: list[int], clean_msg_period: int) -> bool:
        """
        Удаляет пользователей из группы.

        Отправляет запрос на удаление участников, обновляет информацию о чате
        и синхронизирует её с локальным кэшем.

        Args:
            chat_id (int): Идентификатор группы.
            user_ids (list[int]): Список ID пользователей для удаления.
            clean_msg_period (int): Период очистки сообщений для удалённых пользователей (в секундах).

        Returns:
            bool: True, если удаление прошло успешно.

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Формируем payload для удаления пользователей
        payload = RemoveUsersPayload(
            chat_id=chat_id,
            user_ids=user_ids,
            clean_msg_period=clean_msg_period,
        ).model_dump(by_alias=True)

        # Отправляем команду на обновление состава участников
        data = await self._send_and_wait(opcode=Opcode.CHAT_MEMBERS_UPDATE, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа
        chat = Chat.from_dict(data["payload"]["chat"])

        # Обновляем локальный кэш чатов
        if chat:
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

        return True

    async def change_group_settings(
            self,
            chat_id: int,
            all_can_pin_message: bool | None = None,
            only_owner_can_change_icon_title: bool | None = None,
            only_admin_can_add_member: bool | None = None,
            only_admin_can_call: bool | None = None,
            members_can_see_private_link: bool | None = None,
    ) -> None:
        """
        Изменяет настройки приватности и поведения группы.

        Обновляет указанные параметры группы, отправляет запрос на сервер
        и синхронизирует обновлённый чат с локальным кэшем.

        Args:
            chat_id (int): Идентификатор группы.
            all_can_pin_message (bool | None, optional): Разрешить всем закреплять сообщения.
            only_owner_can_change_icon_title (bool | None, optional): Только владелец может менять название и иконку.
            only_admin_can_add_member (bool | None, optional): Только администраторы могут добавлять участников.
            only_admin_can_call (bool | None, optional): Только администраторы могут инициировать звонки.
            members_can_see_private_link (bool | None, optional): Участники могут видеть приватную ссылку-приглашение.

        Returns:
            None

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Формируем payload с новыми настройками группы
        payload = ChangeGroupSettingsPayload(
            chat_id=chat_id,
            options=ChangeGroupSettingsOptions(
                ALL_CAN_PIN_MESSAGE=all_can_pin_message,
                ONLY_OWNER_CAN_CHANGE_ICON_TITLE=only_owner_can_change_icon_title,
                ONLY_ADMIN_CAN_ADD_MEMBER=only_admin_can_add_member,
                ONLY_ADMIN_CAN_CALL=only_admin_can_call,
                MEMBERS_CAN_SEE_PRIVATE_LINK=members_can_see_private_link,
            ),
        ).model_dump(by_alias=True, exclude_none=True)

        # Отправляем команду на обновление настроек чата
        data = await self._send_and_wait(opcode=Opcode.CHAT_UPDATE, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа
        chat = Chat.from_dict(data["payload"]["chat"])

        # Обновляем локальный кэш чатов
        if chat:
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

    async def change_group_profile(self, chat_id: int, name: str | None, description: str | None = None) -> None:
        """
        Изменяет название и/или описание группы.

        Отправляет запрос на обновление профиля группы и синхронизирует
        обновлённые данные с локальным кэшем.

        Args:
            chat_id (int): Идентификатор группы.
            name (str | None): Новое название группы. Если None — не изменяется.
            description (str | None, optional): Новое описание группы. По умолчанию — None.

        Returns:
            None

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Формируем payload для изменения профиля группы
        payload = ChangeGroupProfilePayload(
            chat_id=chat_id,
            theme=name,
            description=description,
        ).model_dump(by_alias=True, exclude_none=True)

        # Отправляем команду на обновление профиля чата
        data = await self._send_and_wait(opcode=Opcode.CHAT_UPDATE, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа
        chat = Chat.from_dict(data["payload"]["chat"])

        # Обновляем локальный кэш чатов
        if chat:
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

    def _process_chat_join_link(self, link: str) -> str | None:
        """
        Извлекает часть ссылки, начинающуюся с 'join/', для использования в API.

        Args:
            link (str): Полная ссылка на группу.

        Returns:
            str | None: Обработанная часть ссылки или None, если 'join/' не найден.
        """
        # Находим индекс подстроки 'join/'
        idx = link.find("join/")
        # Возвращаем подстроку с этого индекса или None, если не найдено
        return link[idx:] if idx != -1 else None

    async def join_group(self, link: str) -> Chat:
        """
        Вступает в группу по ссылке-приглашению.

        Обрабатывает ссылку, отправляет запрос на вступление, проверяет ответ
        и обновляет локальный кэш чатов.

        Args:
            link (str): Полная ссылка на группу (например, https://example.com/join/abc123).

        Returns:
            Chat: Объект чата новой группы.

        Raises:
            ValueError: Если ссылка некорректна.
            Error: Если сервер вернул ошибку.
        """
        # Обрабатываем ссылку для извлечения части 'join/...'
        proceed_link = self._process_chat_join_link(link)
        if proceed_link is None:
            raise ValueError("Invalid group link")

        # Формируем payload для вступления в чат
        payload = JoinChatPayload(link=proceed_link).model_dump(by_alias=True)

        # Отправляем команду на вступление в чат
        data = await self._send_and_wait(opcode=Opcode.CHAT_JOIN, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа
        chat = Chat.from_dict(data["payload"]["chat"])

        # Обновляем локальный кэш чатов
        if chat:
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

        return chat

    async def resolve_group_by_link(self, link: str) -> Chat | None:
        """
        Получает информацию о группе по ссылке-приглашению без вступления.

        Полезно для предварительного просмотра группы перед вступлением.

        Args:
            link (str): Полная ссылка на группу.

        Returns:
            Chat | None: Объект чата группы или None, если группа не найдена или ссылка недействительна.

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Обрабатываем ссылку для извлечения части 'join/...'
        proceed_link = self._process_chat_join_link(link)
        if proceed_link is None:
            raise ValueError("Invalid group link")

        # Отправляем запрос на получение информации о ссылке
        data = await self._send_and_wait(
            opcode=Opcode.LINK_INFO,
            payload={
                "link": proceed_link,
            },
        )

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа, если они есть
        chat = Chat.from_dict(data["payload"].get("chat", {}))
        return chat

    async def rework_invite_link(self, chat_id: int) -> Chat:
        """
        Генерирует новую ссылку-приглашение для группы.

        Инвалидирует старую ссылку и возвращает чат с обновлённой ссылкой.

        Args:
            chat_id (int): Идентификатор группы.

        Returns:
            Chat: Обновлённый объект чата с новой ссылкой-приглашением.

        Raises:
            Error: Если сервер вернул ошибку или данные чата отсутствуют.
        """
        # Формируем payload для пересоздания ссылки-приглашения
        payload = ReworkInviteLinkPayload(chat_id=chat_id).model_dump(by_alias=True)

        # Отправляем команду на обновление чата
        data = await self._send_and_wait(opcode=Opcode.CHAT_UPDATE, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Преобразуем данные чата из ответа
        chat = Chat.from_dict(data["payload"].get("chat"))
        if not chat:
            raise Error("no_chat", "Chat data missing in response", "Chat Error")

        return chat

    async def get_chats(self, chat_ids: list[int]) -> list[Chat]:
        """
        Получает информацию о группах по их ID, используя локальный кэш и запросы к серверу.

        Реализует логику пагинации: сначала проверяет локальный кэш, затем запрашивает
        недостающие чаты с сервера и обновляет кэш.

        Args:
            chat_ids (list[int]): Список идентификаторов групп.

        Returns:
            list[Chat]: Список объектов Chat, соответствующих запрошенным ID.

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Определяем, какие чаты отсутствуют в локальном кэше
        missed_chat_ids = [
            chat_id for chat_id in chat_ids if await self._get_chat(chat_id) is None
        ]

        # Если все чаты уже в кэше, возвращаем их
        if not missed_chat_ids:
            chats: list[Chat] = [
                chat for chat_id in chat_ids if (chat := await self._get_chat(chat_id)) is not None
            ]
            return chats

        # Формируем payload для запроса недостающих чатов
        payload = GetChatInfoPayload(chat_ids=missed_chat_ids).model_dump(by_alias=True)

        # Отправляем запрос на получение информации о чатах
        data = await self._send_and_wait(opcode=Opcode.CHAT_INFO, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Обрабатываем полученные данные чатов
        chats_data = data["payload"].get("chats", [])
        chats: list[Chat] = []
        for chat_dict in chats_data:
            chat = Chat.from_dict(chat_dict)
            chats.append(chat)
            # Обновляем локальный кэш чатов
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

        return chats

    async def get_chat(self, chat_id: int) -> Chat:
        """
        Получает информацию о группе по её ID.

        Обёртка над get_chats для получения одного чата.

        Использует локальный кэш и при необходимости запрашивает данные с сервера.

        Args:
            chat_id (int): Идентификатор группы.

        Returns:
            Chat: Объект чата.

        Raises:
            Error: Если чат не найден в ответе сервера.
        """
        # Получаем список чатов (в данном случае — один)
        chats = await self.get_chats([chat_id])
        if not chats:
            raise Error("no_chat", "Chat not found in response", "Chat Error")
        return chats[0]

    async def leave_group(self, chat_id: int) -> None:
        """
        Покидает группу.

        Отправляет запрос на выход из группы и удаляет чат из локального кэша.

        Args:
            chat_id (int): Идентификатор группы.

        Returns:
            None

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Формируем payload для выхода из чата
        payload = LeaveChatPayload(chat_id=chat_id).model_dump(by_alias=True)

        # Отправляем команду на выход из чата
        data = await self._send_and_wait(opcode=Opcode.CHAT_LEAVE, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Удаляем чат из локального кэша, если он там был
        cached_chat = await self._get_chat(chat_id)
        if cached_chat is not None:
            self.chats.remove(cached_chat)

    async def leave_channel(self, chat_id: int) -> None:
        """
        Покидает канал

        :param chat_id: Идентификатор канала.
        :type chat_id: int
        :return: None
        :rtype: None
        """
        await self.leave_group(chat_id)

    async def fetch_chats(self, marker: int | None = None) -> list[Chat]:
        """
        Загружает список чатов с сервера с поддержкой пагинации.

        Использует маркер времени для получения чатов, созданных до указанного момента.
        Обновляет локальный кэш чатов полученными данными.

        Args:
            marker (int | None, optional): Маркер времени (timestamp * 1000) для пагинации.
                Если None — используется текущее время. По умолчанию — None.

        Returns:
            list[Chat]: Список объектов Chat, отсортированных по времени последнего обновления.

        Raises:
            Error: Если сервер вернул ошибку.
        """
        # Устанавливаем маркер по умолчанию (текущее время в миллисекундах)
        if marker is None:
            marker = int(time.time() * 1000)

        # Формируем payload для запроса списка чатов
        payload = FetchChatsPayload(marker=marker).model_dump(by_alias=True)

        # Отправляем запрос на получение списка чатов
        data = await self._send_and_wait(opcode=Opcode.CHATS_LIST, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Обрабатываем данные чатов из ответа
        chats_data = data["payload"].get("chats", [])
        chats: list[Chat] = []
        for chat_dict in chats_data:
            chat = Chat.from_dict(chat_dict)
            chats.append(chat)
            # Обновляем локальный кэш чатов
            cached_chat = await self._get_chat(chat.id)
            if cached_chat is None:
                self.chats.append(chat)
            else:
                idx = self.chats.index(cached_chat)
                self.chats[idx] = chat

        return chats
