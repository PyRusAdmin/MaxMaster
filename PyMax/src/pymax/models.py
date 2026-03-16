# -*- coding: utf-8 -*-
"""
SQLModel модели для базы данных.

Содержит модель Auth для хранения токенов авторизации и ID устройств.
"""
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Auth(SQLModel, table=True):
    """
    Модель аутентификации для хранения токена и ID устройства.

    :ivar token: Токен авторизации.
    :type token: str | None
    :ivar device_id: UUID устройства (первичный ключ).
    :type device_id: UUID
    """
    token: str | None = None
    device_id: UUID = Field(default_factory=uuid4, primary_key=True)
