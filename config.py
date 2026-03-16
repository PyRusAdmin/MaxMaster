# -*- coding: utf-8 -*-
import os

from dotenv import load_dotenv

# ─── Версия приложения ────────────────────────────────────────────────────────
APP_VERSION = "0.0.1"
APP_DATE = "12.03.2026"


# ─── Конфиг ───────────────────────────────────────────────────────────────────
load_dotenv()
SLEEP_TIME = float(os.getenv("SLEEP_BETWEEN_REQUESTS", "5"))
SLEEP_ON_RATELIMIT = float(os.getenv("SLEEP_ON_RATELIMIT", "10"))
# phone = os.getenv("PHONE_NUMBER")  # Номер телефона аккаунта
DB_PATH = os.getenv("DB_PATH", "data/queue.db")  # База номеров для перебора
EXCEL_FILE = os.getenv("EXCEL_FILE", "output/users.xlsx")  # Полученные номера после перебора
NUMBERS_FILE = os.getenv("NUMBERS_FILE", "input/numbers.txt")  # Номера для перебора