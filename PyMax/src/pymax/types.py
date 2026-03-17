# -*- coding: utf-8 -*-
"""
Модуль типов данных для клиента Max API.

Содержит классы для представления данных, получаемых от сервера Max:
- Присутствие пользователей (Presence)
- Имена и контакты (Name, Names, Contact, User, Me)
- Чаты и диалоги (Chat, Dialog, Channel)
- Сообщения и вложения (Message,各种 Attach классы)
- Реакции (ReactionInfo, ReactionCounter)
- Папки (Folder, FolderList, FolderUpdate)

Все классы имеют метод from_dict() для десериализации из JSON.
"""
from typing import Any

from typing_extensions import Self, override

from PyMax.src.pymax.static.enum import AttachType, FormattingType, MessageStatus, MessageType, ChatType, AccessType


# TODO: все это нужно переделать на pydantic модели.
# Я просто придерживаюсь текущего стиля.
# - 6RUN0
# Хз, а в чем аргументация, так контроля больше и пайдентик модели явного преимущества не дают.
# - ink-developer


class Presence:
    """
    Присутствие пользователя в сети.
    
    Содержит информацию о времени последнего посещения пользователя.
    """

    def __init__(self, seen: int | None) -> None:
        """
        Инициализирует присутствие.

        :param seen: Unix timestamp последнего посещения.
        """
        # TODO надо сделать пребразование в datetime с учетом таймзоны
        self.seen = seen

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр Presence из словаря.
        
        :param data: Словарь с данными присутствия.
        :return: Новый экземпляр Presence.
        """
        return cls(seen=data.get("seen"))

    @override
    def __repr__(self) -> str:
        return f"Presence(seen={self.seen!r})"

    @override
    def __str__(self) -> str:
        return f"{self.seen}"


class Name:
    """
    Структура имени пользователя.
    
    Может содержать несколько вариантов имени (name, firstName, lastName)
    и тип имени (например, ONEME).
    """

    def __init__(self, name: str | None, first_name: None | str, last_name: str | None, type: str | None) -> None:
        """
        Инициализирует структуру имени.

        :param name: Полное имя.
        :param first_name: Имя.
        :param last_name: Фамилия.
        :param type: Тип имени (например, ONEME).
        """
        self.name = name
        self.first_name = first_name
        self.last_name = last_name
        self.type = type

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр Name из словаря.
        
        :param data: Словарь с данными имени.
        :return: Новый экземпляр Name.
        """
        return cls(
            name=data.get("name"),
            first_name=data.get("firstName"),
            last_name=data.get("lastName"),
            type=data.get("type"),
        )

    @override
    def __repr__(self) -> str:
        return f"Name(name={self.name!r}, first_name={self.first_name!r}, last_name={self.last_name!r}, type={self.type!r})"

    @override
    def __str__(self) -> str:
        return self.name or ""


class Names(Name):
    """
    Синоним для класса Name.
    
    Используется для обратной совместимости.
    """

    def __init__(self, name: str | None, first_name: None | str, last_name: str | None, type: str | None) -> None:
        """
        Инициализирует структуру имени (синоним Name).
        """
        super().__init__(name=name, first_name=first_name, last_name=last_name, type=type)


class Contact:
    def __init__(self, id: int | None, account_status: int | None, base_raw_url: str | None, base_url: str | None,
                 names: list[Name] | None, options: list[str] | None, photo_id: int | None,
                 update_time: int | None, ) -> None:
        """
        Контакт.

        Сруктура:
        {
            "accountStatus": 0,
            "baseUrl": "https://i.oneme.ru/i?r=...",
            "names": [
                Name{},
            ],
            "options": [
                "TT",
                "ONEME"
            ],
            "photoId": {{ file id }},
            "updateTime": 0,
            "id": {{ user id }},
            "baseRawUrl": "https://i.oneme.ru/i?r=..."
        }
        """
        self.id = id
        self.account_status = account_status
        self.base_raw_url = base_raw_url
        self.base_url = base_url
        self.names = names
        self.options = options or []
        self.photo_id = photo_id
        # TODO надо сделать пребразование в datetime с учетом таймзоны
        self.update_time = update_time

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            account_status=data.get("accountStatus"),
            update_time=data.get("updateTime"),
            id=data.get("id"),
            names=[Name.from_dict(n) for n in data.get("names", [])],
            options=data.get("options"),
            base_url=data.get("baseUrl"),
            base_raw_url=data.get("baseRawUrl"),
            photo_id=data.get("photoId"),
        )

    @override
    def __repr__(self) -> str:
        return f"Contact(id={self.id!r}, names={self.names!r}, status={self.account_status!r})"

    @override
    def __str__(self) -> str:
        return f"Contact {self.id}: {', '.join(str(n) for n in self.names or [])}"


class Member:
    def __init__(self, contact: Contact, presence: Presence, read_mark: int | None, ) -> None:
        """
        Участник чата.

        Структура:
        {
            "presence": Presence{}
            "readMark": {{ timestamp with milliseconds }},
            "contact": Contact{}
        },
        """
        self.presence = presence
        # TODO надо сделать пребразование в datetime с учетом таймзоны
        self.read_mark = read_mark
        self.contact = contact

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        presence_value = data.get("presence")
        if isinstance(presence_value, dict):
            presence = Presence.from_dict(presence_value)
        else:
            presence = Presence.from_dict({})
        contact_value = data.get("contact")
        if isinstance(contact_value, dict):
            contact = Contact.from_dict(contact_value)
        else:
            contact = Contact.from_dict({})
        return cls(
            contact=contact,
            presence=presence,
            read_mark=data.get("readMark"),
        )

    @override
    def __repr__(self) -> str:
        return f"Member(presence={self.presence!r}, read_mark={self.read_mark!r}, contact={self.contact!r})"

    @override
    def __str__(self) -> str:
        return f"Member {self.contact.id}: {', '.join(str(n) for n in self.contact.names or [])}"


