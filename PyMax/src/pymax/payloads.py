# -*- coding: utf-8 -*-
"""
Модели данных (payloads) для API запросов к серверу Max.

Содержит классы для сериализации данных, отправляемых через WebSocket:
- Базовые сообщения протокола (BaseWebSocketMessage)
- Заголовки пользователя (UserAgentPayload)
- Авторизация (RequestCodePayload, SendCodePayload)
- Синхронизация (SyncPayload)
- Сообщения (SendMessagePayload, EditMessagePayload, DeleteMessagePayload)
- Чаты и группы (CreateGroupPayload, InviteUsersPayload, etc.)
- Файлы и медиа (UploadPayload, AttachPhotoPayload, etc.)
- Навигация и телеметрия (NavigationPayload)
- Реакции (AddReactionPayload, GetReactionsPayload)
- Папки (CreateFolderPayload, UpdateFolderPayload)
- Двухфакторная аутентификация (SetTwoFactorPayload)

Все классы наследуются от CamelModel для автоматического преобразования
имён полей из snake_case в camelCase.
"""
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field

from PyMax.src.pymax.static.constant import (
    DEFAULT_DEVICE_TYPE, DEFAULT_LOCALE, DEFAULT_DEVICE_LOCALE, DEFAULT_OS_VERSION, DEFAULT_DEVICE_NAME,
    DEFAULT_USER_AGENT, DEFAULT_APP_VERSION, DEFAULT_SCREEN, DEFAULT_TIMEZONE, DEFAULT_CLIENT_SESSION_ID,
    DEFAULT_BUILD_NUMBER
)
from PyMax.src.pymax.static.enum import AuthType, AttachType, ContactAction, ReadAction, Capability


def to_camel(string: str) -> str:
    """
    Преобразует строку из snake_case в camelCase.
    
    Используется alias_generator для моделей Pydantic.

    :param string: Строка в snake_case.
    :type string: str
    :return: Строка в camelCase.
    :rtype: str
    
    Пример:
        >>> to_camel("device_type")
        'deviceType'
    """
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """
    Базовая модель для payload с автоматическим преобразованием имён полей в camelCase.
    
    Использует alias_generator для автоматического преобразования имён полей
    из snake_case (Python стиль) в camelCase (стиль JSON API Max).
    """
    model_config = {
        "alias_generator": to_camel,  # Автоматическое преобразование имён полей
        "populate_by_name": True,  # Разрешить использование как имени, так и алиаса
        "arbitrary_types_allowed": True,  # Разрешить произвольные типы
    }


class BaseWebSocketMessage(BaseModel):
    """
    Базовое сообщение WebSocket протокола Max.
    
    Используется для отправки и получения сообщений через WebSocket.
    Все сообщения протокола имеют эту структуру.

    :ivar ver: Версия протокола (10 или 11).
    :ivar cmd: Команда сообщения.
    :ivar seq: Порядковый номер сообщения (sequence number).
    :ivar opcode: Код операции (тип запроса/ответа).
    :ivar payload: Полезная нагрузка сообщения (данные).
    """
    ver: Literal[10, 11] = 11
    cmd: int
    seq: int
    opcode: int
    payload: dict[str, Any]


