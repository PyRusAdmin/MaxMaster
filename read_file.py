# -*- coding: utf-8 -*-
"""
Модуль для чтения номеров телефонов из входного файла.

Предоставляет функцию read_file() для загрузки номеров из файла
input/numbers.txt. Номера должны быть в формате 79999999999.
"""
from loguru import logger


def read_file():
    """
    Читает номера телефонов из файла input/numbers.txt.
    
    Функция открывает файл, читает построчно номера, убирает лишние пробелы
    и переносы строк. Пустые строки пропускаются.
    
    :return: Список номеров телефонов (строки в формате 79999999999).
    :raises FileNotFoundError: Если файл input/numbers.txt не найден.
    """
    numbers = []

    # Открываем файл с номерами телефонов
    with open("input/numbers.txt", mode="r") as file:
        for line in file:
            # Убираем пробелы и переносы строк
            number = line.strip()
            # Пропускаем пустые строки
            if number:
                numbers.append(number)

    # Логируем количество найденных номеров
    logger.warning(f"Найдено {len(numbers)} телефонных номер(а)ов в файле numbers.txt")
    return numbers
