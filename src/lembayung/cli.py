import asyncio
import datetime
import logging
import random

import httpx

from lembayung.adapters.provider import ProviderAdapter, RateLimitHit, UnauthorizedError
from lembayung.core.config import settings
from lembayung.database.sqlite import DatabaseState
from lembayung.engine.worker import MonitoringWorker
from lembayung.notifications.dispatcher import NotificationDispatcher

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_monitoring_session(worker: MonitoringWorker, adapter: ProviderAdapter):
    """Core iteration of fetching and comparing, with circuit-breaker and adaptive delays."""
    target_date = datetime.date.today()
    allowed_days = settings.allowed_weekdays
    request_count = 0

    for i in range(settings.fetch_days_ahead):
        curr_date = target_date + datetime.timedelta(days=i)

        # Skip dates that don't match the day filter
        if curr_date.weekday() not in allowed_days:
            continue

        for pax in settings.pax_range:
            try:
                response_data = await adapter.get_slots(pax, curr_date)
                slots = response_data if isinstance(response_data, list) else []

                # Filter slots by time range
                if slots and (settings.time_range_start and settings.time_range_end):
                    slots = [
                        s
                        for s in slots
                        if settings.is_time_in_range(
                            s.get("time", s.get("start_time", ""))
                        )
                    ]

                if slots:
                    date_str = curr_date.strftime("%Y-%m-%d")
                    added, removed = await worker.db.process_snapshot(
                        date_str, pax, slots
                    )

                    if added:
                        await worker.notifier.dispatch(
                            added, settings.target_slug, date_str, pax
                        )

            except RateLimitHit as e:
                # Circuit-breaker: stop the entire cycle immediately
                logger.warning(f"⚡ Rate limit hit — aborting cycle early. {e}")
                logger.info(
                    f"  Completed {request_count} requests before 428. "
                    f"Will retry next cycle in {settings.poll_interval_seconds}s."
                )
                return  # Exit the cycle, let worker sleep and try next cycle

            except UnauthorizedError as e:
                logger.error(
                    f"❌ Unauthorized Error (API Key or Slug may be invalid). Aborting worker completely: {e}"
                )
                worker.is_running = False
                return

            except httpx.HTTPStatusError as e:
                logger.error(f"Error checking {curr_date} pax {pax}: {e}")
            except Exception as e:
                logger.error(f"Error checking {curr_date} pax {pax}: {e}")

            request_count += 1

            # Batch cooldown: longer pause every N requests
            if (
                request_count % settings.batch_cooldown_every == 0
                and settings.batch_cooldown_every > 0
            ):
                cooldown = settings.batch_cooldown_seconds + random.uniform(0, 3)
                logger.debug(
                    f"Batch cooldown after {request_count} requests: "
                    f"sleeping {cooldown:.1f}s"
                )
                await asyncio.sleep(cooldown)
            else:
                # Randomized jitter between requests
                delay = random.uniform(
                    settings.request_delay_min, settings.request_delay_max
                )
                await asyncio.sleep(delay)


async def main_loop():
    day_desc = settings.day_filter
    time_desc = "all day"
    if settings.time_range_start and settings.time_range_end:
        time_desc = f"{settings.time_range_start}-{settings.time_range_end}"

    logger.info(f"Starting Lembayung for {settings.target_slug}")
    logger.info(
        f"  Pax: {settings.min_pax}-{settings.max_pax} | Days: {day_desc} | Time: {time_desc}"
    )
    logger.info(
        f"  Polling every {settings.poll_interval_seconds}s across {settings.fetch_days_ahead} days ahead"
    )
    logger.info(
        f"  Request delay: {settings.request_delay_min}-{settings.request_delay_max}s | "
        f"Batch cooldown: {settings.batch_cooldown_seconds}s every {settings.batch_cooldown_every} reqs"
    )

    adapter = ProviderAdapter(
        settings.provider_base_url,
        settings.provider_api_key,
        settings.target_slug,
        settings.provider_origin,
        settings.provider_referer,
    )
    db = DatabaseState(settings.sqlite_db_path)
    notifier = NotificationDispatcher(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.slack_webhook_url,
    )

    await db.init_db()

    worker = MonitoringWorker(settings, adapter, db, notifier)
    worker.single_check = lambda: run_monitoring_session(worker, adapter)

    try:
        await worker.run_forever()
    finally:
        await adapter.close()


def main():
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