class UserAgentPayload(CamelModel):
    """
    Заголовки пользователя для подключения к WebSocket.
    
    Содержит информацию о клиенте: тип устройства, версию приложения,
    локаль, часовой пояс и другие параметры для идентификации клиента.

    :ivar device_type: Тип устройства (WEB, ANDROID, IOS, DESKTOP).
    :ivar locale: Локаль приложения (например, 'ru').
    :ivar device_locale: Локаль устройства.
    :ivar os_version: Версия операционной системы.
    :ivar device_name: Имя устройства.
    :ivar header_user_agent: User Agent строка браузера/клиента.
    :ivar app_version: Версия приложения.
    :ivar screen: Разрешение экрана (например, '1920x1080').
    :ivar timezone: Часовой пояс (например, 'Europe/Moscow').
    :ivar client_session_id: ID клиентской сессии.
    :ivar build_number: Номер сборки приложения.
    """
    device_type: str = Field(default=DEFAULT_DEVICE_TYPE)
    locale: str = Field(default=DEFAULT_LOCALE)
    device_locale: str = Field(default=DEFAULT_DEVICE_LOCALE)
    os_version: str = Field(default=DEFAULT_OS_VERSION)
    device_name: str = Field(default=DEFAULT_DEVICE_NAME)
    header_user_agent: str = Field(default=DEFAULT_USER_AGENT)
    app_version: str = Field(default=DEFAULT_APP_VERSION)
    screen: str = Field(default=DEFAULT_SCREEN)
    timezone: str = Field(default=DEFAULT_TIMEZONE)
    client_session_id: int = Field(default=DEFAULT_CLIENT_SESSION_ID)
    build_number: int = Field(default=DEFAULT_BUILD_NUMBER)


class RequestCodePayload(CamelModel):
    """
    Payload для запроса кода подтверждения по номеру телефона.
    
    Используется на первом этапе авторизации для отправки SMS
    или push-уведомления с кодом подтверждения.

    :ivar phone: Номер телефона (например, '79991234567').
    :ivar type: Тип аутентификации (по умолчанию START_AUTH).
    :ivar language: Язык для сообщений (по умолчанию 'ru').
    """
    phone: str
    type: AuthType = AuthType.START_AUTH
    language: str = "ru"


class SendCodePayload(CamelModel):
    """
    Payload для отправки кода подтверждения.
    
    Используется на втором этапе авторизации для проверки кода,
    полученного пользователем через SMS или push.

    :ivar token: Временный токен, полученный из request_code.
    :ivar verify_code: Код верификации (6 цифр).
    :ivar auth_token_type: Тип аутентификации (по умолчанию CHECK_CODE).
    """
    token: str
    verify_code: str
    auth_token_type: AuthType = AuthType.CHECK_CODE


class SyncPayload(CamelModel):
    """
    Payload для синхронизации данных с сервером.
    
    Используется при начальном подключении для получения:
    - Списка чатов
    - Списка контактов
    - Статусов присутствия
    - Черновиков сообщений

    :ivar interactive: Флаг интерактивного режима (ожидание ответа).
    :ivar token: Токен авторизации.
    :ivar chats_sync: Флаг синхронизации чатов (0 = полная синхронизация).
    :ivar contacts_sync: Флаг синхронизации контактов (0 = полная).
    :ivar presence_sync: Флаг синхронизации присутствия.
    :ivar drafts_sync: Флаг синхронизации черновиков.
    :ivar chats_count: Количество чатов для синхронизации (по умолчанию 40).
    :ivar user_agent: Заголовки пользователя.
    """
    interactive: bool = True
    token: str
    chats_sync: int = 0
    contacts_sync: int = 0
    presence_sync: int = 0
    drafts_sync: int = 0
    chats_count: int = 40
    user_agent: UserAgentPayload = Field(
        default_factory=lambda: UserAgentPayload(
            device_type=DEFAULT_DEVICE_TYPE,
            locale=DEFAULT_LOCALE,
            device_locale=DEFAULT_DEVICE_LOCALE,
            os_version=DEFAULT_OS_VERSION,
            device_name=DEFAULT_DEVICE_NAME,
            header_user_agent=DEFAULT_USER_AGENT,
            app_version=DEFAULT_APP_VERSION,
            screen=DEFAULT_SCREEN,
            timezone=DEFAULT_TIMEZONE,
            client_session_id=DEFAULT_CLIENT_SESSION_ID,
            build_number=DEFAULT_BUILD_NUMBER,
        ),
    )


class ReplyLink(CamelModel):
    """
    Ссылка для ответа на сообщение.
    
    Используется для создания ответа на конкретное сообщение в чате.

    :ivar type: Тип ссылки (по умолчанию 'REPLY').
    :ivar message_id: ID сообщения, на которое отвечаем.
    """
    type: str = "REPLY"
    message_id: str