class StickerAttach:
    def __init__(self, author_type: str, lottie_url: str | None, url: str, sticker_id: int, tags: list[str] | None,
                 width: int, set_id: int, time: int, sticker_type: str, audio: bool, height: int, type: AttachType, ):
        self.author_type = author_type
        self.lottie_url = lottie_url
        self.url = url
        self.sticker_id = sticker_id
        self.tags = tags
        self.width = width
        self.set_id = set_id
        self.time = time
        self.sticker_type = sticker_type
        self.audio = audio
        self.height = height
        self.type = type

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            author_type=data["authorType"],
            lottie_url=data.get("lottieUrl"),
            url=data["url"],
            sticker_id=data["stickerId"],
            tags=data.get("tags"),
            width=data["width"],
            set_id=data["setId"],
            time=data["time"],
            sticker_type=data["stickerType"],
            audio=data["audio"],
            height=data["height"],
            type=AttachType(data["_type"]),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"StickerAttach(author_type={self.author_type!r}, lottie_url={self.lottie_url!r}, "
            f"url={self.url!r}, sticker_id={self.sticker_id!r}, tags={self.tags!r}, "
            f"width={self.width!r}, set_id={self.set_id!r}, time={self.time!r}, "
            f"sticker_type={self.sticker_type!r}, audio={self.audio!r}, height={self.height!r}, "
            f"type={self.type!r})"
        )

    @override
    def __str__(self) -> str:
        return f"StickerAttach: {self.sticker_id}"


class ControlAttach:
    def __init__(self, type: AttachType, event: str, **kwargs: dict[str, Any]) -> None:
        self.type = type
        self.event = event
        self.extra = kwargs

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр ControlAttach из словаря.

        Метод извлекает тип вложения и событие из входных данных,
        удаляя их из словаря, а затем передаёт оставшиеся поля как дополнительные параметры.

        Используется для десериализации данных, полученных от API.

        :param data: Словарь с данными вложения.
        :type data: dict[str, Any]
        :return: Новый экземпляр ControlAttach.
        :rtype: Self
        """
        data = dict(data)
        attach_type = AttachType(data.pop("_type"))
        event = data.pop("event")
        return cls(
            type=attach_type,
            event=event,
            **data,
        )

    @override
    def __repr__(self) -> str:
        return f"ControlAttach(type={self.type!r}, event={self.event!r}, extra={self.extra!r})"

    @override
    def __str__(self) -> str:
        return f"ControlAttach: {self.event}"


class AudioAttach:
    """
    Аудиовложение в сообщении (голосовое сообщение).
    
    Содержит данные об аудиофайле: длительность, URL, волновую форму и т.д.
    """
    def __init__(self, duration: int, audio_id: int, url: str, wave: str, transcription_status: str, token: str,
                 type: AttachType, ) -> None:
        """
        Инициализирует аудиовложение.

        :param duration: Длительность аудио в миллисекундах.
        :param audio_id: ID аудиофайла.
        :param url: URL для загрузки аудио.
        :param wave: Волновая форма (визуальное представление).
        :param transcription_status: Статус транскрибации.
        :param token: Токен доступа к аудио.
        :param type: Тип вложения (AUDIO).
        """
        self.duration = duration  # Длительность аудио в мс
        self.audio_id = audio_id  # ID аудиофайла
        self.url = url  # URL для загрузки
        self.wave = wave  # Волновая форма
        self.transcription_status = transcription_status  # Статус транскрибации
        self.token = token  # Токен доступа
        self.type = type  # Тип вложения (AUDIO)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр AudioAttach из словаря.
        
        :param data: Словарь с данными аудио.
        :return: Новый экземпляр AudioAttach.
        """
        return cls(
            duration=data["duration"],
            audio_id=data["audioId"],
            url=data["url"],
            wave=data["wave"],
            transcription_status=data["transcriptionStatus"],
            token=data["token"],
            type=AttachType(data["_type"]),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"AudioAttach(duration={self.duration!r}, audio_id={self.audio_id!r}, "
            f"url={self.url!r}, wave={self.wave!r}, transcription_status={self.transcription_status!r}, "
            f"token={self.token!r}, type={self.type!r})"
        )

    @override
    def __str__(self) -> str:
        return f"AudioAttach: {self.audio_id}"


