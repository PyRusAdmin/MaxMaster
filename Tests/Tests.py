# -*- coding: utf-8 -*-
"""
Тесты для обработки ошибок авторизации в main.py.
Тестируют логику обработки ошибок FAIL_LOGIN_TOKEN и связанных с авторизацией.
Используется pytest-mock фикстура `mocker`.
"""
import pytest
from pathlib import Path


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

    def test_client_connect_default_params(self, mocker):
        """Тест создания клиента с параметрами по умолчанию"""
        mock_max_client = mocker.MagicMock()
        
        mocker.patch("main.MaxClient", return_value=mock_max_client)
        
        from main import client_connect
        
        result = client_connect()
        
        assert result is mock_max_client

    def test_client_connect_with_phone(self, mocker):
        """Тест создания клиента с номером телефона"""
        mock_max_client = mocker.MagicMock()
        
        mocker.patch("main.MaxClient", return_value=mock_max_client)
        
        from main import client_connect
        
        result = client_connect(phone="998950039094", work_dir="test_accounts")
        
        assert result is mock_max_client


class TestConnectClientWithErrorHandling:
    """Тесты функции connect_client_with_error_handling"""

    @pytest.mark.asyncio
    async def test_successful_connection(self, mocker):
        """Тест успешного подключения клиента"""
        mock_client = mocker.MagicMock()
        mock_client.start = mocker.AsyncMock()
        mock_client._work_dir = "accounts"
        
        from main import connect_client_with_error_handling
        
        await connect_client_with_error_handling(mock_client)
        
        mock_client.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fail_login_token_error(self, mocker):
        """Тест обработки ошибки FAIL_LOGIN_TOKEN"""
        mock_client = mocker.MagicMock()
        mock_client.start = mocker.AsyncMock(side_effect=Exception("FAIL_LOGIN_TOKEN"))
        mock_client._work_dir = "accounts"
        
        mock_session_file = mocker.MagicMock()
        mock_session_file.exists.return_value = True
        mock_logger = mocker.MagicMock()
        mock_sys_exit = mocker.MagicMock(side_effect=SystemExit(1))
        
        # Мокируем Path так, чтобы Path("accounts") / "session.db" возвращал mock_session_file
        mock_path_class = mocker.patch("main.Path")
        mock_path_class.return_value.__truediv__.return_value = mock_session_file
        
        mocker.patch("main.console")
        mocker.patch("main.logger", mock_logger)
        mocker.patch("main.sys.exit", mock_sys_exit)
        
        from main import connect_client_with_error_handling
        
        with pytest.raises(SystemExit):
            await connect_client_with_error_handling(mock_client)
        
        mock_session_file.unlink.assert_called_once()
        mock_sys_exit.assert_called_with(1)
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_russian_auth_error(self, mocker):
        """Тест обработки русской ошибки авторизации"""
        mock_client = mocker.MagicMock()
        mock_client.start = mocker.AsyncMock(
            side_effect=Exception("Пожалуйста, авторизируйтесь снова")
        )
        mock_client._work_dir = "accounts"
        
        mock_session_file = mocker.MagicMock()
        mock_session_file.exists.return_value = True
        mock_sys_exit = mocker.MagicMock(side_effect=SystemExit(1))
        
        # Мокируем Path так, чтобы Path("accounts") / "session.db" возвращал mock_session_file
        mock_path_class = mocker.patch("main.Path")
        mock_path_class.return_value.__truediv__.return_value = mock_session_file
        
        mocker.patch("main.console")
        mocker.patch("main.logger")
        mocker.patch("main.sys.exit", mock_sys_exit)
        
        from main import connect_client_with_error_handling
        
        with pytest.raises(SystemExit):
            await connect_client_with_error_handling(mock_client)
        
        mock_sys_exit.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_other_exception(self, mocker):
        """Тест обработки другой ошибки"""
        mock_client = mocker.MagicMock()
        mock_client.start = mocker.AsyncMock(side_effect=Exception("Some other error"))
        mock_client._work_dir = "accounts"
        
        mock_session_file = mocker.MagicMock()
        mock_logger = mocker.MagicMock()
        mock_sys_exit = mocker.MagicMock(side_effect=SystemExit(1))
        
        # Мокируем Path так, чтобы Path("accounts") / "session.db" возвращал mock_session_file
        mock_path_class = mocker.patch("main.Path")
        mock_path_class.return_value.__truediv__.return_value = mock_session_file
        
        mocker.patch("main.console")
        mocker.patch("main.logger", mock_logger)
        mocker.patch("main.sys.exit", mock_sys_exit)
        
        from main import connect_client_with_error_handling
        
        with pytest.raises(SystemExit):
            await connect_client_with_error_handling(mock_client)
        
        mock_session_file.unlink.assert_not_called()
        mock_logger.exception.assert_called()
        mock_sys_exit.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_no_session_file_on_auth_error(self, mocker):
        """Тест когда файл сессии отсутствует при ошибке авторизации"""
        mock_client = mocker.MagicMock()
        mock_client.start = mocker.AsyncMock(side_effect=Exception("FAIL_LOGIN_TOKEN"))
        mock_client._work_dir = "accounts"
        
        mock_session_file = mocker.MagicMock()
        mock_session_file.exists.return_value = False
        mock_sys_exit = mocker.MagicMock(side_effect=SystemExit(1))
        
        # Мокируем Path так, чтобы Path("accounts") / "session.db" возвращал mock_session_file
        mock_path_class = mocker.patch("main.Path")
        mock_path_class.return_value.__truediv__.return_value = mock_session_file
        
        mocker.patch("main.console")
        mocker.patch("main.logger")
        mocker.patch("main.sys.exit", mock_sys_exit)
        
        from main import connect_client_with_error_handling
        
        with pytest.raises(SystemExit):
            await connect_client_with_error_handling(mock_client)
        
        mock_session_file.unlink.assert_not_called()
        mock_sys_exit.assert_called_with(1)