class UploadPayload(CamelModel):
    """
    Payload для загрузки файлов на сервер.
    
    Используется для получения URL для загрузки файлов (фото, видео, документы).

    :ivar count: Количество файлов для загрузки.
    :ivar profile: Флаг загрузки фото профиля (True для аватара).
    """
    count: int = 1
    profile: bool = False


class AttachPhotoPayload(CamelModel):
    """
    Payload для прикрепления фотографии к сообщению.
    
    Используется при отправке сообщений с фото.

    :ivar type: Тип вложения (PHOTO).
    :ivar photo_token: Токен фотографии, полученный после загрузки.
    """
    type: AttachType = Field(default=AttachType.PHOTO, alias="_type")
    photo_token: str


class VideoAttachPayload(CamelModel):
    """
    Payload для прикрепления видео к сообщению.
    
    Используется при отправке сообщений с видео.

    :ivar type: Тип вложения (VIDEO).
    :ivar video_id: ID видео.
    :ivar token: Токен видео.
    """
    type: AttachType = Field(default=AttachType.VIDEO, alias="_type")
    video_id: int
    token: str


class AttachFilePayload(CamelModel):
    """
    Payload для прикрепления файла к сообщению.
    
    Используется при отправке сообщений с документами.

    :ivar type: Тип вложения (FILE).
    :ivar file_id: ID файла.
    """
    type: AttachType = Field(default=AttachType.FILE, alias="_type")
    file_id: int


class MessageElement(CamelModel):
    """
    Элемент сообщения (для форматирования текста).
    
    Используется для выделения жирного, курсива, ссылок и т.д.
    в тексте сообщения.

    :ivar type: Тип элемента (bold, italic, link, etc.).
    :ivar from_: Позиция начала элемента в тексте.
    :ivar length: Длина элемента (количество символов).
    """
    type: str
    from_: int = Field(..., alias="from")
    length: int


class SendMessagePayloadMessage(CamelModel):
    """
    Сообщение для отправки.
    
    Содержит текст, вложения и элементы форматирования.

    :ivar text: Текст сообщения.
    :ivar cid: ID чата для отправки.
    :ivar elements: Элементы форматирования текста.
    :ivar attaches: Вложения (фото, видео, файлы).
    :ivar link: Ссылка для ответа на другое сообщение.
    """
    text: str
    cid: int
    elements: list[MessageElement]
    attaches: list[AttachPhotoPayload | AttachFilePayload | VideoAttachPayload]
    link: ReplyLink | None = None


class SendMessagePayload(CamelModel):
    """
    Payload для отправки сообщения.
    
    Используется для отправки текстовых сообщений с вложениями.

    :ivar chat_id: ID чата для отправки.
    :ivar message: Объект сообщения.
    :ivar notify: Флаг отправки уведомления (по умолчанию False).
    """
    chat_id: int
    message: SendMessagePayloadMessage
    notify: bool = False


class EditMessagePayload(CamelModel):
    """
    Payload для редактирования сообщения.
    
    Используется для изменения текста и вложений уже отправленного сообщения.

    :ivar chat_id: ID чата.
    :ivar message_id: ID редактируемого сообщения.
    :ivar text: Новый текст сообщения.
    :ivar elements: Элементы форматирования.
    :ivar attaches: Вложения.
    """
    chat_id: int
    message_id: int
    text: str
    elements: list[MessageElement]
    attaches: list[AttachPhotoPayload | AttachFilePayload | VideoAttachPayload]


class DeleteMessagePayload(CamelModel):
    """
    Payload для удаления сообщений.
    
    Используется для удаления одного или нескольких сообщений из чата.

    :ivar chat_id: ID чата.
    :ivar message_ids: Список ID сообщений для удаления.
    :ivar for_me: Флаг удаления только для себя (по умолчанию False).
    """
    chat_id: int
    message_ids: list[int]
    for_me: bool = False


class FetchContactsPayload(CamelModel):
    """
    Payload для получения информации о контактах.
    
    Используется для загрузки данных о пользователях по их ID.

    :ivar contact_ids: Список ID контактов для получения.
    """
    contact_ids: list[int]


