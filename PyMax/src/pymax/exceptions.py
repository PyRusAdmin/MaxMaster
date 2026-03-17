# -*- coding: utf-8 -*-
"""
Модуль исключений для клиента Max API.

Содержит классы исключений для обработки ошибок:
- InvalidPhoneError: неверный формат номера телефона
- WebSocketNotConnectedError: WebSocket не подключён
- SocketNotConnectedError: сокет не подключён
- SocketSendError: ошибка отправки через сокет
- ResponseError: ошибка в ответе сервера
- ResponseStructureError: неверная структура ответа
- Error: базовое исключение PyMax
- RateLimitError: превышение лимита запросов
- LoginError: ошибка авторизации
"""


class InvalidPhoneError(Exception):
    """
    Исключение, вызываемое при неверном формате номера телефона.
    
    Возникает, если номер телефона не соответствует ожидаемому формату.

    :param phone: Некорректный номер телефона.
    :type phone: str
    """

    def __init__(self, phone: str) -> None:
        super().__init__(f"Invalid phone number format: {phone}")


class WebSocketNotConnectedError(Exception):
    """
    Исключение, вызываемое при попытке обращения к WebSocket,
    если соединение не установлено.
    
    Возникает при попытке отправить сообщение или выполнить запрос
    через неподключённое WebSocket соединение.
    """
    def __init__(self) -> None:
        super().__init__("WebSocket is not connected")


class SocketNotConnectedError(Exception):
    """
    Исключение, вызываемое при попытке обращения к сокету,
    если соединение не установлено.
    
    Возникает при попытке отправить данные через неподключённый сокет.
    """
    def __init__(self) -> None:
        super().__init__("Socket is not connected")


class SocketSendError(Exception):
    """
    Исключение, вызываемое при ошибке отправки данных через сокет.
    
    Возникает, если отправка данных через сокет завершилась ошибкой.
    """
    def __init__(self) -> None:
        super().__init__("Send and wait failed (socket)")


class ResponseError(Exception):
    """
    Исключение, вызываемое при ошибке в ответе от сервера.
    
    Возникает, если сервер вернул ответ с ошибкой.
    """
    def __init__(self, message: str) -> None:
        super().__init__(f"Response error: {message}")


class ResponseStructureError(Exception):
    """
    Исключение, вызываемое при неверной структуре ответа от сервера.
    
    Возникает, если структура ответа сервера не соответствует ожидаемой.
    """
    def __init__(self, message: str) -> None:
        super().__init__(f"Response structure error: {message}")


class Error(Exception):
    """
    Базовое исключение для ошибок PyMax.
    
    Содержит информацию об ошибке: код, сообщение, заголовок.
    Используется как основа для специфичных исключений (RateLimitError, LoginError).
    """
    def __init__(self, error: str, message: str, title: str, localized_message: str | None = None, ) -> None:
        """
        Инициализирует исключение.

        :param error: Код ошибки.
        :type error: str
        :param message: Сообщение об ошибке.
        :type message: str
        :param title: Заголовок ошибки.
        :type title: str
        :param localized_message: Локализованное сообщение.
        :type localized_message: str | None
        """
        self.error = error
        self.message = message
        self.title = title
        self.localized_message = localized_message

        # Формируем полное сообщение об ошибке
        parts = []
        if localized_message:
            parts.append(localized_message)
        if message:
            parts.append(message)
        if title:
            parts.append(f"({title})")
        parts.append(f"[{error}]")

        super().__init__("PyMax Error: " + " ".join(parts))


class RateLimitError(Error):
    """
    Исключение, вызываемое при превышении лимита запросов.
    
    Возникает, когда клиент отправляет слишком много запросов
    за короткий промежуток времени.
    """
    def __init__(self, error: str, message: str, title: str, localized_message: str | None = None) -> None:
        super().__init__(error, message, title, localized_message)


class LoginError(Error):
    """
    Исключение, вызываемое при ошибке авторизации.
    
    Возникает при неудачной попытке входа в аккаунт:
    - Неверный код подтверждения
    - Неверный токен
    - Ошибка сервера при авторизации
    """
    def __init__(self, error: str, message: str, title: str, localized_message: str | None = None) -> None:
        super().__init__(error, message, title, localized_message)
