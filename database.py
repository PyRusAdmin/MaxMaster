# -*- coding: utf-8 -*-
"""
Модуль работы с базой данных.

Определяет модели данных для хранения:
- Очереди номеров телефонов для обработки
- Подключённых аккаунтов Max
- Журнала действий с аккаунтами

Используется ORM Peewee для работы с SQLite.
"""
import os
from datetime import datetime

from peewee import SqliteDatabase, Model, CharField, DateTimeField, TextField

from config import DB_PATH

# ─── База данных (Peewee) ─────────────────────────────────────────────────────
# Создание директории для базы данных (если не существует)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
# Подключение к SQLite базе данных очереди номеров
db = SqliteDatabase(DB_PATH)


class PhoneQueue(Model):
    """
    Модель очереди номеров телефонов для обработки.
    
    Хранит уникальные номера телефонов, которые будут обработаны программой.
    """
    phone = CharField(unique=True)  # Номер телефона (уникальный)
    added_at = DateTimeField(default=datetime.now)  # Дата и время добавления в очередь

    class Meta:
        database = db  # Используемая база данных
        table_name = "phone_queue"  # Имя таблицы в БД


# ─── База данных аккаунтов Max ────────────────────────────────────────────────
# Путь к базе данных аккаунтов Max
ACCOUNTS_DB_PATH = "data/accounts.db"
# Создание директории для базы данных аккаунтов
os.makedirs(os.path.dirname(ACCOUNTS_DB_PATH), exist_ok=True)
# Подключение к SQLite базе данных аккаунтов
accounts_db = SqliteDatabase(ACCOUNTS_DB_PATH)


class MaxAccount(Model):
    """
    Модель подключённого аккаунта Max.
    
    Хранит информацию о подключённых аккаунтах, их статусе и статистике ошибок.
    """
    phone = CharField(unique=True, help_text="Номер телефона")  # Номер телефона аккаунта
    name = CharField(null=True, help_text="Имя пользователя")  # Имя пользователя из профиля
    user_id = CharField(null=True, help_text="ID пользователя в Max")  # Уникальный ID в системе Max
    account_path = CharField(help_text="Путь к папке аккаунта")  # Путь к директории с данными аккаунта
    connected_at = DateTimeField(default=datetime.now, help_text="Дата подключения")  # Когда аккаунт подключён
    is_active = CharField(default="Y", help_text="Активен ли аккаунт (Y/N)")  # Флаг активности аккаунта
    is_blocked = CharField(default="N", help_text="Заблокирован ли аккаунт (Y/N)")  # Флаг блокировки аккаунта
    errors_count = CharField(default="0", help_text="Количество ошибок")  # Счётчик ошибок при работе
    last_used_at = DateTimeField(null=True, help_text="Последнее использование")  # Время последнего использования
    work_status = CharField(default="idle", help_text="Статус работы: idle/working/blocked")  # Текущий статус

    class Meta:
        database = accounts_db  # Используемая база данных
        table_name = "max_accounts"  # Имя таблицы в БД


class AccountLog(Model):
    """
    Модель журнала действий с аккаунтами.
    
    Логирует все важные события: запуск, остановку, ошибки, блокировки.
    """
    phone = CharField(help_text="Номер телефона аккаунта")  # Номер телефона аккаунта
    action = CharField(help_text="Действие: start/work/error/block/stop")  # Тип действия
    message = TextField(null=True, help_text="Сообщение")  # Дополнительное сообщение
    created_at = DateTimeField(default=datetime.now)  # Дата и время записи

    class Meta:
        database = accounts_db  # Используемая база данных
        table_name = "account_logs"  # Имя таблицы в БД


# Подключение к базам данных и создание таблиц
db.connect()
db.create_tables([PhoneQueue], safe=True)

accounts_db.connect()
accounts_db.create_tables([MaxAccount, AccountLog], safe=True)