class PhotoAttach:
    """
    Вложение фотографии в сообщении.
    
    Содержит данные о фотографии: URL, размеры, токен и т.д.
    """
    def __init__(self, base_url: str, height: int, width: int, photo_id: int, photo_token: str,
                 preview_data: str | None, type: AttachType, ) -> None:
        """
        Инициализирует вложение фотографии.

        :param base_url: Базовый URL для загрузки фото.
        :param height: Высота фото в пикселях.
        :param width: Ширина фото в пикселях.
        :param photo_id: ID фотографии.
        :param photo_token: Токен фотографии.
        :param preview_data: Данные превью (сжатое изображение).
        :param type: Тип вложения (PHOTO).
        """
        self.base_url = base_url  # Базовый URL для загрузки
        self.height = height  # Высота в пикселях
        self.width = width  # Ширина в пикселях
        self.photo_id = photo_id  # ID фотографии
        self.photo_token = photo_token  # Токен фотографии
        self.preview_data = preview_data  # Данные превью
        self.type = type  # Тип вложения (PHOTO)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр PhotoAttach из словаря.
        
        :param data: Словарь с данными фотографии.
        :return: Новый экземпляр PhotoAttach.
        """
        return cls(
            base_url=data["baseUrl"],
            height=data["height"],
            width=data["width"],
            photo_id=data["photoId"],
            photo_token=data["photoToken"],
            preview_data=data.get("previewData"),
            type=AttachType(data["_type"]),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"PhotoAttach(photo_id={self.photo_id!r}, base_url={self.base_url!r}, "
            f"height={self.height!r}, width={self.width!r}, photo_token={self.photo_token!r}, "
            f"preview_data={self.preview_data!r}, type={self.type!r})"
        )

    @override
    def __str__(self) -> str:
        return f"PhotoAttach: {self.photo_id}"


class VideoAttach:
    """
    Видеовложение в сообщении.
    
    Содержит данные о видеофайле: размеры, длительность, превью и т.д.
    """
    def __init__(self, height: int, width: int, video_id: int, duration: int, preview_data: str, type: AttachType,
                 thumbnail: str, token: str, video_type: int, ) -> None:
        """
        Инициализирует видеовложение.

        :param height: Высота видео в пикселях.
        :param width: Ширина видео в пикселях.
        :param video_id: ID видеофайла.
        :param duration: Длительность видео в миллисекундах.
        :param preview_data: Данные превью.
        :param type: Тип вложения (VIDEO).
        :param thumbnail: URL миниатюры.
        :param token: Токен доступа к видео.
        :param video_type: Тип видео.
        """
        self.height = height  # Высота в пикселях
        self.width = width  # Ширина в пикселях
        self.video_id = video_id  # ID видеофайла
        self.duration = duration  # Длительность в мс
        self.preview_data = preview_data  # Данные превью
        self.type = type  # Тип вложения (VIDEO)
        self.thumbnail = thumbnail  # Миниатюра
        self.token = token  # Токен доступа
        self.video_type = video_type  # Тип видео

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр VideoAttach из словаря.
        
        :param data: Словарь с данными видео.
        :return: Новый экземпляр VideoAttach.
        """
        return cls(
            height=data["height"],
            width=data["width"],
            video_id=data["videoId"],
            duration=data["duration"],
            preview_data=data["previewData"],
            type=AttachType(data["_type"]),
            thumbnail=data["thumbnail"],
            token=data["token"],
            video_type=data["videoType"],
        )

    @override
    def __repr__(self) -> str:
        return (
            f"VideoAttach(video_id={self.video_id!r}, height={self.height!r}, "
            f"width={self.width!r}, duration={self.duration!r}, "
            f"preview_data={self.preview_data!r}, type={self.type!r}, "
            f"thumbnail={self.thumbnail!r}, token={self.token!r}, "
            f"video_type={self.video_type!r})"
        )

    @override
    def __str__(self) -> str:
        return f"VideoAttach: {self.video_id}"


class FileAttach:
    """
    Вложение файла в сообщении (документ).
    
    Содержит данные о файле: имя, размер, токен для загрузки.
    """
    def __init__(self, file_id: int, name: str, size: int, token: str, type: AttachType) -> None:
        """
        Инициализирует вложение файла.

        :param file_id: ID файла.
        :param name: Имя файла.
        :param size: Размер файла в байтах.
        :param token: Токен для загрузки.
        :param type: Тип вложения (FILE).
        """
        self.file_id = file_id  # ID файла
        self.name = name  # Имя файла
        self.size = size  # Размер в байтах
        self.token = token  # Токен для загрузки
        self.type = type  # Тип вложения (FILE)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр FileAttach из словаря.
        
        :param data: Словарь с данными файла.
        :return: Новый экземпляр FileAttach.
        """
        return cls(
            file_id=data["fileId"],
            name=data["name"],
            size=data["size"],
            token=data["token"],
            type=AttachType(data["_type"]),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"FileAttach(file_id={self.file_id!r}, name={self.name!r}, "
            f"size={self.size!r}, token={self.token!r}, type={self.type!r})"
        )

    @override
    def __str__(self) -> str:
        return f"FileAttach: {self.file_id}"


class FileRequest:
    """
    Запрос на загрузку файла.
    
    Используется для получения URL загрузки файла.
    """
    def __init__(self, unsafe: bool, url: str, ) -> None:
        """
        Инициализирует запрос на загрузку.

        :param unsafe: Флаг небезопасного соединения.
        :param url: URL для загрузки.
        """
        self.unsafe = unsafe  # Флаг небезопасного соединения
        self.url = url  # URL для загрузки

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр FileRequest из словаря.
        
        :param data: Словарь с данными запроса.
        :return: Новый экземпляр FileRequest.
        """
        return cls(
            unsafe=data["unsafe"],
            url=data["url"],
        )


class VideoRequest:
    """
    Запрос на загрузку видео.
    
    Используется для получения URL загрузки видеофайла.
    """
    def __init__(self, external: str, cache: bool, url: str, ) -> None:
        """
        Инициализирует запрос на загрузку видео.

        :param external: Флаг внешнего источника.
        :param cache: Флаг кэширования.
        :param url: URL для загрузки.
        """
        self.external = external  # Флаг внешнего источника
        self.cache = cache  # Флаг кэширования
        self.url = url  # URL для загрузки

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр VideoRequest из словаря.
        
        :param data: Словарь с данными запроса.
        :return: Новый экземпляр VideoRequest.
        """
        # listdata = list(data.values()) # Костыль ✅
        # Извлекаем URL, исключая служебные поля
        url = [v for k, v in data.items() if k not in ("EXTERNAL", "accounts")][
            0
        ]  # Еще больший костыль ✅
        return cls(
            external=data["EXTERNAL"],
            cache=data["accounts"],
            url=url,
        )


class Me:
    """
    Текущий пользователь (я).
    
    Содержит информацию о текущем авторизованном пользователе:
    - ID и статус аккаунта
    - Номер телефона
    - Имена
    - Опции платформ
    """
    def __init__(self, id: int, account_status: int, phone: str, names: list[Names], update_time: int,
                 options: list[str] | None = None, ) -> None:
        """
        Инициализирует текущего пользователя.

        :param id: ID пользователя.
        :param account_status: Статус аккаунта.
        :param phone: Номер телефона.
        :param names: Список имён.
        :param update_time: Время обновления (timestamp).
        :param options: Опции платформ.
        """
        self.id = id  # ID пользователя
        self.account_status = account_status  # Статус аккаунта
        self.phone = phone  # Номер телефона
        self.update_time = update_time  # Время обновления
        self.options = options  # Опции платформ
        self.names = names  # Список имён

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр Me из словаря.
        
        :param data: Словарь с данными пользователя.
        :return: Новый экземпляр Me.
        """
        return cls(
            id=data["id"],
            account_status=data["accountStatus"],
            phone=data["phone"],
            names=[Names.from_dict(n) for n in data["names"]],
            update_time=data["updateTime"],
            options=data.get("options"),
        )

    @override
    def __repr__(self) -> str:
        return f"Me(id={self.id!r}, account_status={self.account_status!r}, phone={self.phone!r}, names={self.names!r}, update_time={self.update_time!r}, options={self.options!r})"

    @override
    def __str__(self) -> str:
        return f"Me {self.id}: {', '.join(str(n) for n in self.names)}"


