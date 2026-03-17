# -*- coding: utf-8 -*-
"""
Модуль API mixin для клиента Max.

Содержит методы для взаимодействия с сервером Max:
- Синхронизация данных (чаты, контакты, профиль)
- Отправка и получение сообщений
- Управление сессией

Этот файл является частью библиотеки PyMax.
"""
from __future__ import annotations

from loguru import logger

from PyMax.src.pymax.payloads import SyncPayload, UserAgentPayload
from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.enum import ChatType
from PyMax.src.pymax.static.enum import Opcode
from PyMax.src.pymax.types import Chat
from PyMax.src.pymax.types import Dialog, Channel, Me, User
from PyMax.src.pymax.utils import MixinsUtils


class ApiMixin(ClientProtocol):
    """
    Mixin для основных API-запросов к серверу Max.
    
    Наследуется от ClientProtocol и предоставляет реализацию
    методов для работы с сервером: синхронизация, отправка сообщений,
    получение данных о чатах и контактах.
    """

    async def _sync(self, user_agent: UserAgentPayload | None = None) -> None:
        """
        Выполняет начальную синхронизацию с сервером Max.
        
        Метод отправляет запрос на сервер для получения:
        - Списка чатов (диалоги, группы, каналы)
        - Списка контактов
        - Данных профиля текущего пользователя
        
        После успешной синхронизации данные сохраняются в соответствующие
        атрибуты клиента: self.dialogs, self.chats, self.channels,
        self.contacts, self.me.

        :param user_agent: Пользовательский агент для идентификации клиента.
                           Если не указан, используется self.headers или
                           создаётся новый UserAgentPayload.
        :type user_agent: UserAgentPayload | None
        :raises Exception: Если синхронизация не удалась.
        """

        logger.info("Начало начальной синхронизации")

        # Если user_agent не передан, используем заголовки клиента или создаём новый
        if user_agent is None:
            user_agent = self.headers or UserAgentPayload()

        # Формируем полезную нагрузку для запроса синхронизации
        payload = SyncPayload(
            interactive=True,  # Интерактивный режим (ожидание ответа)
            token=self._token,  # Токен авторизации
            chats_sync=0,  # Синхронизация чатов (0 = полная)
            contacts_sync=0,  # Синхронизация контактов (0 = полная)
            presence_sync=0,  # Синхронизация статусов присутствия
            drafts_sync=0,  # Синхронизация черновиков
            chats_count=40,  # Максимальное количество чатов для получения
            user_agent=user_agent,  # Информация о клиенте
        ).model_dump(by_alias=True)  # Преобразуем в словарь с правильными ключами

        try:
            # Отправляем запрос LOGIN и ждём ответ от сервера
            data = await self._send_and_wait(opcode=Opcode.LOGIN, payload=payload)
            raw_payload = data.get("payload", {})

            # Проверяем наличие ошибки в ответе сервера
            if error := raw_payload.get("error"):
                MixinsUtils.handle_error(data)

            # Обрабатываем полученные чаты
            for raw_chat in raw_payload.get("chats", []):
                try:
                    # Распределяем чаты по типам
                    if raw_chat.get("type") == ChatType.DIALOG.value:
                        # Личный диалог (один на один)
                        self.dialogs.append(Dialog.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHAT.value:
                        # Групповой чат
                        self.chats.append(Chat.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHANNEL.value:
                        # Канал (публичный или приватный)
                        self.channels.append(Channel.from_dict(raw_chat))
                except Exception as e:
                    # Логируем ошибку обработки отдельного чата, но продолжаем
                    logger.exception(e)

            # Обрабатываем полученные контакты
            for raw_user in raw_payload.get("contacts", []):
                try:
                    user = User.from_dict(raw_user)
                    if user:
                        self.contacts.append(user)
                except Exception as e:
                    # Логируем ошибку обработки отдельного контакта
                    logger.exception(e)

            # Сохраняем данные профиля текущего пользователя
            if raw_payload.get("profile", {}).get("contact"):
                self.me = Me.from_dict(raw_payload.get("profile", {}).get("contact", {}))

            # Логируем результат синхронизации
            logger.info(
                "Синхронизация завершена: dialogs=%d chats=%d channels=%d",
                len(self.dialogs),
                len(self.chats),
                len(self.channels),
            )

        except Exception as e:
            # Обработка ошибки синхронизации
            logger.exception("Синхронизация не получилась")
            # Устанавливаем флаг отключения
            self.is_connected = False
            # Закрываем WebSocket соединение если оно существует
            if self._ws:
                await self._ws.close()
            self._ws = None
            # Пробрасываем исключение дальше
            raise