class FetchHistoryPayload(CamelModel):
    """
    Payload для получения истории сообщений чата.
    
    Используется для загрузки предыдущих сообщений из чата.

    :ivar chat_id: ID чата.
    :ivar from_time: Время начала выборки (timestamp).
    :ivar forward: Количество сообщений вперёд.
    :ivar backward: Количество сообщений назад (по умолчанию 200).
    :ivar get_messages: Флаг получения сообщений (по умолчанию True).
    """
    chat_id: int
    from_time: int = Field(
        validation_alias=AliasChoices("from_time", "from"),
        serialization_alias="from",
    )
    forward: int
    backward: int = 200
    get_messages: bool = True


class ChangeProfilePayload(CamelModel):
    """
    Payload для изменения профиля пользователя.
    
    Используется для обновления имени, фамилии, описания и аватара.

    :ivar first_name: Имя пользователя.
    :ivar last_name: Фамилия пользователя.
    :ivar description: Описание профиля (статус).
    :ivar photo_token: Токен новой фотографии профиля.
    :ivar avatar_type: Тип аватара (по умолчанию 'USER_AVATAR').
    """
    first_name: str
    last_name: str | None = None
    description: str | None = None
    photo_token: str | None = None
    avatar_type: str = "USER_AVATAR"


class ResolveLinkPayload(CamelModel):
    """
    Payload для разрешения ссылки (например, приглашение в чат).
    
    Используется для получения информации о ссылке-приглашении
    и возможности присоединиться к чату.

    :ivar link: Ссылка для разрешения.
    """
    link: str


class PinMessagePayload(CamelModel):
    """
    Payload для закрепления сообщения в чате.
    
    Используется для закрепления важных сообщений вверху чата.

    :ivar chat_id: ID чата.
    :ivar notify_pin: Флаг уведомления о закреплении.
    :ivar pin_message_id: ID закрепляемого сообщения.
    """
    chat_id: int
    notify_pin: bool
    pin_message_id: int


class CreateGroupAttach(CamelModel):
    """
    Вложение для создания группы.
    
    Содержит данные для создания нового группового чата.

    :ivar type: Тип вложения (CONTROL).
    :ivar event: Событие (по умолчанию 'new' - создание).
    :ivar chat_type: Тип чата (по умолчанию 'CHAT').
    :ivar title: Название группы.
    :ivar user_ids: Список ID пользователей для добавления.
    """
    type: Literal["CONTROL"] = Field("CONTROL", alias="_type")
    event: str = "new"
    chat_type: str = "CHAT"
    title: str
    user_ids: list[int]


class CreateGroupMessage(CamelModel):
    """
    Сообщение для создания группы.
    
    Используется как часть запроса на создание группового чата.

    :ivar cid: ID чата (0 для нового чата).
    :ivar attaches: Вложения с данными группы.
    """
    cid: int
    attaches: list[CreateGroupAttach]


class CreateGroupPayload(CamelModel):
    """
    Payload для создания группы.
    
    Используется для создания нового группового чата с участниками.

    :ivar message: Сообщение с данными группы.
    :ivar notify: Флаг отправки уведомления участникам (по умолчанию True).
    """
    message: CreateGroupMessage
    notify: bool = True


class InviteUsersPayload(CamelModel):
    """
    Payload для приглашения пользователей в чат.
    
    Используется для добавления новых участников в существующий чат.

    :ivar chat_id: ID чата.
    :ivar user_ids: Список ID пользователей для приглашения.
    :ivar show_history: Флаг показа истории новым участникам.
    :ivar operation: Операция (по умолчанию 'add').
    """
    chat_id: int
    user_ids: list[int]
    show_history: bool
    operation: str = "add"


class RemoveUsersPayload(CamelModel):
    """
    Payload для удаления пользователей из чата.
    
    Используется для исключения участников из группового чата.

    :ivar chat_id: ID чата.
    :ivar user_ids: Список ID пользователей для удаления.
    :ivar operation: Операция (по умолчанию 'remove').
    :ivar clean_msg_period: Период очистки сообщений (в секундах).
    """
    chat_id: int
    user_ids: list[int]
    operation: str = "remove"
    clean_msg_period: int