class Element:
    """
    Элемент форматирования текста сообщения.
    
    Используется для выделения частей текста:
    - Жирный (bold)
    - Курсив (italic)
    - Подчёркнутый (underline)
    - Зачёркнутый (strike)
    - Ссылка (link)
    - Код (code)
    """
    def __init__(self, type: FormattingType | str, length: int, from_: int | None = None) -> None:
        """
        Инициализирует элемент форматирования.

        :param type: Тип форматирования.
        :param length: Длина элемента в символах.
        :param from_: Позиция начала элемента в тексте.
        """
        self.type = type  # Тип форматирования
        self.length = length  # Длина в символах
        self.from_ = from_  # Позиция начала

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> Self:
        """
        Создаёт экземпляр Element из словаря.
        
        :param data: Словарь с данными элемента.
        :return: Новый экземпляр Element.
        """
        return cls(type=data["type"], length=data["length"], from_=data.get("from"))

    @override
    def __repr__(self) -> str:
        return f"Element(type={self.type!r}, length={self.length!r}, from_={self.from_!r})"

    @override
    def __str__(self) -> str:
        return f"{self.type}({self.length})"


class MessageLink:
    """
    Ссылка на сообщение (для ответов и пересылок).
    
    Содержит информацию о сообщении, на которое ссылается текущее.
    """
    def __init__(self, chat_id: int, message: "Message", type: str) -> None:
        """
        Инициализирует ссылку на сообщение.

        :param chat_id: ID чата с сообщением.
        :param message: Объект сообщения.
        :param type: Тип ссылки (REPLY, FORWARD и т.д.).
        """
        self.chat_id = chat_id  # ID чата
        self.message = message  # Объект сообщения
        self.type = type  # Тип ссылки

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр MessageLink из словаря.
        
        :param data: Словарь с данными ссылки.
        :return: Новый экземпляр MessageLink.
        """
        return cls(
            chat_id=data["chatId"],
            message=Message.from_dict(data["message"]),
            type=data["type"],
        )

    @override
    def __repr__(self) -> str:
        return (
            f"MessageLink(chat_id={self.chat_id!r}, message={self.message!r}, type={self.type!r})"
        )

    @override
    def __str__(self) -> str:
        return f"MessageLink: {self.chat_id}/{self.message.id}"


class ReactionCounter:
    """
    Счётчик реакции на сообщение.
    
    Содержит информацию о количестве конкретных реакций.
    """
    def __init__(self, count: int, reaction: str) -> None:
        """
        Инициализирует счётчик реакции.

        :param count: Количество реакций.
        :param reaction: Тип реакции (эмодзи).
        """
        self.count = count  # Количество реакций
        self.reaction = reaction  # Тип реакции (эмодзи)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр ReactionCounter из словаря.
        
        :param data: Словарь с данными счётчика.
        :return: Новый экземпляр ReactionCounter.
        """
        return cls(count=data["count"], reaction=data["reaction"])

    @override
    def __repr__(self) -> str:
        return f"ReactionCounter(count={self.count!r}, reaction={self.reaction!r})"

    @override
    def __str__(self) -> str:
        return f"{self.reaction}: {self.count}"


class ReactionInfo:
    """
    Информация о реакциях на сообщение.
    
    Содержит общую информацию о всех реакциях на сообщение.
    """
    def __init__(self, total_count: int, counters: list[ReactionCounter], your_reaction: str | None = None,
                 ) -> None:
        """
        Инициализирует информацию о реакциях.

        :param total_count: Общее количество реакций.
        :param counters: Список счётчиков по типам реакций.
        :param your_reaction: Ваша реакция (если есть).
        """
        self.total_count = total_count  # Общее количество
        self.counters = counters  # Счётчики по типам
        self.your_reaction = your_reaction  # Ваша реакция

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр ReactionInfo из словаря.
        
        :param data: Словарь с данными о реакциях.
        :return: Новый экземпляр ReactionInfo.
        """
        return cls(
            total_count=data.get("totalCount", 0),
            counters=[ReactionCounter.from_dict(c) for c in data.get("counters", [])],
            your_reaction=data.get("yourReaction"),
        )


class ContactAttach:
    """
    Вложение контакта в сообщении.
    
    Используется для отправки контакта пользователя.
    """
    def __init__(self, contact_id: int, first_name: str, last_name: str, name: str, photo_url: str) -> None:
        """
        Инициализирует вложение контакта.

        :param contact_id: ID контакта.
        :param first_name: Имя контакта.
        :param last_name: Фамилия контакта.
        :param name: Полное имя.
        :param photo_url: URL фото контакта.
        """
        self.contact_id = contact_id  # ID контакта
        self.first_name = first_name  # Имя
        self.last_name = last_name  # Фамилия
        self.name = name  # Полное имя
        self.photo_url = photo_url  # URL фото
        self.type = AttachType.CONTACT  # Тип вложения (CONTACT)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр ContactAttach из словаря.
        
        :param data: Словарь с данными контакта.
        :return: Новый экземпляр ContactAttach.
        """
        return cls(
            contact_id=data["contactId"],
            first_name=data["firstName"],
            last_name=data["lastName"],
            name=data["name"],
            photo_url=data["photoUrl"],
        )

    @override
    def __repr__(self) -> str:
        return f"ContactAttach(contact_id={self.contact_id!r}, first_name={self.first_name!r}, last_name={self.last_name!r}, name={self.name!r}, photo_url={self.photo_url!r})"

    @override
    def __str__(self) -> str:
        return f"ContactAttach: {self.name}"


