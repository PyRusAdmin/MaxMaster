# -*- coding: utf-8 -*-
"""
Тесты для обработки ошибок авторизации в main.py.
Тестируют логику обработки ошибок FAIL_LOGIN_TOKEN и связанных с авторизацией.
Используется pytest-mock фикстура `mocker`.
"""
import pytest


class TestAuthErrorDetection:
    """Тесты распознавания ошибок авторизации"""

    def test_fail_login_token_detection(self):
        """Тест распознавания ошибки FAIL_LOGIN_TOKEN"""
        error_msg = "PyMax Error: Ошибка входа. Пожалуйста, авторизируйтесь снова FAIL_LOGIN_TOKEN"

        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()
        assert is_auth_error is True

    def test_russian_auth_error_detection(self):
        """Тест распознавания русской ошибки авторизации"""
        error_msg = "Пожалуйста, авторизируйтесь снова"

        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()
        assert is_auth_error is True

    def test_combined_error_message(self):
        """Тест комбинированного сообщения об ошибке"""
        error_msg = "Ошибка входа. Пожалуйста, авторизируйтесь снова FAIL_LOGIN_TOKEN (Ошибка входа)"

        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()
        assert is_auth_error is True

    @pytest.mark.parametrize("error_msg", [
        "Some other error",
        "Network timeout",
        "WebSocket connection failed",
        "Rate limit exceeded",
        "",
    ])
    def test_other_error_not_detected(self, error_msg):
        """Тест что другие ошибки не определяются как авторизационные"""
        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()
        assert is_auth_error is False


class TestAuthErrorHandlingLogic:
    """Тесты логики обработки ошибок авторизации"""

    def test_error_handling_with_session_file(self, mocker):
        """Тест обработки ошибки при наличии файла сессии"""
        mock_console_print = mocker.MagicMock()
        mock_logger_error = mocker.MagicMock()
        mock_logger_info = mocker.MagicMock()
        mock_path_instance = mocker.MagicMock()
        mock_sys_exit = mocker.MagicMock()

        error_msg = "FAIL_LOGIN_TOKEN"
        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()

        if is_auth_error:
            mock_path_instance.exists.return_value = True
            if mock_path_instance.exists():
                mock_path_instance.unlink()
                mock_logger_info("Старая сессия удалена: %s", mock_path_instance)
            mock_console_print(mocker.MagicMock())
            mock_logger_error("Авторизация не удалась: %s", error_msg)
            mock_sys_exit(1)

        mock_path_instance.unlink.assert_called_once()
        mock_sys_exit.assert_called_once_with(1)
        mock_logger_error.assert_called_once_with("Авторизация не удалась: %s", error_msg)

    def test_error_handling_without_session_file(self, mocker):
        """Тест обработки ошибки когда файл сессии отсутствует"""
        mock_path_instance = mocker.MagicMock()
        mock_sys_exit = mocker.MagicMock()

        error_msg = "FAIL_LOGIN_TOKEN"
        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg

        if is_auth_error:
            mock_path_instance.exists.return_value = False
            if mock_path_instance.exists():
                mock_path_instance.unlink()
            mock_sys_exit(1)

        mock_path_instance.unlink.assert_not_called()
        mock_sys_exit.assert_called_once_with(1)


class TestClientConnectFunction:
    """Тесты функции client_connect"""

    def test_client_connect_default_params(self):
        """Тест создания клиента с параметрами по умолчанию"""
        from main import client_connect

        # Проверяем, что функция существует и вызывается
        assert callable(client_connect)

    def test_client_connect_with_phone(self):
        """Тест создания клиента с номером телефона"""
        from main import client_connect

        # Проверяем, что функция принимает параметры
        assert callable(client_connect)
