# -*- coding: utf-8 -*-
import asyncio
import datetime
import re
import sys
from typing import Any
from loguru import logger
import qrcode

from PyMax.src.pymax.payloads import (
    RequestCodePayload, SendCodePayload, RegisterPayload, CheckPasswordChallengePayload, SetPasswordPayload,
    SetHintPayload, RequestEmailCodePayload, SendEmailCodePayload, CreateTrackPayload, SetTwoFactorPayload
)
from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.constant import PHONE_REGEX, _Unset, UNSET
from PyMax.src.pymax.static.enum import AuthType, Opcode, DeviceType, Capability
from PyMax.src.pymax.utils import MixinsUtils


class AuthMixin(ClientProtocol):
    def _check_phone(self) -> bool:
        """
        Проверяет, соответствует ли номер телефона формату PHONE_REGEX.

        :return: True, если номер соответствует формату, иначе False.
        :rtype: bool
        """
        return bool(re.match(PHONE_REGEX, self.phone))

    async def request_code(self, phone: str, language: str = "ru") -> str:
        """
        Запрашивает код аутентификации для указанного номера телефона и возвращает временный токен.

        Метод отправляет запрос на получение кода верификации на переданный номер телефона.
        Используется в процессе аутентификации или регистрации.

        Используется только в пользовательском flow аутентификации.

        :param phone: Номер телефона в международном формате.
        :type phone: str
        :param language: Язык для сообщения с кодом. По умолчанию "ru".
        :type language: str
        :return: Временный токен для дальнейшей аутентификации.
        :rtype: str
        :raises ValueError: Если полученные данные имеют неверный формат.
        :raises Exception: Если сервер вернул ошибку.
        """
        logger.info("Запрос кода аутентификации")

        payload = RequestCodePayload(
            phone=phone, type=AuthType.START_AUTH, language=language
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.AUTH_REQUEST, payload=payload)

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
        Повторно запрашивает код аутентификации для указанного номера телефона и возвращает временный токен.

        :param phone: Номер телефона в международном формате.
        :type phone: str
        :param language: Язык для сообщения с кодом. По умолчанию "ru".
        :type language: str
        :return: Временный токен для дальнейшей аутентификации.
        :rtype: str
        :raises ValueError: Если полученные данные имеют неверный формат.
        :raises Exception: Если сервер вернул ошибку.
        """
        logger.info("Повторная отправка кода аутентификации")

        payload = RequestCodePayload(
            phone=phone, type=AuthType.RESEND, language=language
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.AUTH_REQUEST, payload=payload)

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

        :param code: Код верификации (6 цифр).
        :type code: str
        :param token: Временный токен, полученный из request_code.
        :type token: str
        :return: Словарь с данными ответа сервера, содержащий токены аутентификации.
        :rtype: dict[str, Any]
        :raises ValueError: Если полученные данные имеют неверный формат.
        :raises Exception: Если сервер вернул ошибку.
        """
        logger.info("Отправка кода для верификации")

        payload = SendCodePayload(
            token=token,
            verify_code=code,
            auth_token_type=AuthType.CHECK_CODE,
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.AUTH, payload=payload)

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

        :param qr_link: Ссылка, которая будет закодирована в QR.
        :type qr_link: str
        :return: None
        :rtype: None
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(qr_link)
        qr.make(fit=True)

        qr.print_ascii()

    async def _request_qr_login(self) -> dict[str, Any]:
        logger.info("Запрос QR-данных для входа")

        data = await self._send_and_wait(opcode=Opcode.GET_QR, payload={})

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
        def version_tuple(v: str) -> tuple[int, ...]:
            return tuple(map(int, (v.split("."))))

        return version_tuple(version) >= version_tuple(min_version)

    async def _login(self) -> None:
        logger.info("Запуск процесса входа")

        if self.user_agent.device_type == DeviceType.WEB.value and self._ws:
            if not self._validate_version(self.user_agent.app_version, "25.12.13"):
                logger.error("Ваша версия приложения слишком старая")
                raise ValueError("Ваша версия приложения слишком старая")

            login_resp = await self._login_by_qr()
        else:
            temp_token = await self.request_code(self.phone)
            if not temp_token or not isinstance(temp_token, str):
                logger.critical("Не удалось запросить код: токен отсутствует")
                raise ValueError("Не запросил код")

            print("Введите код: ", end="", flush=True)
            code = await asyncio.to_thread(lambda: sys.stdin.readline().strip())
            if len(code) != 6 or not code.isdigit():
                logger.error("Введён некорректный формат кода")
                raise ValueError("Некорректный формат кода")

            login_resp = await self._send_code(code, temp_token)

        password_challenge = login_resp.get("passwordChallenge")
        login_attrs = login_resp.get("tokenAttrs", {}).get("LOGIN", {})

        if password_challenge and not login_attrs:
            token = await self._two_factor_auth(password_challenge)
        else:
            token = login_attrs.get("token")

        if not token:
            logger.critical("Не удалось войти, токен не получен")
            raise ValueError("Не удалось войти, токен не получен")

        self._token = token
        self._database.update_auth_token((self._device_id), self._token)
        logger.info("Вход успешен, токен сохранен в базе данных")

    async def _poll_qr_login(self, track_id: str, poll_interval: int) -> bool:
        logger.info("Опрос для подтверждения QR-входа")

        while True:
            data = await self._send_and_wait(
                opcode=Opcode.GET_QR_STATUS,
                payload={"trackId": track_id},
            )

            payload = data.get("payload", {})

            if payload.get("error"):
                MixinsUtils.handle_error(data)
            status = payload.get("status")

            if not status:
                logger.warning("Нет статуса в ответе QR-входа")
                continue

            if status.get("loginAvailable"):
                logger.info("QR-логин подтверждён")
                return True
            else:
                exp_at = status.get("expiresAt")
                if (
                        exp_at
                        and isinstance(exp_at, (int, float))
                        and exp_at < datetime.datetime.now().timestamp() * 1000
                ):
                    logger.warning("QR code expired")
                    return False

            await asyncio.sleep(poll_interval / 1000)

    async def _get_qr_login_data(self, track_id: str) -> dict[str, Any]:
        logger.info("Getting QR login data")

        data = await self._send_and_wait(
            opcode=Opcode.LOGIN_BY_QR,
            payload={"trackId": track_id},
        )

        logger.debug(
            "QR login data response opcode=%s seq=%s",
            data.get("opcode"),
            data.get("seq"),
        )
        payload_data = data.get("payload")
        if isinstance(payload_data, dict):
            return payload_data
        else:
            logger.error("Invalid payload data received")
            raise ValueError("Invalid payload data received")

    async def _login_by_qr(self) -> dict[str, Any]:
        data = await self._request_qr_login()

        poll_interval = data.get("pollingInterval")
        link = data.get("qrLink")
        track_id = data.get("trackId")
        expires_at = data.get("expiresAt")

        if not poll_interval or not link or not track_id or not expires_at:
            logger.critical("Invalid QR login data received")
            raise ValueError("Invalid QR login data received")

        logger.info("Starting QR login flow")
        self._print_qr(link)

        poll_qr_task = asyncio.create_task(self._poll_qr_login(track_id, poll_interval))

        while True:
            now_ms = datetime.datetime.now().timestamp() * 1000

            done, pending = await asyncio.wait(
                [poll_qr_task],
                timeout=1,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if now_ms >= expires_at:
                poll_qr_task.cancel()
                logger.error("QR code expired before confirmation")
                raise RuntimeError("QR code expired before confirmation")

            if poll_qr_task in done:
                exc = poll_qr_task.exception()
                if exc is not None:
                    raise exc
                elif poll_qr_task.result():
                    logger.info("QR login successful")

                    data = await self._get_qr_login_data(track_id)

                    return data

                else:
                    logger.error("QR login failed or expired")
                    raise RuntimeError("QR login failed or expired")

    async def _submit_reg_info(
            self, first_name: str, last_name: str | None, token: str
    ) -> dict[str, Any]:
        try:
            logger.info("Submitting registration info")

            payload = RegisterPayload(
                first_name=first_name,
                last_name=last_name,
                token=token,
            ).model_dump(by_alias=True)

            data = await self._send_and_wait(opcode=Opcode.AUTH_CONFIRM, payload=payload)
            if data.get("payload", {}).get("error"):
                MixinsUtils.handle_error(data)

            logger.debug(
                "Registration info response opcode=%s seq=%s",
                data.get("opcode"),
                data.get("seq"),
            )
            payload_data = data.get("payload")
            if isinstance(payload_data, dict):
                return payload_data
            raise ValueError("Invalid payload data received")
        except Exception:
            logger.error("Submit registration info failed", exc_info=True)
            raise RuntimeError("Submit registration info failed")

    async def _register(self, first_name: str, last_name: str | None = None) -> None:
        logger.info("Starting registration flow")

        request_code_payload = await self.request_code(self.phone)
        temp_token = request_code_payload

        if not temp_token or not isinstance(temp_token, str):
            logger.critical("Failed to request code: token missing")
            raise ValueError("Failed to request code")

        print("Введите код: ", end="", flush=True)
        code = await asyncio.to_thread(lambda: sys.stdin.readline().strip())
        if len(code) != 6 or not code.isdigit():
            logger.error("Invalid code format entered")
            raise ValueError("Invalid code format")

        registration_response = await self._send_code(code, temp_token)
        token = registration_response.get("tokenAttrs", {}).get("REGISTER", {}).get("token", "")
        if not token:
            logger.critical("Failed to register, token not received")
            raise ValueError("Failed to register, token not received")

        data = await self._submit_reg_info(first_name, last_name, token)
        self._token = data.get("token")
        if not self._token:
            logger.critical("Failed to register, token not received")
            raise ValueError("Failed to register, token not received")

        logger.info("Registration successful")
        logger.info("Token: %s", self._token)
        logger.warning(
            "IMPORTANT: Use this token ONLY with device_type='DESKTOP' and the special init user agent"
        )
        logger.warning("Этот токен НЕ ДОЛЖЕН использоваться в веб-клиентах")

    async def _check_password(self, password: str, track_id: str) -> dict[str, Any] | None:
        payload = CheckPasswordChallengePayload(
            track_id=track_id,
            password=password,
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.AUTH_LOGIN_CHECK_PASSWORD, payload=payload)

        token_attrs = data.get("payload", {}).get("tokenAttrs", {})
        if data.get("payload", {}).get("error"):
            return None
        return token_attrs

    async def _two_factor_auth(self, password_challenge: dict[str, Any]) -> None:
        logger.info("Начальный поток двухфакторной аутентификации")

        track_id = password_challenge.get("trackId")
        if not track_id:
            logger.critical("Проблема с паролем: отсутствует трек ID")
            raise ValueError("Проблема с паролем: отсутствует трек ID")

        hint = password_challenge.get("hint", "No hint provided")

        while True:
            password = await asyncio.to_thread(
                lambda: input(f"Введите пароль (Подсказка: {hint}): ").strip()
            )
            if not password:
                logger.warning("Пароль пустой, пожалуйста, попробуйте ещё раз")
                continue

            token_attrs = await self._check_password(password, track_id)
            if not token_attrs:
                logger.error("Неправильный пароль, пожалуйста, попробуйте ещё раз")
                continue

            login_attrs = token_attrs.get("LOGIN", {})
            if login_attrs:
                token = login_attrs.get("token")
                if not token:
                    logger.critical("Ответ входа не содержал tokenAttrs.LOGIN.token")
                    raise ValueError("Ответ входа не содержал tokenAttrs.LOGIN.token")
                return token

    async def _set_password(self, password: str, track_id: str) -> bool:
        payload = SetPasswordPayload(
            track_id=track_id,
            password=password,
        ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.AUTH_VALIDATE_PASSWORD, payload=payload)
        payload = data.get("payload", {})
        return not payload

    async def _set_hint(self, hint: str, track_id: str) -> bool:
        payload = SetHintPayload(track_id=track_id, hint=hint, ).model_dump(by_alias=True)

        data = await self._send_and_wait(opcode=Opcode.AUTH_VALIDATE_HINT, payload=payload)
        payload = data.get("payload", {})
        return not payload

    async def _set_email(self, email: str, track_id: str) -> bool:
        payload = RequestEmailCodePayload(
            track_id=track_id,
            email=email,
        )

        data = await self._send_and_wait(
            opcode=Opcode.AUTH_VERIFY_EMAIL,
            payload=payload.model_dump(by_alias=True),
        )

        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        while True:
            verify_code = await asyncio.to_thread(
                lambda: input(f"Введите код подтверждения, отправленный на {email}: ").strip()
            )
            if not verify_code:
                logger.warning("Код проверки пуст, пожалуйста, попробуйте ещё раз")
                continue

            payload = SendEmailCodePayload(
                track_id=track_id,
                verify_code=verify_code,
            )

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
        Устанавливает пароль для аккаунта

        .. warning::
            Метод не будет работать, если на аккаунте уже установлен пароль.

        :param password: Новый пароль для аккаунта.
        :type password: str
        :param email: Адрес электронной почты для восстановления пароля.
        :type email: str
        :param hint: Подсказка для пароля. По умолчанию None.
        :type hint: str | None
        :return: None
        :rtype: None
        """
        logger.info("Установка пароля аккаунта")

        payload = CreateTrackPayload().model_dump(by_alias=True)

        data = await self._send_and_wait(
            opcode=Opcode.AUTH_CREATE_TRACK,
            payload=payload,
        )
        print(data)
        if data.get("payload", {}).get("error"):
            MixinsUtils.handle_error(data)

        track_id = data.get("payload", {}).get("trackId")
        if not track_id:
            logger.critical("Не удалось создать трек пароля: отсутствует идентификатор трека")
            raise ValueError("Не удалось создать трек пароля")

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
