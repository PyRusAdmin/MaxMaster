import json
import os
import sys
from uuid import uuid4
from pymax import SocketMaxClient
from pymax.payloads import UserAgentPayload
from dotenv import load_dotenv
from websockets.sync.client import connect

import asyncio

from pymax import MaxClient, Message
from pymax.filters import Filters

load_dotenv()

phone_number = os.getenv("PHONE_NUMBER")

client = MaxClient(
    phone=phone_number,
    work_dir="cache",  # директория для сессий
)


# Обработка входящих сообщений
@client.on_message(Filters.chat(0))  # фильтр по ID чата
async def on_message(msg: Message) -> None:
    print(f"[{msg.sender}] {msg.text}")

    await client.send_message(
        chat_id=msg.chat_id,
        text="Привет, я бот на PyMax!",
    )

    await client.add_reaction(
        chat_id=msg.chat_id,
        message_id=str(msg.id),
        reaction="👍",
    )


@client.on_start
async def on_start() -> None:
    print(f"Клиент запущен. Ваш ID: {client.me.id}")

    # Посмотреть все публичные методы клиента
    methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
    print("Доступные методы:", methods)

    # Номер телефона в международном формате (без +)
    phone = "79493477926"  # замените на нужный номер

    print(f"\n🔍 Ищем пользователя по номеру: {phone}")
    try:
        # Поиск по телефону
        result = await client.search_by_phone(phone=phone)
        print(f"✓ Результат поиска: {type(result)}")
        print(f"Данные: {result}")

        # Если результат — объект пользователя, покажем поля
        if result and not isinstance(result, (str, int, bool)):
            print("\n📋 Доступные поля пользователя:")
            for attr in dir(result):
                if not attr.startswith('_'):
                    try:
                        val = getattr(result, attr)
                        if not callable(val):
                            print(f"  {attr}: {val}")
                    except:
                        pass

    except Exception as e:
        print(f"❌ Ошибка при поиске: {type(e).__name__}: {e}")

    # Получение истории
    history = await client.fetch_history(chat_id=0)
    print("Последние сообщения из чата 0:")
    for m in history:
        print(f"- {m.text}")


async def main():
    await client.start()  # подключение и авторизация


if __name__ == "__main__":
    asyncio.run(main())