class ChangeGroupSettingsOptions(BaseModel):
    """
    Опции для изменения настроек группы.
    
    Используется для управления правами участников группы.

    :ivar ONLY_OWNER_CAN_CHANGE_ICON_TITLE: Только владелец может менять иконку и название.
    :ivar ALL_CAN_PIN_MESSAGE: Все участники могут закреплять сообщения.
    :ivar ONLY_ADMIN_CAN_ADD_MEMBER: Только админы могут добавлять участников.
    :ivar ONLY_ADMIN_CAN_CALL: Только админы могут создавать звонки.
    :ivar MEMBERS_CAN_SEE_PRIVATE_LINK: Участники видят приватную ссылку-приглашение.
    """
    ONLY_OWNER_CAN_CHANGE_ICON_TITLE: bool | None
    ALL_CAN_PIN_MESSAGE: bool | None
    ONLY_ADMIN_CAN_ADD_MEMBER: bool | None
    ONLY_ADMIN_CAN_CALL: bool | None
    MEMBERS_CAN_SEE_PRIVATE_LINK: bool | None


class ChangeGroupSettingsPayload(CamelModel):
    """
    Payload для изменения настроек группы.
    
    Используется для обновления прав и настроек группового чата.

    :ivar chat_id: ID чата.
    :ivar options: Опции настроек группы.
    """
    chat_id: int
    options: ChangeGroupSettingsOptions


class ChangeGroupProfilePayload(CamelModel):
    """
    Payload для изменения профиля группы.
    
    Используется для обновления названия, описания и оформления группы.

    :ivar chat_id: ID чата.
    :ivar theme: Тема оформления группы.
    :ivar description: Описание группы.
    """
    chat_id: int
    theme: str | None
    description: str | None


class GetGroupMembersPayload(CamelModel):
    """
    Payload для получения участников группы.
    
    Используется для загрузки списка участников чата с пагинацией.

    :ivar type: Тип запроса (по умолчанию 'MEMBER').
    :ivar marker: Маркер для пагинации (ID последнего полученного участника).
    :ivar chat_id: ID чата.
    :ivar count: Количество участников для получения.
    """
    type: Literal["MEMBER"] = "MEMBER"
    marker: int | None = None
    chat_id: int
    count: int


class SearchGroupMembersPayload(CamelModel):
    """
    Payload для поиска участников группы.
    
    Используется для поиска участников по имени в групповом чате.

    :ivar type: Тип запроса (по умолчанию 'MEMBER').
    :ivar query: Строка поиска (часть имени).
    :ivar chat_id: ID чата.
    """
    type: Literal["MEMBER"] = "MEMBER"
    query: str
    chat_id: int


class NavigationEventParams(BaseModel):
    """
    Параметры события навигации.
    
    Используется для отслеживания переходов между экранами приложения.

    :ivar action_id: ID действия навигации.
    :ivar screen_to: Целевой экран (код экрана).
    :ivar screen_from: Исходный экран (код экрана).
    :ivar source_id: ID источника перехода.
    :ivar session_id: ID сессии навигации.
    """
    action_id: int
    screen_to: int
    screen_from: int | None = None
    source_id: int
    session_id: int


class NavigationEventPayload(CamelModel):
    """
    Событие навигации.
    
    Используется для отправки телеметрии о перемещениях пользователя
    по экранам приложения.

    :ivar event: Название события (например, 'screen_open').
    :ivar time: Время события (timestamp в миллисекундах).
    :ivar type: Тип события (по умолчанию 'NAV').
    :ivar user_id: ID пользователя.
    :ivar params: Параметры события навигации.
    """
    event: str
    time: int
    type: str = "NAV"
    user_id: int
    params: NavigationEventParams


class NavigationPayload(CamelModel):
    """
    Payload для отправки навигационных событий.
    
    Используется для пакетной отправки событий навигации на сервер.

    :ivar events: Список событий навигации.
    """
    events: list[NavigationEventPayload]


