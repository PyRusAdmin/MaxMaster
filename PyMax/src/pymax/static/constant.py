# -*- coding: utf-8 -*-
"""
Константы для работы с API Max.

Содержит константы для User-Agent, таймаутов, URI и других параметров.
"""
from random import choice, randint
from re import Pattern, compile
from typing import Final

import ua_generator
from websockets.typing import Origin

#: Список имён устройств для User-Agent.
DEVICE_NAMES: Final[list[str]] = [
    "Chrome",
    "Firefox",
    "Edge",
    "Safari",
    "Opera",
    "Vivaldi",
    "Brave",
    "Chromium",
    # os
    "Windows 10",
    "Windows 11",
    "macOS Big Sur",
    "macOS Monterey",
    "macOS Ventura",
    "Ubuntu 20.04",
    "Ubuntu 22.04",
    "Fedora 35",
    "Fedora 36",
    "Debian 11",
]
#: Список разрешений экрана.
SCREEN_SIZES: Final[list[str]] = [
    "1920x1080 1.0x",
    "1366x768 1.0x",
    "1440x900 1.0x",
    "1536x864 1.0x",
    "1280x720 1.0x",
    "1600x900 1.0x",
    "1680x1050 1.0x",
    "2560x1440 1.0x",
    "3840x2160 1.0x",
]
#: Список версий ОС.
OS_VERSIONS: Final[list[str]] = [
    "Windows 10",
    "Windows 11",
    "macOS Big Sur",
    "macOS Monterey",
    "macOS Ventura",
    "Ubuntu 20.04",
    "Ubuntu 22.04",
    "Fedora 35",
    "Fedora 36",
    "Debian 11",
]
#: Список часовых поясов.
TIMEZONES: Final[list[str]] = [
    "Europe/Moscow",
    "Europe/Kaliningrad",
    "Europe/Samara",
    "Asia/Yekaterinburg",
    "Asia/Omsk",
    "Asia/Krasnoyarsk",
    "Asia/Irkutsk",
    "Asia/Yakutsk",
    "Asia/Vladivostok",
    "Asia/Kamchatka",
]

#: Регулярное выражение для проверки номера телефона.
PHONE_REGEX: Final[Pattern[str]] = compile(r"^\+?\d{10,15}$")
#: URI WebSocket сервера.
WEBSOCKET_URI: Final[str] = "wss://ws-api.oneme.ru/websocket"
#: Имя файла базы данных сессий.
SESSION_STORAGE_DB = "session.db"
#: Origin для WebSocket подключения.
WEBSOCKET_ORIGIN: Final[Origin] = Origin("https://web.max.ru")
#: Хост API сервера.
HOST: Final[str] = "api.oneme.ru"
#: Порт API сервера.
PORT: Final[int] = 443
#: Таймаут по умолчанию.
DEFAULT_TIMEOUT: Final[float] = 20.0
#: Тип устройства по умолчанию.
DEFAULT_DEVICE_TYPE: Final[str] = "DESKTOP"
#: Локаль по умолчанию.
DEFAULT_LOCALE: Final[str] = "ru"
#: Локаль устройства по умолчанию.
DEFAULT_DEVICE_LOCALE: Final[str] = "ru"
#: Имя устройства по умолчанию.
DEFAULT_DEVICE_NAME: Final[str] = choice(DEVICE_NAMES)
#: Версия приложения по умолчанию.
DEFAULT_APP_VERSION: Final[str] = "25.12.14"
#: Разрешение экрана по умолчанию.
DEFAULT_SCREEN: Final[str] = "1080x1920 1.0x"
#: Версия ОС по умолчанию.
DEFAULT_OS_VERSION: Final[str] = choice(OS_VERSIONS)
#: User-Agent по умолчанию.
DEFAULT_USER_AGENT: Final[str] = ua_generator.generate().text
#: Номер сборки по умолчанию.
DEFAULT_BUILD_NUMBER: Final[int] = 0x97CB
#: ID клиентской сессии по умолчанию.
DEFAULT_CLIENT_SESSION_ID: Final[int] = randint(1, 15)
#: Часовой пояс по умолчанию.
DEFAULT_TIMEZONE: Final[str] = choice(TIMEZONES)
#: Лимит участников чата по умолчанию.
DEFAULT_CHAT_MEMBERS_LIMIT: Final[int] = 50
#: Значение маркера по умолчанию.
DEFAULT_MARKER_VALUE: Final[int] = 0
#: Интервал ping по умолчанию.
DEFAULT_PING_INTERVAL: Final[float] = 30.0
#: Задержка при ошибке recv loop.
RECV_LOOP_BACKOFF_DELAY: Final[float] = 0.5


class _Unset:
    """Класс-маркер для обозначения неустановленного значения."""
    pass


#: Маркер неустановленного значения.
UNSET = _Unset()
