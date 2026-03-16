# -*- coding: utf-8 -*-
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from openpyxl import Workbook
from peewee import SqliteDatabase, Model, CharField, DateTimeField

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from PyMax.src.pymax.core import MaxClient
from PyMax.src.pymax.payloads import UserAgentPayload
from read_file import read_file

# ─── Версия приложения ────────────────────────────────────────────────────────
APP_VERSION = "0.0.1"
APP_DATE = "12.03.2026"

# ─── Логгер ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add("logs/log.log", rotation="1 MB", level="INFO")
logger.add(sys.stderr, level="WARNING")

# ─── Конфиг ───────────────────────────────────────────────────────────────────
load_dotenv()
SLEEP_TIME = float(os.getenv("SLEEP_BETWEEN_REQUESTS", "5"))
SLEEP_ON_RATELIMIT = float(os.getenv("SLEEP_ON_RATELIMIT", "30"))
phone = os.getenv("PHONE_NUMBER")  # Номер телефона аккаунта
DB_PATH = os.getenv("DB_PATH", "data/queue.db")  # База номеров для перебора
EXCEL_FILE = os.getenv("EXCEL_FILE", "output/users.xlsx")  # Полученные номера после перебора
NUMBERS_FILE = os.getenv("NUMBERS_FILE", "input/numbers.txt")  # Номера для перебора

# ─── Rich консоль ─────────────────────────────────────────────────────────────
console = Console()

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


db.connect()
db.create_tables([PhoneQueue], safe=True)

# ─── Max клиент ───────────────────────────────────────────────────────────────


headers = UserAgentPayload(device_type="WEB")

client = MaxClient(
    phone=phone,
    work_dir="cache",
    reconnect=False,
    headers=headers,
)

# ─── Заголовки Excel ──────────────────────────────────────────────────────────
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


# ─── Утилиты ──────────────────────────────────────────────────────────────────

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
                        user_data[attr] = val
            except Exception:
                pass
    return user_data


def save_to_excel(users_data: list[dict], filename: str = EXCEL_FILE) -> str:
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    if os.path.exists(filename):
        from openpyxl import load_workbook
        wb = load_workbook(filename)
        ws = wb.active
        headers = [cell.value for cell in ws[1] if cell.value]
        ru_to_key = {v: k for k, v in HEADERS_RU.items()}
        header_keys = [ru_to_key.get(h, h) for h in headers]
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Пользователи"
        headers = []
        header_keys = []

    all_keys = set(header_keys)
    for user in users_data:
        all_keys.update(user.keys())

    new_keys = sorted(all_keys)
    if new_keys != header_keys:
        for col, key in enumerate(new_keys, 1):
            ws.cell(row=1, column=col, value=HEADERS_RU.get(key, key))
        header_keys = new_keys

    start_row = ws.max_row + 1 if ws.max_row > 1 else 2

    for row_idx, user in enumerate(users_data, start_row):
        for col_idx, key in enumerate(header_keys, 1):
            value = user.get(key, "")
            if isinstance(value, list):
                value = " | ".join(str(v) for v in value)
            ws.cell(row=row_idx, column=col_idx, value=value)

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    wb.save(filename)
    return filename


def load_numbers_to_db() -> int:
    """Загружает номера из файла в БД, пропуская дубликаты."""
    numbers = read_file()  # без аргумента
    added = 0
    for phone in numbers:
        try:
            PhoneQueue.get_or_create(phone=str(phone).strip())
            added += 1
        except Exception:
            pass
    return PhoneQueue.select().count()


def get_queue_count() -> int:
    return PhoneQueue.select().count()


def remove_from_queue(phone: str):
    PhoneQueue.delete().where(PhoneQueue.phone == phone).execute()


def get_next_phones(batch: int = 1) -> list[str]:
    rows = PhoneQueue.select().order_by(PhoneQueue.added_at).limit(batch)
    return [r.phone for r in rows]


# ─── UI ───────────────────────────────────────────────────────────────────────

