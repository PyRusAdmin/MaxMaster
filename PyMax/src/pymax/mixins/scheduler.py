# -*- coding: utf-8 -*-
"""
Mixin для планирования периодических задач.

Содержит SchedulerMixin для выполнения задач по расписанию.
"""
import asyncio
import traceback
from collections.abc import Awaitable, Callable
from typing import Any
from loguru import logger

from PyMax.src.pymax.protocols import ClientProtocol


class SchedulerMixin(ClientProtocol):
    """
    Mixin для планирования и выполнения периодических задач.
    """
    async def _run_periodic(
            self, func: Callable[[], Any | Awaitable[Any]], interval: float
    ) -> None:
        """
        Выполняет функцию периодически с заданным интервалом.

        :param func: Функция для выполнения.
        :type func: Callable[[], Any | Awaitable[Any]]
        :param interval: Интервал выполнения в секундах.
        :type interval: float
        :return: None
        """
        while True:
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"Error in scheduled task {func}: {e}")
                raise
            await asyncio.sleep(interval)

    async def _start_scheduled_tasks(self) -> None:
        """
        Запускает все запланированные задачи.

        :return: None
        """
        for func, interval in self._scheduled_tasks:
            task = asyncio.create_task(self._run_periodic(func, interval))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