class GetVideoPayload(CamelModel):
    """
    Payload для получения видео.
    
    Используется для загрузки видео из сообщения.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения с видео.
    :ivar video_id: ID видео для загрузки.
    """
    chat_id: int
    message_id: int | str
    video_id: int


class GetFilePayload(CamelModel):
    """
    Payload для получения файла.
    
    Используется для загрузки файлов из сообщения.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения с файлом.
    :ivar file_id: ID файла для загрузки.
    """
    chat_id: int
    message_id: str | int
    file_id: int


class SearchByPhonePayload(CamelModel):
    """
    Payload для поиска пользователя по номеру телефона.
    
    Используется для поиска пользователя в мессенджере по его номеру.

    :ivar phone: Номер телефона для поиска.
    """
    phone: str


class JoinChatPayload(CamelModel):
    """
    Payload для присоединения к чату по ссылке.
    
    Используется для входа в чат по ссылке-приглашению.

    :ivar link: Ссылка-приглашение в чат.
    """
    link: str


class ReactionInfoPayload(CamelModel):
    """
    Информация о реакции.
    
    Используется для добавления реакции к сообщению.

    :ivar reaction_type: Тип реакции (по умолчанию 'EMOJI').
    :ivar id: ID реакции (например, код эмодзи).
    """
    reaction_type: str = "EMOJI"
    id: str


class AddReactionPayload(CamelModel):
    """
    Payload для добавления реакции к сообщению.
    
    Используется для отправки реакции (лайк, сердечко и т.д.)
    к сообщению в чате.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    :ivar reaction: Информация о реакции.
    """
    chat_id: int
    message_id: str
    reaction: ReactionInfoPayload


class GetReactionsPayload(CamelModel):
    """
    Payload для получения реакций.
    
    Используется для загрузки информации о реакциях
    к сообщениям в чате.

    :ivar chat_id: ID чата.
    :ivar message_ids: Список ID сообщений.
    """
    chat_id: int
    message_ids: list[str]


class RemoveReactionPayload(CamelModel):
    """
    Payload для удаления реакции.
    
    Используется для удаления своей реакции с сообщения.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    """
    chat_id: int
    message_id: str


class ReworkInviteLinkPayload(CamelModel):
    """
    Payload для перевыпуска ссылки-приглашения.
    
    Используется для отзыва старой и создания новой
    приватной ссылки для приглашения в чат.

    :ivar revoke_private_link: Флаг отзыва приватной ссылки (по умолчанию True).
    :ivar chat_id: ID чата.
    """
    revoke_private_link: bool = True
    chat_id: int


class ContactActionPayload(CamelModel):
    """
    Payload для действия с контактом.
    
    Используется для добавления или удаления контакта.

    :ivar contact_id: ID контакта.
    :ivar action: Действие (ContactAction: ADD или REMOVE).
    """
    contact_id: int
    action: ContactAction


class RegisterPayload(CamelModel):
    """
    Payload для регистрации пользователя.
    
    Используется для регистрации нового пользователя после
    успешной авторизации по номеру телефона.

    :ivar last_name: Фамилия пользователя.
    :ivar first_name: Имя пользователя.
    :ivar token: Токен авторизации.
    :ivar token_type: Тип токена (по умолчанию REGISTER).
    """
    last_name: str | None = None
    first_name: str
    token: str
    token_type: AuthType = AuthType.REGISTER


class CreateFolderPayload(CamelModel):
    """
    Payload для создания папки чатов.
    
    Используется для создания новой папки для группировки чатов.

    :ivar id: ID папки (уникальный идентификатор).
    :ivar title: Название папки.
    :ivar include: Список ID чатов для включения в папку.
    :ivar filters: Фильтры папки (по умолчанию пустой список).
    """
    id: str
    title: str
    include: list[int]
    filters: list[Any] = []


class GetChatInfoPayload(CamelModel):
    """
    Payload для получения информации о чатах.
    
    Используется для загрузки подробной информации о чатах.

    :ivar chat_ids: Список ID чатов для получения информации.
    """
    chat_ids: list[int]


