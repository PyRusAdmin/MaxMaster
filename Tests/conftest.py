# -*- coding: utf-8 -*-
"""
Конфигурация pytest для проекта.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импортов
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