class Message:
    """
    Сообщение в чате.
    
    Основной класс для представления сообщений в мессенджере Max.
    Содержит всю информацию о сообщении:
    - Текст и элементы форматирования
    - Вложения (фото, видео, файлы, стикеры, аудио)
    - Реакции
    - Ссылки (ответы, пересылки)
    - Статус доставки
    """
    def __init__(self, chat_id: int | None, sender: int | None, elements: list[Element] | None,
                 reaction_info: ReactionInfo | None, options: int | None, id: int, time: int, link: MessageLink | None,
                 text: str, status: MessageStatus | None, type: MessageType | str,
                 attaches: (
                         list[
                             PhotoAttach
                             | VideoAttach
                             | FileAttach
                             | ControlAttach
                             | StickerAttach
                             | AudioAttach
                             | ContactAttach
                             ]
                         | None
                 ),
                 ) -> None:
        """
        Инициализирует сообщение.

        :param chat_id: ID чата, в котором отправлено сообщение.
        :param sender: ID отправителя.
        :param elements: Элементы форматирования текста.
        :param reaction_info: Информация о реакциях.
        :param options: Опции сообщения.
        :param id: ID сообщения.
        :param time: Время отправки (timestamp).
        :param link: Ссылка на другое сообщение.
        :param text: Текст сообщения.
        :param status: Статус сообщения.
        :param type: Тип сообщения.
        :param attaches: Список вложений.
        """
        self.chat_id = chat_id  # ID чата
        self.sender = sender  # ID отправителя
        self.elements = elements  # Элементы форматирования
        self.options = options  # Опции
        self.id = id  # ID сообщения
        self.time = time  # Время отправки
        self.text = text  # Текст сообщения
        self.type = type  # Тип сообщения
        self.attaches = attaches  # Вложения
        self.status = status  # Статус
        self.link = link  # Ссылка
        self.reactionInfo = reaction_info  # Информация о реакциях

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> Self:
        """
        Создаёт экземпляр Message из словаря.
        
        :param data: Словарь с данными сообщения.
        :return: Новый экземпляр Message.
        """
        message = data["message"] if data.get("message") else data
        attaches: list[
            PhotoAttach
            | VideoAttach
            | FileAttach
            | ControlAttach
            | StickerAttach
            | AudioAttach
            | ContactAttach
            ] = []
        
        # Обрабатываем каждое вложение в зависимости от типа
        for a in message.get("attaches", []):
            if a["_type"] == AttachType.PHOTO:
                attaches.append(PhotoAttach.from_dict(a))
            elif a["_type"] == AttachType.VIDEO:
                attaches.append(VideoAttach.from_dict(a))
            elif a["_type"] == AttachType.FILE:
                attaches.append(FileAttach.from_dict(a))
            elif a["_type"] == AttachType.CONTROL:
                attaches.append(ControlAttach.from_dict(a))
            elif a["_type"] == AttachType.STICKER:
                attaches.append(StickerAttach.from_dict(a))
            elif a["_type"] == AttachType.AUDIO:
                attaches.append(AudioAttach.from_dict(a))
            elif a["_type"] == AttachType.CONTACT:
                attaches.append(ContactAttach.from_dict(a))
        
        # Обрабатываем ссылку (ответ/пересылка)
        link_value = message.get("link")
        if isinstance(link_value, dict):
            link = MessageLink.from_dict(link_value)
        else:
            link = None
        
        # Обрабатываем информацию о реакциях
        reaction_info_value = message.get("reactionInfo")
        if isinstance(reaction_info_value, dict):
            reaction_info = ReactionInfo.from_dict(reaction_info_value)
        else:
            reaction_info = None
        
        return cls(
            chat_id=data.get("chatId"),
            sender=message.get("sender"),
            elements=[Element.from_dict(e) for e in message.get("elements", [])],
            options=message.get("options"),
            id=message["id"],
            time=message["time"],
            text=message["text"],
            type=message["type"],
            attaches=attaches,
            status=message.get("status"),
            link=link,
            reaction_info=reaction_info,
        )

    @override
    def __repr__(self) -> str:
        return (
            f"Message(id={self.id!r}, sender={self.sender!r}, text={self.text!r}, "
            f"type={self.type!r}, status={self.status!r}, elements={self.elements!r})"
            f"attaches={self.attaches!r}, chat_id={self.chat_id!r}, time={self.time!r}, options={self.options!r}, reactionInfo={self.reactionInfo!r})"
        )

    @override
    def __str__(self) -> str:
        return f"Message {self.id} from {self.sender}: {self.text}"


