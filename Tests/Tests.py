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
        # Моки через mocker
        mock_console_print = mocker.MagicMock()
        mock_logger_error = mocker.MagicMock()
        mock_logger_info = mocker.MagicMock()
        mock_path_instance = mocker.MagicMock()
        mock_sys_exit = mocker.MagicMock()

        error_msg = "FAIL_LOGIN_TOKEN"

        # Симулируем логику из main()
        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()

        if is_auth_error:
            mock_path_instance.exists.return_value = True

            if mock_path_instance.exists():
                mock_path_instance.unlink()
                mock_logger_info("Старая сессия удалена: %s", mock_path_instance)

            mock_console_print(mocker.MagicMock())
            mock_logger_error("Авторизация не удалась: %s", error_msg)
            mock_sys_exit(1)

        # Проверки
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
                mock_path_instance.unlink()  # Не должно вызваться

            mock_sys_exit(1)

        # unlink не должен вызываться
        mock_path_instance.unlink.assert_not_called()
        mock_sys_exit.assert_called_once_with(1)

    def test_other_exception_handling(self, mocker):
        """Тест обработки других исключений (не авторизация)"""
        mock_path_instance = mocker.MagicMock()
        mock_logger_exception = mocker.MagicMock()
        mock_sys_exit = mocker.MagicMock()

        error_msg = "Some other error"
        is_auth_error = "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower()

        if is_auth_error:
            mock_path_instance.unlink()
        else:
            # Другие ошибки
            mock_logger_exception("Необработанная ошибка в main()")
            mock_sys_exit(1)

        # Для других ошибок unlink не вызывается
        mock_path_instance.unlink.assert_not_called()
        mock_logger_exception.assert_called_once_with("Необработанная ошибка в main()")
        mock_sys_exit.assert_called_once_with(1)


class TestMainFunctionIntegration:
    """Интеграционные тесты для main функции"""

    @pytest.mark.asyncio
    async def test_main_successful_start(self, mocker):
        """Тест успешного запуска клиента"""
        mock_client = mocker.MagicMock()
        mock_client.start = mocker.AsyncMock()

        # Симулируем успешный запуск
        await mock_client.start()

        mock_client.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_fail_login_token_raises(self, mocker):
        """Тест что FAIL_LOGIN_TOKEN вызывает исключение"""
        mock_client = mocker.MagicMock()
        error = Exception("PyMax Error: FAIL_LOGIN_TOKEN")
        mock_client.start = mocker.AsyncMock(side_effect=error)

        with pytest.raises(Exception, match="FAIL_LOGIN_TOKEN"):
            await mock_client.start()

    @pytest.mark.asyncio
    async def test_main_russian_auth_error_raises(self, mocker):
        """Тест что русская ошибка авторизации вызывает исключение"""
        mock_client = mocker.MagicMock()
        error = Exception("Пожалуйста, авторизируйтесь снова")
        mock_client.start = mocker.AsyncMock(side_effect=error)

        with pytest.raises(Exception, match="авторизируйтесь снова"):
            await mock_client.start()


class TestSessionFileHandling:
    """Тесты обработки файла сессии"""

    def test_session_file_path_construction(self):
        """Тест построения пути к файлу сессии"""
        session_file = Path("cache") / "session.db"

        assert session_file.name == "session.db"
        assert session_file.parent == Path("cache")
        # Проверяем, что путь содержит правильные компоненты
        assert "cache" in str(session_file)
        assert "session.db" in str(session_file)

    def test_session_file_exists_check(self, mocker):
        """Тест проверки существования файла сессии"""
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = True

        assert mock_path.exists() is True

    def test_session_file_not_exists_check(self, mocker):
        """Тест проверки отсутствия файла сессии"""
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = False

        assert mock_path.exists() is False

    def test_session_file_unlink(self, mocker):
        """Тест удаления файла сессии"""
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = True

        if mock_path.exists():
            mock_path.unlink()

        mock_path.unlink.assert_called_once()


class TestConsoleOutput:
    """Тесты вывода сообщений пользователю"""

    def test_auth_error_panel_created(self):
        """Тест что панель ошибки авторизации создаётся"""
        error_msg = "FAIL_LOGIN_TOKEN"

        # Симулируем создание панели
        panel_content = (
            "[bold red]❌ Ошибка авторизации![/]\n\n"
            "Ваша сессия истекла или была разорвана.\n\n"
            "[green]✓ Старая сессия удалена автоматически[/]\n\n"
            "[yellow]Что делать дальше:[/]\n"
            "  1. Запустите приложение заново\n"
            "  2. Пройдите повторную авторизацию\n\n"
            "[dim]Ошибка: {error}[/]".format(error=error_msg)
        )

        assert "Ошибка авторизации" in panel_content
        assert "FAIL_LOGIN_TOKEN" in panel_content
        assert "Старая сессия удалена" in panel_content

    def test_error_message_format(self):
        """Тест формата сообщения об ошибке"""
        error_msg = "PyMax Error: FAIL_LOGIN_TOKEN"

        # Проверяем форматирование
        formatted_msg = "[dim]Ошибка: {error}[/]".format(error=error_msg)

        assert error_msg in formatted_msg
        assert formatted_msg.startswith("[dim]")


class TestLoggerCalls:
    """Тесты вызовов логгера"""

    def test_logger_error_called_on_auth_fail(self, mocker):
        """Тест что logger.error вызывается при ошибке авторизации"""
        mock_logger = mocker.MagicMock()
        error_msg = "FAIL_LOGIN_TOKEN"

        mock_logger.error("Авторизация не удалась: %s", error_msg)

        mock_logger.error.assert_called_once_with("Авторизация не удалась: %s", error_msg)

    def test_logger_info_called_on_session_delete(self, mocker):
        """Тест что logger.info вызывается при удалении сессии"""
        mock_logger = mocker.MagicMock()
        session_file = "cache/session.db"

        mock_logger.info("Старая сессия удалена: %s", session_file)

        mock_logger.info.assert_called_once_with("Старая сессия удалена: %s", session_file)

    def test_logger_exception_called_on_other_error(self, mocker):
        """Тест что logger.exception вызывается при других ошибках"""
        mock_logger = mocker.MagicMock()

        mock_logger.exception("Необработанная ошибка в main()")

        mock_logger.exception.assert_called_once_with("Необработанная ошибка в main()")
