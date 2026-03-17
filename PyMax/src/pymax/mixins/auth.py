# -*- coding: utf-8 -*-
"""
Модуль аутентификации для клиента Max API.

Содержит AuthMixin - класс для управления процессами аутентификации и регистрации:
- Запрос и подтверждение кода верификации по SMS
- Вход по QR-коду (для WEB устройств)
- Регистрация нового пользователя
- Двухфакторная аутентификация (2FA)
- Установка и управление паролем
- Привязка email для восстановления пароля

Пример использования:
    client = MaxClient(phone="79991234567")
    await client.start()  # Автоматический запуск процесса аутентификации
"""
import asyncio
import datetime
import re
import sys
from typing import Any
from loguru import logger
import qrcode  # https://github.com/lincolnloop/python-qrcode

from PyMax.src.pymax.payloads import (
    RequestCodePayload, SendCodePayload, RegisterPayload, CheckPasswordChallengePayload, SetPasswordPayload,
    SetHintPayload, RequestEmailCodePayload, SendEmailCodePayload, CreateTrackPayload, SetTwoFactorPayload
)
from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.constant import PHONE_REGEX, _Unset, UNSET
from PyMax.src.pymax.static.enum import AuthType, Opcode, DeviceType, Capability
from PyMax.src.pymax.utils import MixinsUtils


