from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lembayung.core.config import AppConfig

if TYPE_CHECKING:
    from lembayung.adapters.provider import ProviderAdapter
    from lembayung.database.sqlite import DatabaseState
    from lembayung.notifications.dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


class MonitoringWorker:
    def __init__(
        self,
        config: AppConfig,
        adapter: ProviderAdapter,
        db: DatabaseState,
        notifier: NotificationDispatcher,
    ):
        self.config = config
        self.adapter = adapter
        self.db = db
        self.notifier = notifier
        self.is_running = False

    async def single_check(self):
        """
        Subclasses/instances override this logic locally as shown in cli.py.
        """
        pass

    async def run_forever(self):
        self.is_running = True
        interval = self.config.poll_interval_seconds
        logger.info(f"Starting worker loop. Polling interval: {interval}s")
        while self.is_running:
            try:
                await self.single_check()
            except Exception as e:
                logger.error(f"Error during overall check cycle: {e}")
            logger.info("Cycle complete. Sleeping...")
            await asyncio.sleep(interval)
