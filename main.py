import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from pymax import MaxClient, Message
from pymax import SocketMaxClient
from pymax.filters import Filters
from loguru import logger
from openpyxl import Workbook

from read_file import read_file

logger.add("logs/log.log", rotation="1 MB")

load_dotenv()

phone_number = os.getenv("PHONE_NUMBER")

client = MaxClient(
    phone=phone_number,
    work_dir="cache",  # директория для сессий
)


def extract_user_data(result) -> dict:
    """Извлекает все доступные данные из объекта пользователя."""
    user_data = {}
    
    if not result or isinstance(result, (str, int, bool)):
        return user_data
    
    for attr in dir(result):
        if not attr.startswith('_'):
            try:
                val = getattr(result, attr)
                if not callable(val):
                    # Обрабатываем списки объектов (например, names)
                    if isinstance(val, list) and val and hasattr(val[0], '__dict__'):
                        user_data[attr] = [str(item) for item in val]
                    else:
                        user_data[attr] = val
            except Exception:
                pass
    
    return user_data


def save_to_excel(users_data: list[dict], filename: str = "output/users.xlsx") -> str:
    """Сохраняет данные пользователей в Excel таблицу."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    
    # Собираем все возможные заголовки из всех записей
    all_headers = set()
    for user in users_data:
        all_headers.update(user.keys())
    
    # Сортируем заголовки для удобства
    headers = sorted(list(all_headers))
    
    # Записываем заголовки
    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)
    
    # Записываем данные
    for row_idx, user in enumerate(users_data, 2):
        for col_idx, header in enumerate(headers, 1):
            value = user.get(header, "")
            # Преобразуем списки в строку
            if isinstance(value, list):
                value = " | ".join(str(v) for v in value)
            ws.cell(row=row_idx, column=col_idx, value=value)
    
    # Автоширина колонок
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width
    
    # Сохраняем
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    wb.save(filename)
    return filename


# Обработка входящих сообщений
# @client.on_message(Filters.chat(0))  # фильтр по ID чата
# async def on_message(msg: Message) -> None:
#     print(f"[{msg.sender}] {msg.text}")
#
#     await client.send_message(
#         chat_id=msg.chat_id,
#         text="Привет, я бот на PyMax!",
#     )
#
#     await client.add_reaction(
#         chat_id=msg.chat_id,
#         message_id=str(msg.id),
#         reaction="👍",
#     )


@client.on_start
async def on_start() -> None:
    logger.info(f"Клиент запущен. Ваш ID: {client.me.id}")

    # Посмотреть все публичные методы клиента
    methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
    logger.info("Доступные методы:", methods)

    # Номер телефона в международном формате (без +)
    numbers = read_file()

    users_data = []  # Список для хранения данных всех пользователей

    for phone in numbers:

        logger.info(f"\n🔍 Ищем пользователя по номеру: {phone}")
        try:
            # Поиск по телефону
            result = await client.search_by_phone(phone=phone)
            logger.info(f"✓ Результат поиска: {type(result)}")
            logger.info(f"Данные: {result}")

            # Если результат — объект пользователя, извлекаем все данные
            if result and not isinstance(result, (str, int, bool)):
                user_data = extract_user_data(result)
                user_data['searched_phone'] = phone  # Добавляем номер, по которому искали
                users_data.append(user_data)
                
                logger.info("\n📋 Доступные поля пользователя:")
                for attr, val in user_data.items():
                    logger.info(f"  {attr}: {val}")

        except Exception as e:
            logger.info(f"❌ Ошибка при поиске: {type(e).__name__}: {e}")
            # Сохраняем информацию об ошибке
            users_data.append({
                'searched_phone': phone,
                'error': f"{type(e).__name__}: {e}"
            })

    # Сохраняем все данные в Excel
    if users_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"output/users_{timestamp}.xlsx"
        saved_file = save_to_excel(users_data, filename)
        logger.info(f"\n💾 Данные сохранены в файл: {saved_file}")
        logger.info(f"Всего записей: {len(users_data)}")

    # Получение истории
    history = await client.fetch_history(chat_id=0)
    logger.info("Последние сообщения из чата 0:")
    for m in history:
        logger.info(f"- {m.text}")


async def main():
    await client.start()  # подключение и авторизация


if __name__ == "__main__":
    asyncio.run(main())