class GetFolderPayload(CamelModel):
    """
    Payload для получения папок.
    
    Используется для синхронизации папок чатов.

    :ivar folder_sync: Флаг синхронизации папок (0 = полная синхронизация).
    """
    folder_sync: int = 0


class UpdateFolderPayload(CamelModel):
    """
    Payload для обновления папки.
    
    Используется для изменения существующей папки чатов.

    :ivar id: ID папки.
    :ivar title: Название папки.
    :ivar include: Список ID чатов в папке.
    :ivar filters: Фильтры папки.
    :ivar options: Опции папки.
    """
    id: str
    title: str
    include: list[int]
    filters: list[Any] = []
    options: list[Any] = []


class DeleteFolderPayload(CamelModel):
    """
    Payload для удаления папок.
    
    Используется для удаления одной или нескольких папок чатов.

    :ivar folder_ids: Список ID папок для удаления.
    """
    folder_ids: list[str]


class LeaveChatPayload(CamelModel):
    """
    Payload для выхода из чата.
    
    Используется для выхода из группового чата или канала.

    :ivar chat_id: ID чата.
    """
    chat_id: int


class FetchChatsPayload(CamelModel):
    """
    Payload для получения списка чатов.
    
    Используется для загрузки чатов с пагинацией.

    :ivar marker: Маркер для пагинации (ID последнего полученного чата).
    """
    marker: int


class ReadMessagesPayload(CamelModel):
    """
    Payload для отметки сообщений как прочитанных.
    
    Используется для отправки информации о прочтении сообщений.

    :ivar type: Тип действия (ReadAction: READ или DELIVER).
    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    :ivar mark: Метка прочтения.
    """
    type: ReadAction
    chat_id: int
    message_id: str
    mark: int


class CheckPasswordChallengePayload(CamelModel):
    """
    Payload для проверки парольного вызова.
    
    Используется для проверки пароля при двухфакторной аутентификации.

    :ivar track_id: ID трека аутентификации.
    :ivar password: Пароль пользователя.
    """
    track_id: str
    password: str


class CreateTrackPayload(CamelModel):
    """
    Payload для создания трека аутентификации.
    
    Используется для создания нового трека при настройке
    двухфакторной аутентификации.

    :ivar type: Тип трека (по умолчанию 0).
    """
    type: int = 0


class SetPasswordPayload(CamelModel):
    """
    Payload для установки пароля.
    
    Используется для установки пароля двухфакторной аутентификации.

    :ivar track_id: ID трека аутентификации.
    :ivar password: Пароль для установки.
    """
    track_id: str
    password: str


class SetHintPayload(CamelModel):
    """
    Payload для установки подсказки к паролю.
    
    Используется для добавления подсказки к паролю
    двухфакторной аутентификации.

    :ivar track_id: ID трека аутентификации.
    :ivar hint: Текст подсказки.
    """
    track_id: str
    hint: str


class SetTwoFactorPayload(CamelModel):
    """
    Payload для установки двухфакторной аутентификации.
    
    Используется для полной настройки 2FA: пароль, подсказка
    и ожидаемые возможности аккаунта.

    :ivar expected_capabilities: Список ожидаемых возможностей аккаунта.
    :ivar track_id: ID трека аутентификации.
    :ivar password: Пароль для установки.
    :ivar hint: Подсказка к паролю.
    """
    expected_capabilities: list[Capability]
    track_id: str
    password: str
    hint: str | None = None


class RequestEmailCodePayload(CamelModel):
    """
    Payload для запроса кода на email.
    
    Используется для отправки кода подтверждения на
    адрес электронной почты.

    :ivar track_id: ID трека аутентификации.
    :ivar email: Email адрес для отправки кода.
    """
    track_id: str
    email: str


class SendEmailCodePayload(CamelModel):
    """
    Payload для отправки кода подтверждения email.
    
    Используется для проверки кода, полученного на email.

    :ivar track_id: ID трека аутентификации.
    :ivar verify_code: Код верификации из email.
    """
    track_id: str
    verify_code: str