class Dialog:
    """
    Личный диалог (чат один на один).
    
    Представляет диалог между двумя пользователями.
    Наследуется от базового типа чата.
    """
    def __init__(self, cid: int | None, owner: int, has_bots: bool | None, join_time: int, created: int,
                 last_message: Message | None, type: ChatType | str, last_fire_delayed_error_time: int,
                 last_delayed_update_time: int, prev_message_id: str | None, options: dict[str, bool], modified: int,
                 last_event_time: int, id: int, status: str, participants: dict[str, int]) -> None:
        """
        Инициализирует диалог.

        :param cid: ID чата.
        :param owner: ID владельца.
        :param has_bots: Наличие ботов.
        :param join_time: Время вступления.
        :param created: Время создания.
        :param last_message: Последнее сообщение.
        :param type: Тип чата (DIALOG).
        :param last_fire_delayed_error_time: Время последней ошибки.
        :param last_delayed_update_time: Время последнего обновления.
        :param prev_message_id: ID предыдущего сообщения.
        :param options: Опции чата.
        :param modified: Время изменения.
        :param last_event_time: Время последнего события.
        :param id: ID диалога.
        :param status: Статус.
        :param participants: Участники.
        """
        self.cid = cid  # ID чата
        self.owner = owner  # ID владельца
        self.has_bots = has_bots  # Наличие ботов
        self.join_time = join_time  # Время вступления
        self.created = created  # Время создания
        self.last_message = last_message  # Последнее сообщение
        self.type = type  # Тип чата
        self.last_fire_delayed_error_time = last_fire_delayed_error_time  # Время ошибки
        self.last_delayed_update_time = last_delayed_update_time  # Время обновления
        self.prev_message_id = prev_message_id  # ID предыдущего сообщения
        self.options = options  # Опции
        self.modified = modified  # Время изменения
        self.last_event_time = last_event_time  # Время последнего события
        self.id = id  # ID диалога
        self.status = status  # Статус
        self.participants = participants  # Участники

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> Self:
        """
        Создаёт экземпляр Dialog из словаря.
        
        :param data: Словарь с данными диалога.
        :return: Новый экземпляр Dialog.
        """
        return cls(
            cid=data.get("cid"),
            owner=data["owner"],
            has_bots=data.get("hasBots"),
            join_time=data["joinTime"],
            created=data["created"],
            last_message=(
                Message.from_dict(data["lastMessage"]) if data.get("lastMessage") else None
            ),
            type=ChatType(data["type"]),
            last_fire_delayed_error_time=data["lastFireDelayedErrorTime"],
            last_delayed_update_time=data["lastDelayedUpdateTime"],
            prev_message_id=data.get("prevMessageId"),
            options=data.get("options", {}),
            modified=data["modified"],
            last_event_time=data["lastEventTime"],
            id=data["id"],
            status=data["status"],
            participants=data["participants"],
        )

    @override
    def __repr__(self) -> str:
        return f"Dialog(id={self.id!r}, owner={self.owner!r}, type={self.type!r}, last_message={self.last_message!r})"

    @override
    def __str__(self) -> str:
        return f"Dialog {self.id} ({self.type})"


class Chat:
    """
    Групповой чат.
    
    Представляет групповой чат с несколькими участниками.
    Содержит полную информацию о чате: участники, админы, настройки и т.д.
    """
    def __init__(self, participants_count: int, access: AccessType | str, invited_by: int | None, link: str | None,
                 chat_type: ChatType | str, title: str | None, last_fire_delayed_error_time: int,
                 last_delayed_update_time: int, options: dict[str, bool], base_raw_icon_url: str | None,
                 base_icon_url: str | None, description: str | None, modified: int, id_: int,
                 admin_participants: dict[int, dict[Any, Any]], participants: dict[int, int], owner: int,
                 join_time: int, created: int, last_message: Message | None, prev_message_id: str | None,
                 last_event_time: int, messages_count: int, admins: list[int], restrictions: int | None, status: str,
                 cid: int) -> None:
        """
        Инициализирует групповой чат.

        :param participants_count: Количество участников.
        :param access: Тип доступа (публичный/приватный).
        :param invited_by: ID пригласившего.
        :param link: Ссылка-приглашение.
        :param chat_type: Тип чата.
        :param title: Название чата.
        :param last_fire_delayed_error_time: Время последней ошибки.
        :param last_delayed_update_time: Время последнего обновления.
        :param options: Опции чата.
        :param base_raw_icon_url: URL иконки (исходная).
        :param base_icon_url: URL иконки (сжатая).
        :param description: Описание чата.
        :param modified: Время изменения.
        :param id_: ID чата.
        :param admin_participants: Администраторы.
        :param participants: Участники.
        :param owner: ID владельца.
        :param join_time: Время вступления.
        :param created: Время создания.
        :param last_message: Последнее сообщение.
        :param prev_message_id: ID предыдущего сообщения.
        :param last_event_time: Время последнего события.
        :param messages_count: Количество сообщений.
        :param admins: Список админов.
        :param restrictions: Ограничения.
        :param status: Статус.
        :param cid: ID чата.
        """
        self.participants_count = participants_count  # Количество участников
        self.access = access  # Тип доступа
        self.invited_by = invited_by  # ID пригласившего
        self.link = link  # Ссылка-приглашение
        self.type = chat_type  # Тип чата
        self.title = title  # Название
        self.last_fire_delayed_error_time = last_fire_delayed_error_time  # Время ошибки
        self.last_delayed_update_time = last_delayed_update_time  # Время обновления
        self.options = options  # Опции
        self.base_raw_icon_url = base_raw_icon_url  # URL иконки (исходная)
        self.base_icon_url = base_icon_url  # URL иконки (сжатая)
        self.description = description  # Описание
        self.modified = modified  # Время изменения
        self.id = id_  # ID чата
        self.admin_participants = admin_participants  # Администраторы
        self.participants = participants  # Участники
        self.owner = owner  # ID владельца
        self.join_time = join_time  # Время вступления
        self.created = created  # Время создания
        self.last_message = last_message  # Последнее сообщение
        self.prev_message_id = prev_message_id  # ID предыдущего сообщения
        self.last_event_time = last_event_time  # Время последнего события
        self.messages_count = messages_count  # Количество сообщений
        self.admins = admins  # Список админов
        self.restrictions = restrictions  # Ограничения
        self.status = status  # Статус
        self.cid = cid  # ID чата

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> Self:
        """
        Создаёт экземпляр Chat из словаря.
        
        :param data: Словарь с данными чата.
        :return: Новый экземпляр Chat.
        """
        # Преобразуем ключи словарей в int
        raw_admins = data.get("adminParticipants", {}) or {}
        admin_participants: dict[int, dict[Any, Any]] = {int(k): v for k, v in raw_admins.items()}
        raw_participants = data.get("participants", {}) or {}
        participants: dict[int, int] = {int(k): v for k, v in raw_participants.items()}
        
        # Обрабатываем последнее сообщение
        last_msg = Message.from_dict(data["lastMessage"]) if data.get("lastMessage") else None
        
        return cls(
            participants_count=data.get("participantsCount", 0),
            access=AccessType(data.get("access", AccessType.PUBLIC.value)),
            invited_by=data.get("invitedBy"),
            link=data.get("link"),
            base_raw_icon_url=data.get("baseRawIconUrl"),
            base_icon_url=data.get("baseIconUrl"),
            description=data.get("description"),
            chat_type=ChatType(data.get("type", ChatType.CHAT.value)),
            title=data.get("title"),
            last_fire_delayed_error_time=data.get("lastFireDelayedErrorTime", 0),
            last_delayed_update_time=data.get("lastDelayedUpdateTime", 0),
            options=data.get("options", {}),
            modified=data.get("modified", 0),
            id_=data.get("id", 0),
            admin_participants=admin_participants,
            participants=participants,
            owner=data.get("owner", 0),
            join_time=data.get("joinTime", 0),
            created=data.get("created", 0),
            last_message=last_msg,
            prev_message_id=data.get("prevMessageId"),
            last_event_time=data.get("lastEventTime", 0),
            messages_count=data.get("messagesCount", 0),
            admins=data.get("admins", []),
            restrictions=data.get("restrictions"),
            status=data.get("status", ""),
            cid=data.get("cid", 0),
        )

    @override
    def __repr__(self) -> str:
        return f"Chat(id={self.id!r}, title={self.title!r}, type={self.type!r})"

    @override
    def __str__(self) -> str:
        return f"{self.title} ({self.type})"


