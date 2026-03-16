# -*- coding: utf-8 -*-
"""
Модуль для форматирования текста и парсинга Markdown.

Содержит класс Formatting для преобразования Markdown-разметки
в элементы форматирования Max API.

Использование::

    from PyMax.src.pymax.formatting import Formatting

    elements, clean_text = Formatting.get_elements_from_markdown("**Привет** мир!")
    # elements = [Element(type=FormattingType.STRONG, from_=0, length=6)]
    # clean_text = "Привет мир!"
"""
import re

from PyMax.src.pymax.static.enum import FormattingType
from PyMax.src.pymax.types import Element


class Formatting:
    """
    Класс для парсинга Markdown-разметки и преобразования в элементы форматирования.

    Поддерживаемые форматы:
    - **text** — жирный (strong)
    - *text* — курсив (emphasized)
    - __text__ — подчёркнутый (underline)
    - ~~text~~ — зачёркнутый (strikethrough)

    :cvar MARKUP_BLOCK_PATTERN: Регулярное выражение для поиска Markdown разметки.
    :type MARKUP_BLOCK_PATTERN: re.Pattern
    """
    MARKUP_BLOCK_PATTERN = re.compile(
        (
            r"\*\*(?P<strong>.+?)\*\*|"
            r"\*(?P<italic>.+?)\*|"
            r"__(?P<underline>.+?)__|"
            r"~~(?P<strike>.+?)~~"
        ),
        re.DOTALL,
    )

    @staticmethod
    def get_elements_from_markdown(text: str) -> tuple[list[Element], str]:
        """
        Извлекает элементы форматирования из Markdown текста.

        Парсит текст, находит Markdown-разметку и создаёт список элементов
        форматирования с указанием типа, позиции и длины каждого элемента.

        Алгоритм работы:
        1. Находит все вхождения Markdown-разметки с помощью регулярного выражения
        2. Для каждого совпадения определяет тип форматирования
        3. Создаёт элемент Element с позицией и длиной
        4. Формирует чистый текст без Markdown-символов

        :param text: Текст с Markdown разметкой.
        :type text: str
        :return: Кортеж из списка элементов форматирования и чистого текста.
        :rtype: tuple[list[Element], str]

        Example::

            >>> elements, clean = Formatting.get_elements_from_markdown("**Привет** мир!")
            >>> len(elements)
            1
            >>> elements[0].type
            <FormattingType.STRONG: 'STRONG'>
            >>> clean
            'Привет мир!'
        """
        text = text.strip("\n")
        elements: list[Element] = []
        clean_parts: list[str] = []
        current_pos = 0

        last_end = 0
        for match in Formatting.MARKUP_BLOCK_PATTERN.finditer(text):
            between = text[last_end: match.start()]
            if between:
                clean_parts.append(between)
                current_pos += len(between)

            inner_text = None
            fmt_type = None
            if match.group("strong") is not None:
                inner_text = match.group("strong")
                fmt_type = FormattingType.STRONG
            elif match.group("italic") is not None:
                inner_text = match.group("italic")
                fmt_type = FormattingType.EMPHASIZED
            elif match.group("underline") is not None:
                inner_text = match.group("underline")
                fmt_type = FormattingType.UNDERLINE
            elif match.group("strike") is not None:
                inner_text = match.group("strike")
                fmt_type = FormattingType.STRIKETHROUGH

            if inner_text is not None and fmt_type is not None:
                next_pos = match.end()
                has_newline = (next_pos < len(text) and text[next_pos] == "\n") or (
                        next_pos == len(text)
                )

                length = len(inner_text) + (1 if has_newline else 0)
                elements.append(Element(type=fmt_type, from_=current_pos, length=length))

                clean_parts.append(inner_text)
                if has_newline:
                    clean_parts.append("\n")

                current_pos += length

                if next_pos < len(text) and text[next_pos] == "\n":
                    last_end = match.end() + 1
                else:
                    last_end = match.end()
            else:
                last_end = match.end()

        tail = text[last_end:]
        if tail:
            clean_parts.append(tail)

        clean_text = "".join(clean_parts)
        return elements, clean_text