def print_header():
    console.clear()
    title = Text("📱  MAX / OneMe Phone Parser", style="bold cyan")
    subtitle = Text("Парсинг пользователей по номерам телефона", style="dim")
    version = Text(f"Версия: {APP_VERSION} от {APP_DATE}", style="yellow")
    console.print(Panel(
        Align.center(Text.assemble(title, "\n", subtitle, "\n", version)),
        border_style="cyan",
        padding=(1, 4),
    ))


def print_stats():
    total = get_queue_count()
    table = Table(box=box.ROUNDED, border_style="blue", show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold green")
    table.add_row("📋 Осталось в очереди:", str(total))
    table.add_row("💾 Файл результатов:", EXCEL_FILE)
    table.add_row("⏱️  Задержка между запросами:", f"{SLEEP_TIME} сек")
    console.print(table)


def print_menu() -> str:
    console.print()
    console.print(Panel(
        "[bold white]Выберите действие:[/]\n\n"
        "  [cyan][1][/cyan] ▶  Продолжить / начать перебор номеров\n"
        "  [cyan][2][/cyan] 🔄  Обновить список номеров из файла\n"
        "  [cyan][3][/cyan] 📊  Показать статистику очереди\n"
        "  [cyan][0][/cyan] ❌  Выйти",
        title="[bold cyan]Меню[/]",
        border_style="cyan",
        padding=(1, 3),
    ))
    choice = Prompt.ask(
        "[bold yellow]Ваш выбор[/]",
        choices=["0", "1", "2", "3"],
        default="1",
    )
    return choice


# ─── Парсинг ──────────────────────────────────────────────────────────────────

async def parse_phones():
    total_start = get_queue_count()
    if total_start == 0:
        console.print(Panel(
            "[yellow]Очередь пуста.[/]\nЗагрузите номера через пункт [cyan][2][/cyan] меню.",
            border_style="yellow",
        ))
        return

    console.print(Panel(
        f"[green]Начинаем обработку [bold]{total_start}[/bold] номеров...[/]\n"
        f"[dim]Нажмите Ctrl+C для паузы[/]",
        border_style="green",
    ))

    processed = 0
    found = 0
    errors = 0

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[dim]{task.fields[status]}[/]"),
            console=console,
            transient=False,
    ) as progress:
        task = progress.add_task(
            "[cyan]Обработка...",
            total=total_start,
            status="",
        )

        while True:
            phones = get_next_phones(1)
            if not phones:
                break

            phone = phones[0]
            progress.update(task, description=f"[cyan]📞 {phone}", status="запрос...")

            await asyncio.sleep(SLEEP_TIME)

            try:
                result = await safe_search(phone)
                if result is None:
                    logger.error(f"Не удалось получить данные для {phone} после нескольких попыток")
                    status_text = "❌ нет соединения"
                    # не удаляем из очереди
                    continue

                if result and not isinstance(result, (str, int, bool)):
                    user_data = extract_user_data(result)
                    user_data['searched_phone'] = phone
                    save_to_excel([user_data], EXCEL_FILE)
                    found += 1
                    status_text = f"✅ найден: {user_data.get('names', ['?'])[0] if user_data.get('names') else '?'}"
                    logger.info(f"Найден пользователь {phone}: {user_data}")
                else:
                    status_text = "⚪ не найден"
                    logger.info(f"Пользователь не найден: {phone}")

            except Exception as e:
                err_str = str(e)
                if 'too-many' in err_str.lower():
                    progress.update(task, status=f"⏳ rate limit, ждём {SLEEP_ON_RATELIMIT}с...")
                    logger.warning(f"Rate limit на {phone}, ждём {SLEEP_ON_RATELIMIT}с")
                    await asyncio.sleep(SLEEP_ON_RATELIMIT)
                    # Не удаляем из очереди — попробуем снова
                    continue
                else:
                    error_data = {'searched_phone': phone, 'error': f"{type(e).__name__}: {e}"}
                    save_to_excel([error_data], EXCEL_FILE)
                    errors += 1
                    status_text = f"❌ ошибка"
                    logger.error(f"Ошибка для {phone}: {e}")

            # Удаляем из очереди только после успешной обработки
            remove_from_queue(phone)
            processed += 1
            progress.update(task, advance=1, status=status_text)

    console.print()
    console.print(Panel(
        f"[bold green]✅ Обработка завершена![/]\n\n"
        f"  Обработано: [bold]{processed}[/]\n"
        f"  Найдено:    [bold green]{found}[/]\n"
        f"  Ошибок:     [bold red]{errors}[/]\n\n"
        f"  Результаты: [cyan]{EXCEL_FILE}[/]",
        border_style="green",
        padding=(1, 3),
    ))