class Channel(Chat):
    """
    Канал.
    
    Наследуется от Chat, представляет публичный или приватный канал.
    Отличается от чата тем, что сообщения могут отправлять только администраторы.
    """
    @override
    def __repr__(self) -> str:
        return f"Channel(id={self.id!r}, title={self.title!r})"

    @override
    def __str__(self) -> str:
        return f"Channel: {self.title}"


class User:
    """
    Пользователь мессенджера Max.
    
    Содержит полную информацию о пользователе:
    - Имя и фамилия
    - Аватар
    - Описание (статус)
    - Пол
    - Ссылка на профиль
    - Веб-приложение и кнопка меню
    """
    def __init__(
            self,
            account_status: int,
            update_time: int,
            id: int,
            names: list[Names],
            options: list[str] | None = None,
            base_url: str | None = None,
            base_raw_url: str | None = None,
            photo_id: int | None = None,
            description: str | None = None,
            gender: int | None = None,
            link: str | None = None,
            web_app: str | None = None,
            menu_button: dict[str, Any] | None = None,
    ) -> None:
        """
        Инициализирует пользователя.

        :param account_status: Статус аккаунта.
        :param update_time: Время обновления (timestamp).
        :param id: ID пользователя.
        :param names: Список имён.
        :param options: Опции платформ.
        :param base_url: URL аватара (сжатый).
        :param base_raw_url: URL аватара (исходный).
        :param photo_id: ID фотографии.
        :param description: Описание (статус).
        :param gender: Пол.
        :param link: Ссылка на профиль.
        :param web_app: Веб-приложение.
        :param menu_button: Кнопка меню.
        """
        self.account_status = account_status  # Статус аккаунта
        self.update_time = update_time  # Время обновления
        self.id = id  # ID пользователя
        self.names = names  # Список имён
        self.options = options or []  # Опции платформ
        self.base_url = base_url  # URL аватара (сжатый)
        self.base_raw_url = base_raw_url  # URL аватара (исходный)
        self.photo_id = photo_id  # ID фотографии
        self.description = description  # Описание
        self.gender = gender  # Пол
        self.link = link  # Ссылка на профиль
        self.web_app = web_app  # Веб-приложение
        self.menu_button = menu_button  # Кнопка меню

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр User из словаря.
        
        :param data: Словарь с данными пользователя.
        :return: Новый экземпляр User.
        """
        return cls(
            account_status=data["accountStatus"],
            update_time=data["updateTime"],
            id=data["id"],
            names=[Names.from_dict(n) for n in data.get("names", [])],
            options=data.get("options"),
            base_url=data.get("baseUrl"),
            base_raw_url=data.get("baseRawUrl"),
            photo_id=data.get("photoId"),
            description=data.get("description"),
            gender=data.get("gender"),
            link=data.get("link"),
            web_app=data.get("webApp"),
            menu_button=data.get("menuButton"),
        )

    @override
    def __repr__(self) -> str:
        return f"User(id={self.id!r}, names={self.names!r}, status={self.account_status!r})"

    @override
    def __str__(self) -> str:
        return f"User {self.id}: {', '.join(str(n) for n in self.names)}"


class Attach:  # УБРАТЬ ГАДА!!! или нет...
    """
    Базовое вложение.
    
    Примечание разработчика: класс-заглушка для совместимости.
    Возможно, будет удалён в будущих версиях.
    """
    def __init__(
            self,
            _type: AttachType,
            video_id: int | None = None,
            photo_token: str | None = None,
            file_id: int | None = None,
            token: str | None = None,
    ) -> None:
        """
        Инициализирует базовое вложение.

        :param _type: Тип вложения.
        :param video_id: ID видео.
        :param photo_token: Токен фото.
        :param file_id: ID файла.
        :param token: Токен доступа.
        """
        self.type = _type  # Тип вложения
        self.video_id = video_id  # ID видео
        self.photo_token = photo_token  # Токен фото
        self.file_id = file_id  # ID файла
        self.token = token  # Токен доступа

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр Attach из словаря.
        
        :param data: Словарь с данными вложения.
        :return: Новый экземпляр Attach.
        """
        return cls(
            _type=AttachType(data["type"]),
            video_id=data.get("videoId"),
            photo_token=data.get("photoToken"),
            file_id=data.get("fileId"),
            token=data.get("token"),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"Attach(type={self.type!r}, video_id={self.video_id!r}, "
            f"photo_token={self.photo_token!r}, file_id={self.file_id!r}, token={self.token!r})"
        )

    @override
    def __str__(self) -> str:
        return f"Attach: {self.type}"


