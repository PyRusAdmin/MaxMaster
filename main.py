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
SLEEP_TIME = float(os.getenv("SLEEP_BETWEEN_REQUESTS", "5"))
phone_number = os.getenv("PHONE_NUMBER")

client = MaxClient(
    phone=phone_number,
    work_dir="cache",  # директория для сессий
)


def extract_user_data(result) -> dict:
    user_data = {}

    if not result or isinstance(result, (str, int, bool)):
        return user_data

    for attr in dir(result):
        if not attr.startswith('_'):
            try:
                val = getattr(result, attr)
                if not callable(val):
                    if attr == 'update_time' and isinstance(val, (int, float)):
                        dt = datetime.fromtimestamp(val / 1000)
                        user_data[attr] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(val, list) and val and hasattr(val[0], '__dict__'):
                        user_data[attr] = [str(item) for item in val]
                    else:
                        user_data[attr] = val  # просто сохраняем как есть
            except Exception:
                pass

    return user_data


HEADERS_RU = {
    'account_status': 'Статус аккаунта',
    'base_raw_url': 'Фото (raw URL)',
    'base_url': 'Фото (URL)',
    'description': 'Описание',
    'error': 'Ошибка',
    'gender': 'Пол',
    'id': 'ID пользователя',
    'link': 'Ссылка на профиль',
    'menu_button': 'Кнопка меню',
    'names': 'Имя',
    'options': 'Платформы',
    'photo_id': 'ID фото',
    'searched_phone': 'Искомый телефон',
    'update_time': 'Последняя активность',
    'web_app': 'Веб-приложение',
}


def save_to_excel(users_data: list[dict], filename: str = "output/users.xlsx") -> str:
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    if os.path.exists(filename):
        from openpyxl import load_workbook
        wb = load_workbook(filename)
        ws = wb.active
        headers = [cell.value for cell in ws[1] if cell.value]
        # Восстанавливаем ключи из русских заголовков (обратный маппинг)
        ru_to_key = {v: k for k, v in HEADERS_RU.items()}
        header_keys = [ru_to_key.get(h, h) for h in headers]
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Пользователи"
        headers = []
        header_keys = []

    # Добавляем новые ключи если появились
    all_keys = set(header_keys)
    for user in users_data:
        all_keys.update(user.keys())

    new_keys = sorted(all_keys)
    if new_keys != header_keys:
        for col, key in enumerate(new_keys, 1):
            ws.cell(row=1, column=col, value=HEADERS_RU.get(key, key))  # пишем русское название
        header_keys = new_keys

    # Записываем строки
    start_row = ws.max_row + 1 if ws.max_row > 1 else 2

    for row_idx, user in enumerate(users_data, start_row):
        for col_idx, key in enumerate(header_keys, 1):
            value = user.get(key, "")
            if isinstance(value, list):
                value = " | ".join(str(v) for v in value)
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Автоширина
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

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

    excel_file = "output/users.xlsx"  # Фиксированное имя файла

    for phone in numbers:

        await asyncio.sleep(SLEEP_TIME)

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

                logger.info("\n📋 Доступные поля пользователя:")
                for attr, val in user_data.items():
                    logger.info(f"  {attr}: {val}")

                # Сохраняем данные в Excel после каждого успешного поиска
                save_to_excel([user_data], excel_file)
                logger.info(f"💾 Данные сохранены в {excel_file}")

        except Exception as e:
            logger.info(f"❌ Ошибка при поиске: {type(e).__name__}: {e}")
            # Сохраняем информацию об ошибке в Excel
            error_data = {
                'searched_phone': phone,
                'error': f"{type(e).__name__}: {e}"
            }
            save_to_excel([error_data], excel_file)

    logger.info(f"\n✅ Обработка завершена. Файл: {excel_file}")

    # Получение истории
    history = await client.fetch_history(chat_id=0)
    logger.info("Последние сообщения из чата 0:")
    for m in history:
        logger.info(f"- {m.text}")


async def main():
    await client.start()  # подключение и авторизация


if __name__ == "__main__":
    asyncio.run(main())
