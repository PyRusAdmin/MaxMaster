# -*- coding: utf-8 -*-
import os
from datetime import datetime

from peewee import SqliteDatabase, Model, CharField, DateTimeField, TextField

from config import DB_PATH

# ─── База данных (Peewee) ─────────────────────────────────────────────────────
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
db = SqliteDatabase(DB_PATH)


class PhoneQueue(Model):
    """Очередь номеров телефонов для обработки."""
    phone = CharField(unique=True)
    added_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "phone_queue"


# ─── База данных аккаунтов Max ────────────────────────────────────────────────
ACCOUNTS_DB_PATH = "data/accounts.db"
os.makedirs(os.path.dirname(ACCOUNTS_DB_PATH), exist_ok=True)
accounts_db = SqliteDatabase(ACCOUNTS_DB_PATH)


class MaxAccount(Model):
    """Подключённые аккаунты Max."""
    phone = CharField(unique=True, help_text="Номер телефона")
    name = CharField(null=True, help_text="Имя пользователя")
    user_id = CharField(null=True, help_text="ID пользователя в Max")
    account_path = CharField(help_text="Путь к папке аккаунта")
    connected_at = DateTimeField(default=datetime.now, help_text="Дата подключения")
    is_active = CharField(default="Y", help_text="Активен ли аккаунт (Y/N)")
    is_blocked = CharField(default="N", help_text="Заблокирован ли аккаунт (Y/N)")
    errors_count = CharField(default="0", help_text="Количество ошибок")
    last_used_at = DateTimeField(null=True, help_text="Последнее использование")
    work_status = CharField(default="idle", help_text="Статус работы: idle/working/blocked")

    class Meta:
        database = accounts_db
        table_name = "max_accounts"


class AccountLog(Model):
    """Лог использования аккаунтов."""
    phone = CharField(help_text="Номер телефона аккаунта")
    action = CharField(help_text="Действие: start/work/error/block/stop")
    message = TextField(null=True, help_text="Сообщение")
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        database = accounts_db
        table_name = "account_logs"


db.connect()
db.create_tables([PhoneQueue], safe=True)

accounts_db.connect()
accounts_db.create_tables([MaxAccount, AccountLog], safe=True)