class Session:
    """
    Сессия пользователя (устройство).
    
    Содержит информацию об активном устройстве пользователя.
    """
    def __init__(
            self,
            client: str,
            info: str,
            location: str,
            time: int,
            current: bool | None = None,
    ) -> None:
        """
        Инициализирует сессию.

        :param client: Название клиента (устройства).
        :param info: Дополнительная информация.
        :param location: Местоположение.
        :param time: Время создания (timestamp).
        :param current: Флаг текущей сессии.
        """
        self.client = client  # Название клиента
        self.info = info  # Информация
        self.location = location  # Местоположение
        self.time = time  # Время создания
        self.current = current if current is not None else False  # Флаг текущей

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр Session из словаря.
        
        :param data: Словарь с данными сессии.
        :return: Новый экземпляр Session.
        """
        return cls(
            client=data["client"],
            info=data["info"],
            location=data["location"],
            time=data["time"],
            current=data.get("current"),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"Session(client={self.client!r}, info={self.info!r}, "
            f"location={self.location!r}, time={self.time!r}, current={self.current!r})"
        )

    @override
    def __str__(self) -> str:
        return (
            f"Session: {self.client} from {self.location} at {self.time} (current={self.current})"
        )


class Folder:
    """
    Папка чатов.
    
    Используется для группировки чатов по категориям.
    """
    def __init__(self, source_id: int, include: list[int], options: list[Any], update_time: int, id: str,
                 filters: list[Any], title: str, ) -> None:
        """
        Инициализирует папку чатов.

        :param source_id: ID источника.
        :param include: Список ID чатов в папке.
        :param options: Опции папки.
        :param update_time: Время обновления.
        :param id: ID папки.
        :param filters: Фильтры папки.
        :param title: Название папки.
        """
        self.source_id = source_id  # ID источника
        self.include = include  # Список чатов
        self.options = options  # Опции
        self.update_time = update_time  # Время обновления
        self.id = id  # ID папки
        self.filters = filters  # Фильтры
        self.title = title  # Название

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр Folder из словаря.
        
        :param data: Словарь с данными папки.
        :return: Новый экземпляр Folder.
        """
        return cls(
            source_id=data.get("sourceId", 0),
            include=data.get("include", []),
            options=data.get("options", []),
            update_time=data.get("updateTime", 0),
            id=data.get("id", ""),
            filters=data.get("filters", []),
            title=data.get("title", ""),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"Folder(id={self.id!r}, title={self.title!r}, source_id={self.source_id!r}, "
            f"include={self.include!r}, options={self.options!r}, "
            f"update_time={self.update_time!r}, filters={self.filters!r})"
        )

    @override
    def __str__(self) -> str:
        return f"Folder: {self.title} ({self.id})"


class FolderUpdate:
    """
    Обновление папки.
    
    Содержит информацию об обновлении папки чатов.
    """
    def __init__(
            self, folder_order: list[str] | None, folder: Folder | None, folder_sync: int
    ) -> None:
        """
        Инициализирует обновление папки.

        :param folder_order: Порядок папок.
        :param folder: Объект папки.
        :param folder_sync: Флаг синхронизации.
        """
        self.folder_order = folder_order  # Порядок папок
        self.folder = folder  # Объект папки
        self.folder_sync = folder_sync  # Флаг синхронизации

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр FolderUpdate из словаря.
        
        :param data: Словарь с данными обновления.
        :return: Новый экземпляр FolderUpdate.
        """
        folder_order = data.get("foldersOrder", [])
        folder_sync = data.get("folderSync", 0)
        folder_data = data.get("folder", {})
        folder = Folder.from_dict(folder_data)
        return cls(
            folder_order=folder_order,
            folder=folder,
            folder_sync=folder_sync,
        )

    @override
    def __repr__(self) -> str:
        return (
            f"FolderUpdate(folder_order={self.folder_order!r}, "
            f"folder={self.folder!r}, folder_sync={self.folder_sync!r})"
        )

    @override
    def __str__(self) -> str:
        return f"FolderUpdate: {self.folder.title} ({self.folder.id})"


class FolderList:
    """
    Список папок.
    
    Содержит все папки чатов пользователя.
    """
    def __init__(self, folders_order: list[str], folders: list[Folder], folder_sync: int,
                 all_filter_exclude_folders: list[Any] | None = None) -> None:
        """
        Инициализирует список папок.

        :param folders_order: Порядок папок.
        :param folders: Список папок.
        :param folder_sync: Флаг синхронизации.
        :param all_filter_exclude_folders: Исключения фильтра.
        """
        self.folders_order = folders_order  # Порядок папок
        self.folders = folders  # Список папок
        self.all_filter_exclude_folders = all_filter_exclude_folders or []  # Исключения
        self.folder_sync = folder_sync  # Флаг синхронизации

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр FolderList из словаря.
        
        :param data: Словарь со списком папок.
        :return: Новый экземпляр FolderList.
        """
        return cls(
            folders_order=data.get("foldersOrder", []),
            folders=[Folder.from_dict(f) for f in data.get("folders", [])],
            all_filter_exclude_folders=data.get("allFilterExcludeFolders", []),
            folder_sync=data.get("folderSync", 0),
        )

    @override
    def __repr__(self) -> str:
        return (
            f"FolderList(folders_order={self.folders_order!r}, "
            f"folders={self.folders!r}, "
            f"all_filter_exclude_folders={self.all_filter_exclude_folders!r}, "
            f"folder_sync={self.folder_sync!r})"
        )

    @override
    def __str__(self) -> str:
        return f"FolderList: {len(self.folders)} folders"


class ReadState:
    """
    Состояние прочтения сообщений.
    
    Содержит информацию о непрочитанных сообщениях.
    """
    def __init__(
            self,
            unread: int,
            mark: int,
    ) -> None:
        """
        Инициализирует состояние прочтения.

        :param unread: Количество непрочитанных сообщений.
        :param mark: Метка прочтения.
        """
        self.unread = unread  # Количество непрочитанных
        self.mark = mark  # Метка прочтения

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Создаёт экземпляр ReadState из словаря.
        
        :param data: Словарь с данными состояния.
        :return: Новый экземпляр ReadState.
        """
        return cls(
            unread=data["unread"],
            mark=data["mark"],
        )

    @override
    def __repr__(self) -> str:
        return f"ReadState(unread={self.unread!r}, mark={self.mark!r})"

    @override
    def __str__(self) -> str:
        return f"ReadState: unread={self.unread}, mark={self.mark}"