class AuthMixin(ClientProtocol):
    """
    Mixin для управления аутентификацией и регистрацией в Max API.
    
    Наследуется от ClientProtocol и предоставляет методы для:
    - Запроса кода подтверждения по номеру телефона
    - Повторной отправки кода
    - Подтверждения кода и получения токена
    - Входа по QR-коду (для WEB устройств)
    - Регистрации нового пользователя
    - Двухфакторной аутентификации
    - Установки пароля и привязки email
    
    :cvar PHONE_REGEX: Регулярное выражение для валидации номера телефона.
    """
    
    def _check_phone(self) -> bool:
        """
        Проверяет, соответствует ли номер телефона формату PHONE_REGEX.
        
        Валидация номера выполняется перед отправкой запроса на сервер.
        Ожидаемый формат: 7XXXXXXXXXX (11 цифр, начиная с 7).

        :return: True, если номер соответствует формату, иначе False.
        :rtype: bool
        """
        return bool(re.match(PHONE_REGEX, self.phone))

    async def request_code(self, phone: str, language: str = "ru") -> str:
        """
        Запрашивает код аутентификации для указанного номера телефона и возвращает временный токен.

        Метод отправляет запрос на получение кода верификации на переданный номер телефона.
        Код отправляется через SMS или push-уведомление.
        Используется в процессе аутентификации или регистрации.

        .. note::
            Используется только в пользовательском flow аутентификации.

        :param phone: Номер телефона в международном формате (например, '79991234567').
        :type phone: str
        :param language: Язык для сообщения с кодом. По умолчанию "ru".
        :type language: str, optional
        :return: Временный токен для дальнейшей аутентификации.
        :rtype: str
        :raises ValueError: Если полученные данные имеют неверный формат.
        :raises Exception: Если сервер вернул ошибку.
        
        Пример:
            >>> token = await client.request_code("79991234567")
            >>> print(f"Временный токен: {token}")
        """
        logger.info("Запрос кода аутентификации")

        # Формируем payload для запроса кода
        payload = RequestCodePayload(
            phone=phone, type=AuthType.START_AUTH, language=language
        ).model_dump(by_alias=True)

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(opcode=Opcode.AUTH_REQUEST, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug(
            "Код запроса кода на ответ=%s seq=%s",
            data.get("opcode"),
            data.get("seq"),
        )
        payload_data = data.get("payload")
        if isinstance(payload_data, dict):
            return payload_data["token"]
        else:
            logger.error("Полученные некорректные данные полезной нагрузки")
            raise ValueError("Полученные некорректные данные полезной нагрузки")

    async def resend_code(self, phone: str, language: str = "ru") -> str:
        """
        Повторно запрашивает код аутентификации для указанного номера телефона.

        Используется, если пользователь не получил код при первом запросе.
        Возвращает новый временный токен для дальнейшей аутентификации.

        :param phone: Номер телефона в международном формате.
        :type phone: str
        :param language: Язык для сообщения с кодом. По умолчанию "ru".
        :type language: str, optional
        :return: Временный токен для дальнейшей аутентификации.
        :rtype: str
        :raises ValueError: Если полученные данные имеют неверный формат.
        :raises Exception: Если сервер вернул ошибку.
        """
        logger.info("Повторная отправка кода аутентификации")

        # Формируем payload для повторной отправки кода
        payload = RequestCodePayload(
            phone=phone, type=AuthType.RESEND, language=language
        ).model_dump(by_alias=True)

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(opcode=Opcode.AUTH_REQUEST, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug(
            "Код повторной отправки ответа=%s seq=%s",
            data.get("opcode"),
            data.get("seq"),
        )
        payload_data = data.get("payload")
        if isinstance(payload_data, dict):
            return payload_data["token"]
        else:
            logger.error("Полученные некорректные данные полезной нагрузки")
            raise ValueError("Полученные некорректные данные полезной нагрузки")

    async def _send_code(self, code: str, token: str) -> dict[str, Any]:
        """
        Отправляет код верификации на сервер для подтверждения.

        Внутренний метод, используемый после получения кода от пользователя.
        Проверяет 6-значный код и возвращает токены аутентификации.

        :param code: Код верификации (6 цифр), полученный из SMS/push.
        :type code: str
        :param token: Временный токен, полученный из request_code.
        :type token: str
        :return: Словарь с данными ответа сервера, содержащий токены аутентификации.
        :rtype: dict[str, Any]
        :raises ValueError: Если полученные данные имеют неверный формат.
        :raises Exception: Если сервер вернул ошибку.
        """
        logger.info("Отправка кода для верификации")

        # Формируем payload для проверки кода
        payload = SendCodePayload(
            token=token,
            verify_code=code,
            auth_token_type=AuthType.CHECK_CODE,
        ).model_dump(by_alias=True)

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(opcode=Opcode.AUTH, payload=payload)

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug(
            "Отправка кода ответа операции=%s seq=%s",
            data.get("opcode"),
            data.get("seq"),
        )
        payload_data = data.get("payload")
        if isinstance(payload_data, dict):
            return payload_data
        else:
            logger.error("Полученные некорректные данные полезной нагрузки")
            raise ValueError("Полученные некорректные данные полезной нагрузки")

    def _print_qr(self, qr_link: str) -> None:
        """
        Генерирует и выводит QR-код в консоль в ASCII-формате.

        Используется для отображения QR-кода при входе через QR.
        Пользователь должен отсканировать этот код в мобильном приложении Max.

        :param qr_link: Ссылка, которая будет закодирована в QR.
        :type qr_link: str
        :return: None
        :rtype: None
        
        Пример вывода:
            ██████  ████████    ██████  ██████
            ██  ██  ██    ██    ██  ██  ██  ██
            ██████  ████████    ██████  ██  ██
        """
        # Создаём объект QRCode с настройками
        qr = qrcode.QRCode(
            version=1,  # Размер QR-кода (1 = 21x21 модулей)
            error_correction=qrcode.ERROR_CORRECT_L,  # Низкий уровень коррекции ошибок
            box_size=1,  # Размер одного модуля
            border=1,  # Ширина рамки
        )
        qr.add_data(qr_link)  # Добавляем данные
        qr.make(fit=True)  # Оптимизируем размер

        qr.print_ascii()  # Вывод QR-кода в консоль в ASCII-формате

    async def _request_qr_login(self) -> dict[str, Any]:
        """
        Запрашивает данные для входа по QR-коду.

        Внутренний метод, возвращает ссылку для генерации QR-кода,
        track_id для отслеживания статуса и время истечения.

        :return: Словарь с данными для QR-входа (qrLink, trackId, expiresAt, pollingInterval).
        :rtype: dict[str, Any]
        :raises ValueError: Если сервер вернул некорректные данные.
        """
        logger.info("Запрос QR-данных для входа")

        # Отправляем запрос на получение данных для QR-входа
        data = await self._send_and_wait(opcode=Opcode.GET_QR, payload={})

        # Проверяем наличие ошибки в ответе
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        logger.debug(
            "Оперативный код ответа на QR-данные входа=%s seq=%s",
            data.get("opcode"),
            data.get("seq"),
        )
        payload_data = data.get("payload")
        if isinstance(payload_data, dict):
            return payload_data
        else:
            logger.error("Полученные некорректные данные полезной нагрузки")
            raise ValueError("Полученные некорректные данные полезной нагрузки")

    def _validate_version(self, version: str, min_version: str) -> bool:
        """
        Проверяет, соответствует ли версия приложения минимально требуемой.

        Используется для проверки совместимости клиента с API сервера.
        Сравнивает версии покомпонентно (major.minor.patch).

        :param version: Текущая версия приложения.
        :type version: str
        :param min_version: Минимально требуемая версия.
        :type min_version: str
        :return: True, если версия соответствует или выше, иначе False.
        :rtype: bool
        
        Пример:
            >>> client._validate_version("25.12.13", "25.0.0")
            True
        """
        def version_tuple(v: str) -> tuple[int, ...]:
            # Преобразует строку версии в кортеж чисел
            return tuple(map(int, (v.split("."))))

        return version_tuple(version) >= version_tuple(min_version)

    async def _login(self) -> None:
        """
        Запускает процесс входа в аккаунт.

        Внутренний метод, который выбирает способ аутентификации:
        - Для WEB устройств: вход по QR-коду
        - Для других устройств: вход по коду из SMS

        После успешного входа сохраняет токен в базу данных.

        :raises ValueError: Если версия приложения слишком старая или токен не получен.
        :raises Exception: Если произошла ошибка при входе.
        """
        logger.info("Запуск процесса входа")

        # Проверяем тип устройства и выбираем способ аутентификации
        if self.user_agent.device_type == DeviceType.WEB.value and self._ws:
            # Для WEB проверяем минимальную версию приложения
            if not self._validate_version(self.user_agent.app_version, "25.12.13"):
                logger.error("Ваша версия приложения слишком старая")
                raise ValueError("Ваша версия приложения слишком старая")

            # Вход по QR-коду
            login_resp = await self._login_by_qr()
        else:
            # Вход по коду из SMS
            temp_token = await self.request_code(self.phone)
            if not temp_token or not isinstance(temp_token, str):
                logger.critical("Не удалось запросить код: токен отсутствует")
                raise ValueError("Не запросил код")

            # Запрашиваем код у пользователя
            print("Введите код: ", end="", flush=True)
            code = await asyncio.to_thread(lambda: sys.stdin.readline().strip())
            if len(code) != 6 or not code.isdigit():
                logger.error("Введён некорректный формат кода")
                raise ValueError("Некорректный формат кода")

            # Отправляем код на сервер
            login_resp = await self._send_code(code, temp_token)

        # Проверяем наличие двухфакторной аутентификации
        password_challenge = login_resp.get("passwordChallenge")
        login_attrs = login_resp.get("tokenAttrs", {}).get("LOGIN", {})

        if password_challenge and not login_attrs:
            # Требуется 2FA
            token = await self._two_factor_auth(password_challenge)
        else:
            # Обычный вход
            token = login_attrs.get("token")

        if not token:
            logger.critical("Не удалось войти, токен не получен")
            raise ValueError("Не удалось войти, токен не получен")

        # Сохраняем токен в базу данных
        self._token = token
        self._database.update_auth_token((self._device_id), self._token)
        logger.info("Вход успешен, токен сохранен в базе данных")

    async def _poll_qr_login(self, track_id: str, poll_interval: int) -> bool:
        """
        Опрашивает сервер для подтверждения QR-входа.

        Внутренний метод, который периодически проверяет статус QR-кода.
        Возвращает True, когда пользователь отсканировал QR-код и подтвердил вход.

        :param track_id: ID трека для отслеживания статуса QR-входа.
        :type track_id: str
        :param poll_interval: Интервал опроса в миллисекундах.
        :type poll_interval: int
        :return: True, если вход подтверждён, иначе False.
        :rtype: bool
        """
        logger.info("Опрос для подтверждения QR-входа")

        while True:
            # Запрашиваем статус QR-входа
            data = await self._send_and_wait(
                opcode=Opcode.GET_QR_STATUS,
                payload={"trackId": track_id},
            )

            payload = data.get("payload", {})

            # Проверяем наличие ошибки
            if payload.get("error"):
                MixinsUtils.handle_error(data)
            
            status = payload.get("status")

            if not status:
                logger.warning("Нет статуса в ответе QR-входа")
                continue

            # Проверяем, доступен ли вход
            if status.get("loginAvailable"):
                logger.info("QR-логин подтверждён")
                return True
            else:
                # Проверяем, не истёк ли QR-код
                exp_at = status.get("expiresAt")
                if (
                        exp_at
                        and isinstance(exp_at, (int, float))
                        and exp_at < datetime.datetime.now().timestamp() * 1000
                ):
                    logger.warning("QR-код просрочен")
                    return False

            # Ждём перед следующим опросом
            await asyncio.sleep(poll_interval / 1000)

    async def _get_qr_login_data(self, track_id: str) -> dict[str, Any]:
        """
        Получает данные для входа по QR-коду после подтверждения.

        Внутренний метод, вызываемый после успешного сканирования QR-кода.
        Возвращает токены аутентификации.

        :param track_id: ID трека QR-входа.
        :type track_id: str
        :return: Словарь с данными входа (токены и др.).
        :rtype: dict[str, Any]
        :raises ValueError: Если сервер вернул некорректные данные.
        """
        logger.info("Получение QR-данных входа")

        # Запрашиваем финальные данные для входа
        data = await self._send_and_wait(
            opcode=Opcode.LOGIN_BY_QR,
            payload={"trackId": track_id},
        )

        logger.debug(
            "Оперативный код ответа на QR-данные входа=%s seq=%s",
            data.get("opcode"),
            data.get("seq"),
        )
        payload_data = data.get("payload")
        if isinstance(payload_data, dict):
            return payload_data
        else:
            logger.error("Полученные некорректные данные полезной нагрузки")
            raise ValueError("Полученные некорректные данные полезной нагрузки")

    async def _login_by_qr(self) -> dict[str, Any]:
        """
        Выполняет процесс входа по QR-коду.

        Внутренний метод, который:
        1. Запрашивает данные для QR-входа
        2. Отображает QR-код в консоли
        3. Ожидает подтверждения от пользователя
        4. Получает токены аутентификации

        :return: Словарь с данными входа (токены).
        :rtype: dict[str, Any]
        :raises ValueError: Если данные QR-входа некорректны.
        :raises RuntimeError: Если QR-код истёк или вход не удался.
        """
        # Запрашиваем данные для QR-входа
        data = await self._request_qr_login()

        # Извлекаем параметры
        poll_interval = data.get("pollingInterval")
        link = data.get("qrLink")
        track_id = data.get("trackId")
        expires_at = data.get("expiresAt")

        # Проверяем наличие всех необходимых данных
        if not poll_interval or not link or not track_id or not expires_at:
            logger.critical("Получены некорректные данные QR-входа")
            raise ValueError("Получены некорректные данные QR-входа")

        logger.info("Запуск процесса входа в QR")
        self._print_qr(link)  # Отображаем QR-код

        # Создаём задачу для опроса статуса QR-входа
        poll_qr_task = asyncio.create_task(self._poll_qr_login(track_id, poll_interval))

        while True:
            now_ms = datetime.datetime.now().timestamp() * 1000

            # Ждём завершения задачи опроса или таймаута
            done, pending = await asyncio.wait(
                [poll_qr_task],
                timeout=1,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Проверяем, не истёк ли QR-код
            if now_ms >= expires_at:
                poll_qr_task.cancel()
                logger.error("QR-код истёк до подтверждения")
                raise RuntimeError("QR-код истёк до подтверждения")

            # Проверяем результат задачи опроса
            if poll_qr_task in done:
                exc = poll_qr_task.exception()
                if exc is not None:
                    raise exc
                elif poll_qr_task.result():
                    logger.info("QR-вход успешен")

                    # Получаем финальные данные входа
                    data = await self._get_qr_login_data(track_id)

                    return data

                else:
                    logger.error("QR-вход не удался или истек.")
                    raise RuntimeError("QR-вход не удался или истек.")

    async def _submit_reg_info(
            self, first_name: str, last_name: str | None, token: str
    ) -> dict[str, Any]:
        """
        Отправляет регистрационные данные на сервер.

        Внутренний метод, используемый при регистрации нового пользователя.
        Сохраняет имя и фамилию в профиле пользователя.

        :param first_name: Имя пользователя.
        :type first_name: str
        :param last_name: Фамилия пользователя (может быть None).
        :type last_name: str | None
        :param token: Токен регистрации.
        :type token: str
        :return: Словарь с данными ответа сервера.
        :rtype: dict[str, Any]
        :raises ValueError: Если данные некорректны.
        :raises RuntimeError: Если отправка не удалась.
        """
        try:
            logger.info("Отправка регистрационных данных")

            # Формируем payload для регистрации
            payload = RegisterPayload(
                first_name=first_name,
                last_name=last_name,
                token=token,
            ).model_dump(by_alias=True)

            # Отправляем запрос и ждём ответ
            data = await self._send_and_wait(opcode=Opcode.AUTH_CONFIRM, payload=payload)
            if data.get("payload", {}).get("error"):
                MixinsUtils.handle_error(data)

            logger.debug(
                "Регистрационная информация ответ opcode=%s seq=%s",
                data.get("opcode"),
                data.get("seq"),
            )
            payload_data = data.get("payload")
            if isinstance(payload_data, dict):
                return payload_data
            raise ValueError("Полученные некорректные данные полезной нагрузки")
        except Exception:
            logger.error("Отправка регистрационных данных не получила", exc_info=True)
            raise RuntimeError("Отправка регистрационных данных не получила")

    async def _register(self, first_name: str, last_name: str | None = None) -> None:
        """
        Выполняет процесс регистрации нового пользователя.

        Внутренний метод, который:
        1. Запрашивает код подтверждения на номер телефона
        2. Проверяет код
        3. Отправляет регистрационные данные (имя, фамилия)
        4. Сохраняет токен регистрации

        :param first_name: Имя пользователя.
        :type first_name: str
        :param last_name: Фамилия пользователя (необязательно).
        :type last_name: str | None
        :raises ValueError: Если код некорректен или токен не получен.
        :raises RuntimeError: Если регистрация не удалась.
        """
        logger.info("Начальный процесс регистрации")

        # Запрашиваем код подтверждения
        request_code_payload = await self.request_code(self.phone)
        temp_token = request_code_payload

        if not temp_token or not isinstance(temp_token, str):
            logger.critical("Не удалось запросить код: токен отсутствует")
            raise ValueError("Не запросил код")

        # Запрашиваем код у пользователя
        print("Введите код: ", end="", flush=True)
        code = await asyncio.to_thread(lambda: sys.stdin.readline().strip())
        if len(code) != 6 or not code.isdigit():
            logger.error("Введён некорректный формат кода")
            raise ValueError("Некорректный формат кода")

        # Отправляем код на сервер
        registration_response = await self._send_code(code, temp_token)
        token = registration_response.get("tokenAttrs", {}).get("REGISTER", {}).get("token", "")
        if not token:
            logger.critical("Не удалось зарегистрироваться, токен не получен")
            raise ValueError("Не удалось зарегистрироваться, токен не получен")

        # Отправляем регистрационные данные
        data = await self._submit_reg_info(first_name, last_name, token)
        self._token = data.get("token")
        if not self._token:
            logger.critical("Не удалось зарегистрироваться, токен не получен")
            raise ValueError("Не удалось зарегистрироваться, токен не получен")

        logger.info("Регистрация прошла успешно")
        logger.info("Token: %s", self._token)
        logger.warning(
            "ВАЖНО: Используйте этот токен ТОЛЬКО с device_type='DESKTOP' и специальным init user agent"
        )
        logger.warning("Этот токен НЕ ДОЛЖЕН использоваться в веб-клиентах")

    async def _check_password(self, password: str, track_id: str) -> dict[str, Any] | None:
        """
        Проверяет пароль для двухфакторной аутентификации.

        Внутренний метод, используемый при входе с включённым 2FA.

        :param password: Пароль пользователя.
        :type password: str
        :param track_id: ID трека аутентификации.
        :type track_id: str
        :return: Токены аутентификации или None, если пароль неверный.
        :rtype: dict[str, Any] | None
        """
        # Формируем payload для проверки пароля
        payload = CheckPasswordChallengePayload(
            track_id=track_id,
            password=password,
        ).model_dump(by_alias=True)

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(opcode=Opcode.AUTH_LOGIN_CHECK_PASSWORD, payload=payload)

        token_attrs = data.get("payload", {}).get("tokenAttrs", {})
        if data.get("payload", {}).get("error"):
            return None
        return token_attrs

    async def _two_factor_auth(self, password_challenge: dict[str, Any]) -> None:
        """
        Выполняет процесс двухфакторной аутентификации.

        Внутренний метод, который запрашивает пароль у пользователя
        и проверяет его до получения токена входа.

        :param password_challenge: Данные вызова пароля (trackId, hint).
        :type password_challenge: dict[str, Any]
        :return: Токен аутентификации.
        :rtype: str
        :raises ValueError: Если trackId отсутствует или токен не получен.
        """
        logger.info("Начальный поток двухфакторной аутентификации")

        # Извлекаем trackId
        track_id = password_challenge.get("trackId")
        if not track_id:
            logger.critical("Проблема с паролем: отсутствует трек ID")
            raise ValueError("Проблема с паролем: отсутствует трек ID")

        # Получаем подсказку к паролю
        hint = password_challenge.get("hint", "No hint provided")

        while True:
            # Запрашиваем пароль у пользователя
            password = await asyncio.to_thread(
                lambda: input(f"Введите пароль (Подсказка: {hint}): ").strip()
            )
            if not password:
                logger.warning("Пароль пустой, пожалуйста, попробуйте ещё раз")
                continue

            # Проверяем пароль
            token_attrs = await self._check_password(password, track_id)
            if not token_attrs:
                logger.error("Неправильный пароль, пожалуйста, попробуйте ещё раз")
                continue

            # Извлекаем токен входа
            login_attrs = token_attrs.get("LOGIN", {})
            if login_attrs:
                token = login_attrs.get("token")
                if not token:
                    logger.critical("Ответ входа не содержал tokenAttrs.LOGIN.token")
                    raise ValueError("Ответ входа не содержал tokenAttrs.LOGIN.token")
                return token

    async def _set_password(self, password: str, track_id: str) -> bool:
        """
        Устанавливает пароль для аккаунта.

        Внутренний метод, используемый при настройке двухфакторной аутентификации.

        :param password: Пароль для установки.
        :type password: str
        :param track_id: ID трека аутентификации.
        :type track_id: str
        :return: True, если пароль установлен успешно, иначе False.
        :rtype: bool
        """
        # Формируем payload для установки пароля
        payload = SetPasswordPayload(
            track_id=track_id,
            password=password,
        ).model_dump(by_alias=True)

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(opcode=Opcode.AUTH_VALIDATE_PASSWORD, payload=payload)
        payload = data.get("payload", {})
        return not payload  # Возвращаем True, если ошибок нет

    async def _set_hint(self, hint: str, track_id: str) -> bool:
        """
        Устанавливает подсказку к паролю.

        Внутренний метод, используемый при настройке двухфакторной аутентификации.

        :param hint: Текст подсказки.
        :type hint: str
        :param track_id: ID трека аутентификации.
        :type track_id: str
        :return: True, если подсказка установлена успешно, иначе False.
        :rtype: bool
        """
        # Формируем payload для установки подсказки
        payload = SetHintPayload(track_id=track_id, hint=hint, ).model_dump(by_alias=True)

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(opcode=Opcode.AUTH_VALIDATE_HINT, payload=payload)
        payload = data.get("payload", {})
        return not payload  # Возвращаем True, если ошибок нет

    async def _set_email(self, email: str, track_id: str) -> bool:
        """
        Привязывает email для восстановления пароля.

        Внутренний метод, который:
        1. Отправляет код подтверждения на email
        2. Запрашивает код у пользователя
        3. Проверяет код

        :param email: Адрес электронной почты.
        :type email: str
        :param track_id: ID трека аутентификации.
        :type track_id: str
        :return: True, если email привязан успешно, иначе False.
        :rtype: bool
        """
        # Формируем payload для запроса кода на email
        payload = RequestEmailCodePayload(
            track_id=track_id,
            email=email,
        )

        # Отправляем запрос и ждём ответ
        data = await self._send_and_wait(
            opcode=Opcode.AUTH_VERIFY_EMAIL,
            payload=payload.model_dump(by_alias=True),
        )

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Запрашиваем код подтверждения у пользователя
        while True:
            verify_code = await asyncio.to_thread(
                lambda: input(f"Введите код подтверждения, отправленный на {email}: ").strip()
            )
            if not verify_code:
                logger.warning("Код проверки пуст, пожалуйста, попробуйте ещё раз")
                continue

            # Формируем payload для проверки кода
            payload = SendEmailCodePayload(
                track_id=track_id,
                verify_code=verify_code,
            )

            # Отправляем запрос и ждём ответ
            data = await self._send_and_wait(
                opcode=Opcode.AUTH_CHECK_EMAIL,
                payload=payload.model_dump(by_alias=True),
            )

            if data.get("payload", {}).get("error"):
                logger.error("Неправильный код подтверждения, пожалуйста, попробуйте ещё раз")
                continue

            return True

    async def set_password(self, password: str, email: str | None = None, hint: str | None | _Unset = UNSET):
        """
        Устанавливает пароль для аккаунта.

        Метод настраивает двухфакторную аутентификацию:
        1. Создаёт трек аутентификации
        2. Устанавливает пароль
        3. Устанавливает подсказку к паролю (опционально)
        4. Привязывает email для восстановления (опционально)

        .. warning::
            Метод не будет работать, если на аккаунте уже установлен пароль.

        :param password: Новый пароль для аккаунта. Если пустой, будет запрошен у пользователя.
        :type password: str
        :param email: Адрес электронной почты для восстановления пароля. Если пустой, будет запрошен у пользователя.
        :type email: str | None, optional
        :param hint: Подсказка для пароля. По умолчанию None (будет запрошена у пользователя).
        :type hint: str | None | _Unset, optional
        :return: True, если пароль установлен успешно.
        :rtype: bool
        :raises ValueError: Если не удалось создать трек аутентификации.
        
        Пример:
            >>> await client.set_password("MySecurePassword123", email="user@example.com", hint="Любимое животное")
            True
        """
        logger.info("Установка пароля аккаунта")

        # Создаём трек для настройки 2FA
        payload = CreateTrackPayload().model_dump(by_alias=True)

        data = await self._send_and_wait(
            opcode=Opcode.AUTH_CREATE_TRACK,
            payload=payload,
        )
        print(data)
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        # Извлекаем trackId
        track_id = data.get("payload", {}).get("trackId")
        if not track_id:
            logger.critical("Не удалось создать трек пароля: отсутствует идентификатор трека")
            raise ValueError("Не удалось создать трек пароля")

        # Устанавливаем пароль
        while True:
            if not password:
                password = await asyncio.to_thread(lambda: input("Введите пароль: ").strip())
                if not password:
                    logger.warning("Пароль пустой, пожалуйста, попробуйте ещё раз")
                    continue

            success = await self._set_password(password, track_id)
            if success:
                logger.info("Пароль установлен успешно")
                break
            else:
                logger.error("Не удалось установить пароль, пожалуйста, попробуйте снова")

        # Устанавливаем подсказку к паролю
        while True:
            if hint is UNSET:
                hint = await asyncio.to_thread(
                    lambda: input("Введите подсказку для пароля (пустая - пропустить): ").strip()
                )
                if not hint:
                    break

            if hint is None:
                break

            success = await self._set_hint(hint, track_id)
            if success:
                logger.info("Подсказка пароля успешно установлена")
                break
            else:
                logger.error("Не удалось настроить подсказку пароля, пожалуйста, попробуйте ещё раз")

        # Привязываем email для восстановления
        while True:
            if not email:
                email = await asyncio.to_thread(
                    lambda: input("Введите email для восстановления пароля: ").strip()
                )
                if not email:
                    logger.warning("Электронная почта пустая, пожалуйста, попробуйте ещё раз")
                    continue

            success = await self._set_email(email, track_id)
            if success:
                logger.info("Восстановление электронной почты успешно установлены")
                break

        # Финализируем настройку 2FA
        payload = SetTwoFactorPayload(
            expected_capabilities=[
                Capability.DEFAULT,
                Capability.SECOND_FACTOR_HAS_HINT,
                Capability.SECOND_FACTOR_HAS_EMAIL,
            ],
            track_id=track_id,
            password=password,
            hint=hint if isinstance(hint, (str, type(None))) else None,
        )

        data = await self._send_and_wait(
            opcode=Opcode.AUTH_SET_2FA,
            payload=payload.model_dump(by_alias=True),
        )
        payload = data.get("payload", {})
        if payload and payload.get("error"):
            MixinsUtils.handle_error(data)

        return True
