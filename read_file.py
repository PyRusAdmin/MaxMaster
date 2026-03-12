# -*- coding: utf-8 -*-
from loguru import logger


def read_file():
    """
    Читает номера пользователя из папки input, файл numbers.txt.
    Номера должны быть в формате 79999999999.
    :return: список номеров (строки)
    """
    numbers = []

    with open("input/numbers.txt", mode="r") as file:
        for line in file:
            # Убираем пробелы и переносы строк
            number = line.strip()
            # Пропускаем пустые строки
            if number:
                numbers.append(number)
    logger.warning(f"Найдено {len(numbers)} телефонных номер(а)ов в файле numbers.txt")
    return numbers