async def safe_search(phone: str, retries: int = 3):
    """Поиск с автоматическим переподключением."""
    for attempt in range(retries):
        try:
            result = await client.search_by_phone(phone=phone)
            return result
        except Exception as e:
            err = str(e).lower()
            if 'not connected' in err or 'websocket' in err:
                logger.warning(f"WebSocket отключён, ждём переподключения... (попытка {attempt + 1}/{retries})")
                await asyncio.sleep(10)  # даём pymax время переподключиться
                continue
            raise  # остальные ошибки — пробрасываем
    return None


# ─── Точка входа ──────────────────────────────────────────────────────────────

@client.on_start
async def on_start() -> None:
    logger.info(f"Клиент запущен. ID: {client.me.id}")

    print_header()
    console.print(f"[dim]Подключено. Ваш ID: [cyan]{client.me.id}[/][/]\n")

    while True:
        print_stats()
        choice = print_menu()

        if choice == "0":
            console.print("\n[dim]До свидания![/]")
            sys.exit(0)

        elif choice == "1":
            try:
                await parse_phones()
            except KeyboardInterrupt:
                console.print("\n[yellow]⏸  Пауза. Прогресс сохранён в БД.[/]")

        elif choice == "2":
            with console.status("[cyan]Загружаем номера из файла...[/]"):
                count = load_numbers_to_db()
            console.print(Panel(
                f"[green]✅ Готово![/] В очереди теперь [bold]{count}[/bold] номеров.",
                border_style="green",
            ))

        elif choice == "3":
            print_header()
            # Детальная статистика
            total = get_queue_count()
            table = Table(title="Статистика очереди", box=box.ROUNDED, border_style="cyan")
            table.add_column("Параметр", style="dim")
            table.add_column("Значение", style="bold")
            table.add_row("Номеров в очереди", str(total))
            table.add_row("Файл номеров", NUMBERS_FILE)
            table.add_row("База данных", DB_PATH)
            table.add_row("Результаты Excel", EXCEL_FILE)
            table.add_row("Задержка запросов", f"{SLEEP_TIME} сек")
            table.add_row("Задержка при rate limit", f"{SLEEP_ON_RATELIMIT} сек")
            console.print(table)

        console.print()
        input("  [Enter] для возврата в меню...")
        print_header()


async def main():
    try:
        await client.start()
    except Exception as e:
        error_msg = str(e)

        # Обработка ошибки авторизации
        if "FAIL_LOGIN_TOKEN" in error_msg or "авторизируйтесь снова" in error_msg.lower():
            # Автоматическая очистка старой сессии
            session_file = Path("cache") / "session.db"
            if session_file.exists():
                session_file.unlink()
                logger.info("Старая сессия удалена: %s", session_file)

            console.print(Panel(
                "[bold red]❌ Ошибка авторизации![/]\n\n"
                "Ваша сессия истекла или была разорвана.\n\n"
                "[green]✓ Старая сессия удалена автоматически[/]\n\n"
                "[yellow]Что делать дальше:[/]\n"
                "  1. Запустите приложение заново\n"
                "  2. Пройдите повторную авторизацию (отсканируйте QR-код или введите код из SMS)\n\n"
                "[dim]Ошибка: {error}[/]".format(error=error_msg),
                title="[bold red]Требуется авторизация[/]",
                border_style="red",
                padding=(1, 3),
            ))
            logger.error(f"Авторизация не удалась: {error_msg}")
            sys.exit(1)

        # Другие ошибки
        console.print(Panel(
            f"[bold red]❌ Произошла ошибка:[/]\n\n{error_msg}",
            title="[bold red]Ошибка[/]",
            border_style="red",
            padding=(1, 3),
        ))
        logger.exception("Необработанная ошибка в main()")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
