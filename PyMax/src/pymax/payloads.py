# -*- coding: utf-8 -*-
"""
Модели данных (payloads) для API запросов к серверу Max.

Содержит классы для сериализации данных, отправляемых через WebSocket.
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

    :param string: Строка в snake_case.
    :type string: str
    :return: Строка в camelCase.
    :rtype: str
    """
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """
    Базовая модель для payload с автоматическим преобразованием имён полей в camelCase.
    """
    model_config = {
        "alias_generator": to_camel,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class BaseWebSocketMessage(BaseModel):
    """
    Базовое сообщение WebSocket протокола Max.

    :ivar ver: Версия протокола (10 или 11).
    :ivar cmd: Команда сообщения.
    :ivar seq: Порядковый номер сообщения.
    :ivar opcode: Код операции.
    :ivar payload: Полезная нагрузка сообщения.
    """
    ver: Literal[10, 11] = 11
    cmd: int
    seq: int
    opcode: int
    payload: dict[str, Any]


class UserAgentPayload(CamelModel):
    """
    Заголовки пользователя для подключения к WebSocket.

    :ivar device_type: Тип устройства (WEB, ANDROID, IOS, DESKTOP).
    :ivar locale: Локаль приложения.
    :ivar device_locale: Локаль устройства.
    :ivar os_version: Версия операционной системы.
    :ivar device_name: Имя устройства.
    :ivar header_user_agent: User Agent строка.
    :ivar app_version: Версия приложения.
    :ivar screen: Разрешение экрана.
    :ivar timezone: Часовой пояс.
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

    :ivar phone: Номер телефона.
    :ivar type: Тип аутентификации.
    :ivar language: Язык для сообщений (по умолчанию 'ru').
    """
    phone: str
    type: AuthType = AuthType.START_AUTH
    language: str = "ru"


class SendCodePayload(CamelModel):
    """
    Payload для отправки кода подтверждения.

    :ivar token: Временный токен.
    :ivar verify_code: Код верификации (6 цифр).
    :ivar auth_token_type: Тип аутентификации.
    """
    token: str
    verify_code: str
    auth_token_type: AuthType = AuthType.CHECK_CODE


class SyncPayload(CamelModel):
    """
    Payload для синхронизации данных с сервером.

    :ivar interactive: Флаг интерактивного режима.
    :ivar token: Токен авторизации.
    :ivar chats_sync: Флаг синхронизации чатов.
    :ivar contacts_sync: Флаг синхронизации контактов.
    :ivar presence_sync: Флаг синхронизации присутствия.
    :ivar drafts_sync: Флаг синхронизации черновиков.
    :ivar chats_count: Количество чатов для синхронизации.
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

    :ivar type: Тип ссылки (REPLY).
    :ivar message_id: ID сообщения, на которое отвечаем.
    """
    type: str = "REPLY"
    message_id: str


class UploadPayload(CamelModel):
    """
    Payload для загрузки файлов.

    :ivar count: Количество файлов.
    :ivar profile: Флаг загрузки фото профиля.
    """
    count: int = 1
    profile: bool = False


class AttachPhotoPayload(CamelModel):
    """
    Payload для прикрепления фотографии к сообщению.

    :ivar type: Тип вложения (PHOTO).
    :ivar photo_token: Токен фотографии.
    """
    type: AttachType = Field(default=AttachType.PHOTO, alias="_type")
    photo_token: str


class VideoAttachPayload(CamelModel):
    """
    Payload для прикрепления видео к сообщению.

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

    :ivar type: Тип вложения (FILE).
    :ivar file_id: ID файла.
    """
    type: AttachType = Field(default=AttachType.FILE, alias="_type")
    file_id: int


class MessageElement(CamelModel):
    """
    Элемент сообщения (для форматирования).

    :ivar type: Тип элемента.
    :ivar from_: Позиция начала элемента.
    :ivar length: Длина элемента.
    """
    type: str
    from_: int = Field(..., alias="from")
    length: int


class SendMessagePayloadMessage(CamelModel):
    """
    Сообщение для отправки.

    :ivar text: Текст сообщения.
    :ivar cid: ID чата.
    :ivar elements: Элементы форматирования.
    :ivar attaches: Вложения.
    :ivar link: Ссылка для ответа.
    """
    text: str
    cid: int
    elements: list[MessageElement]
    attaches: list[AttachPhotoPayload | AttachFilePayload | VideoAttachPayload]
    link: ReplyLink | None = None


class SendMessagePayload(CamelModel):
    """
    Payload для отправки сообщения.

    :ivar chat_id: ID чата.
    :ivar message: Сообщение.
    :ivar notify: Флаг отправки уведомления.
    """
    chat_id: int
    message: SendMessagePayloadMessage
    notify: bool = False


class EditMessagePayload(CamelModel):
    """
    Payload для редактирования сообщения.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    :ivar text: Новый текст.
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

    :ivar chat_id: ID чата.
    :ivar message_ids: Список ID сообщений для удаления.
    :ivar for_me: Флаг удаления только для себя.
    """
    chat_id: int
    message_ids: list[int]
    for_me: bool = False


class FetchContactsPayload(CamelModel):
    """
    Payload для получения контактов.

    :ivar contact_ids: Список ID контактов.
    """
    contact_ids: list[int]


class FetchHistoryPayload(CamelModel):
    """
    Payload для получения истории сообщений.

    :ivar chat_id: ID чата.
    :ivar from_time: Время начала выборки.
    :ivar forward: Направление вперёд.
    :ivar backward: Количество сообщений назад.
    :ivar get_messages: Флаг получения сообщений.
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

    :ivar first_name: Имя.
    :ivar last_name: Фамилия.
    :ivar description: Описание профиля.
    :ivar photo_token: Токен фотографии.
    :ivar avatar_type: Тип аватара.
    """
    first_name: str
    last_name: str | None = None
    description: str | None = None
    photo_token: str | None = None
    avatar_type: str = "USER_AVATAR"


class ResolveLinkPayload(CamelModel):
    """
    Payload для разрешения ссылки (например, приглашение в чат).

    :ivar link: Ссылка для разрешения.
    """
    link: str


class PinMessagePayload(CamelModel):
    """
    Payload для закрепления сообщения.

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

    :ivar type: Тип вложения (CONTROL).
    :ivar event: Событие (new).
    :ivar chat_type: Тип чата (CHAT).
    :ivar title: Название группы.
    :ivar user_ids: Список ID пользователей.
    """
    type: Literal["CONTROL"] = Field("CONTROL", alias="_type")
    event: str = "new"
    chat_type: str = "CHAT"
    title: str
    user_ids: list[int]


class CreateGroupMessage(CamelModel):
    """
    Сообщение для создания группы.

    :ivar cid: ID чата.
    :ivar attaches: Вложения.
    """
    cid: int
    attaches: list[CreateGroupAttach]


class CreateGroupPayload(CamelModel):
    """
    Payload для создания группы.

    :ivar message: Сообщение с данными группы.
    :ivar notify: Флаг отправки уведомления.
    """
    message: CreateGroupMessage
    notify: bool = True


class InviteUsersPayload(CamelModel):
    """
    Payload для приглаения пользователей в чат.

    :ivar chat_id: ID чата.
    :ivar user_ids: Список ID пользователей.
    :ivar show_history: Флаг показа истории.
    :ivar operation: Операция (add).
    """
    chat_id: int
    user_ids: list[int]
    show_history: bool
    operation: str = "add"


class RemoveUsersPayload(CamelModel):
    """
    Payload для удаления пользователей из чата.

    :ivar chat_id: ID чата.
    :ivar user_ids: Список ID пользователей.
    :ivar operation: Операция (remove).
    :ivar clean_msg_period: Период очистки сообщений.
    """
    chat_id: int
    user_ids: list[int]
    operation: str = "remove"
    clean_msg_period: int


class ChangeGroupSettingsOptions(BaseModel):
    """
    Опции для изменения настроек группы.

    :ivar ONLY_OWNER_CAN_CHANGE_ICON_TITLE: Только владелец может менять иконку и название.
    :ivar ALL_CAN_PIN_MESSAGE: Все могут закреплять сообщения.
    :ivar ONLY_ADMIN_CAN_ADD_MEMBER: Только админы могут добавлять участников.
    :ivar ONLY_ADMIN_CAN_CALL: Только админы могут звонить.
    :ivar MEMBERS_CAN_SEE_PRIVATE_LINK: Участники видят приватную ссылку.
    """
    ONLY_OWNER_CAN_CHANGE_ICON_TITLE: bool | None
    ALL_CAN_PIN_MESSAGE: bool | None
    ONLY_ADMIN_CAN_ADD_MEMBER: bool | None
    ONLY_ADMIN_CAN_CALL: bool | None
    MEMBERS_CAN_SEE_PRIVATE_LINK: bool | None


class ChangeGroupSettingsPayload(CamelModel):
    """
    Payload для изменения настроек группы.

    :ivar chat_id: ID чата.
    :ivar options: Опции настроек.
    """
    chat_id: int
    options: ChangeGroupSettingsOptions


class ChangeGroupProfilePayload(CamelModel):
    """
    Payload для изменения профиля группы.

    :ivar chat_id: ID чата.
    :ivar theme: Тема оформления.
    :ivar description: Описание группы.
    """
    chat_id: int
    theme: str | None
    description: str | None


class GetGroupMembersPayload(CamelModel):
    """
    Payload для получения участников группы.

    :ivar type: Тип запроса (MEMBER).
    :ivar marker: Маркер для пагинации.
    :ivar chat_id: ID чата.
    :ivar count: Количество участников.
    """
    type: Literal["MEMBER"] = "MEMBER"
    marker: int | None = None
    chat_id: int
    count: int


class SearchGroupMembersPayload(CamelModel):
    """
    Payload для поиска участников группы.

    :ivar type: Тип запроса (MEMBER).
    :ivar query: Строка поиска.
    :ivar chat_id: ID чата.
    """
    type: Literal["MEMBER"] = "MEMBER"
    query: str
    chat_id: int


class NavigationEventParams(BaseModel):
    """
    Параметры события навигации.

    :ivar action_id: ID действия.
    :ivar screen_to: Целевой экран.
    :ivar screen_from: Исходный экран.
    :ivar source_id: ID источника.
    :ivar session_id: ID сессии.
    """
    action_id: int
    screen_to: int
    screen_from: int | None = None
    source_id: int
    session_id: int


class NavigationEventPayload(CamelModel):
    """
    Событие навигации.

    :ivar event: Название события.
    :ivar time: Время события.
    :ivar type: Тип события (NAV).
    :ivar user_id: ID пользователя.
    :ivar params: Параметры события.
    """
    event: str
    time: int
    type: str = "NAV"
    user_id: int
    params: NavigationEventParams


class NavigationPayload(CamelModel):
    """
    Payload для отправки навигационных событий.

    :ivar events: Список событий навигации.
    """
    events: list[NavigationEventPayload]


class GetVideoPayload(CamelModel):
    """
    Payload для получения видео.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    :ivar video_id: ID видео.
    """
    chat_id: int
    message_id: int | str
    video_id: int


class GetFilePayload(CamelModel):
    """
    Payload для получения файла.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    :ivar file_id: ID файла.
    """
    chat_id: int
    message_id: str | int
    file_id: int


class SearchByPhonePayload(CamelModel):
    """
    Payload для поиска пользователя по номеру телефона.

    :ivar phone: Номер телефона для поиска.
    """
    phone: str


class JoinChatPayload(CamelModel):
    """
    Payload для присоединения к чату по ссылке.

    :ivar link: Ссылка-приглашение.
    """
    link: str


class ReactionInfoPayload(CamelModel):
    """
    Информация о реакции.

    :ivar reaction_type: Тип реакции (EMOJI).
    :ivar id: ID реакции.
    """
    reaction_type: str = "EMOJI"
    id: str


class AddReactionPayload(CamelModel):
    """
    Payload для добавления реакции к сообщению.

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

    :ivar chat_id: ID чата.
    :ivar message_ids: Список ID сообщений.
    """
    chat_id: int
    message_ids: list[str]


class RemoveReactionPayload(CamelModel):
    """
    Payload для удаления реакции.

    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    """
    chat_id: int
    message_id: str


class ReworkInviteLinkPayload(CamelModel):
    """
    Payload для перевыпуска ссылки-приглашения.

    :ivar revoke_private_link: Флаг отзыва приватной ссылки.
    :ivar chat_id: ID чата.
    """
    revoke_private_link: bool = True
    chat_id: int


class ContactActionPayload(CamelModel):
    """
    Payload для действия с контактом.

    :ivar contact_id: ID контакта.
    :ivar action: Действие (ContactAction).
    """
    contact_id: int
    action: ContactAction


class RegisterPayload(CamelModel):
    """
    Payload для регистрации пользователя.

    :ivar last_name: Фамилия.
    :ivar first_name: Имя.
    :ivar token: Токен авторизации.
    :ivar token_type: Тип токена.
    """
    last_name: str | None = None
    first_name: str
    token: str
    token_type: AuthType = AuthType.REGISTER


class CreateFolderPayload(CamelModel):
    """
    Payload для создания папки чатов.

    :ivar id: ID папки.
    :ivar title: Название папки.
    :ivar include: Список ID чатов.
    :ivar filters: Фильтры папки.
    """
    id: str
    title: str
    include: list[int]
    filters: list[Any] = []


class GetChatInfoPayload(CamelModel):
    """
    Payload для получения информации о чатах.

    :ivar chat_ids: Список ID чатов.
    """
    chat_ids: list[int]


class GetFolderPayload(CamelModel):
    """
    Payload для получения папки.

    :ivar folder_sync: Флаг синхронизации папок.
    """
    folder_sync: int = 0


class UpdateFolderPayload(CamelModel):
    """
    Payload для обновления папки.

    :ivar id: ID папки.
    :ivar title: Название папки.
    :ivar include: Список ID чатов.
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

    :ivar folder_ids: Список ID папок для удаления.
    """
    folder_ids: list[str]


class LeaveChatPayload(CamelModel):
    """
    Payload для выхода из чата.

    :ivar chat_id: ID чата.
    """
    chat_id: int


class FetchChatsPayload(CamelModel):
    """
    Payload для получения списка чатов.

    :ivar marker: Маркер для пагинации.
    """
    marker: int


class ReadMessagesPayload(CamelModel):
    """
    Payload для отметки сообщений как прочитанных.

    :ivar type: Тип действия (ReadAction).
    :ivar chat_id: ID чата.
    :ivar message_id: ID сообщения.
    :ivar mark: Метка.
    """
    type: ReadAction
    chat_id: int
    message_id: str
    mark: int


class CheckPasswordChallengePayload(CamelModel):
    """
    Payload для проверки парольного вызова.

    :ivar track_id: ID трека.
    :ivar password: Пароль.
    """
    track_id: str
    password: str


class CreateTrackPayload(CamelModel):
    """
    Payload для создания трека.

    :ivar type: Тип трека.
    """
    type: int = 0


class SetPasswordPayload(CamelModel):
    """
    Payload для установки пароля.

    :ivar track_id: ID трека.
    :ivar password: Пароль.
    """
    track_id: str
    password: str


class SetHintPayload(CamelModel):
    """
    Payload для установки подсказки к паролю.

    :ivar track_id: ID трека.
    :ivar hint: Подсказка.
    """
    track_id: str
    hint: str


class SetTwoFactorPayload(CamelModel):
    """
    Payload для установки двухфакторной аутентификации.

    :ivar expected_capabilities: Ожидаемые возможности.
    :ivar track_id: ID трека.
    :ivar password: Пароль.
    :ivar hint: Подсказка к паролю.
    """
    expected_capabilities: list[Capability]
    track_id: str
    password: str
    hint: str | None = None


class RequestEmailCodePayload(CamelModel):
    """
    Payload для запроса кода на email.

    :ivar track_id: ID трека.
    :ivar email: Email адрес.
    """
    track_id: str
    email: str


class SendEmailCodePayload(CamelModel):
    """
    Payload для отправки кода подтверждения email.

    :ivar track_id: ID трека.
    :ivar verify_code: Код верификации.
    """
    track_id: str
    verify_code: str
