import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(
        self,
        telegram_token: str | None = None,
        chat_id: str | None = None,
        slack_webhook: str | None = None,
    ):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.slack_webhook = slack_webhook

    async def send_telegram(self, message: str, reply_markup: dict | None = None):
        if not self.telegram_token or not self.chat_id:
            logger.debug("Telegram credentials missing, skipping alert.")
            return

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json=payload, timeout=5.0)
                logger.info("Alert dispatched to Telegram.")
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")

    async def dispatch(
        self, new_slots: list, target_slug: str, date_str: str, party_size: int
    ):
        if not new_slots:
            return

        times = [s.get("time", s.get("start_time", "Unknown")) for s in new_slots]
        message = (
            f"🚨 *{target_slug} Availability Alert!* 🚨\n\n"
            f"📅 Date: {date_str}\n"
            f"👥 Pax: {party_size}\n"
            f"🕰️ New Slots: {', '.join(times)}"
        )

        booking_url = f"https://reservation.provider.com/en/block/{target_slug}"
        reply_markup = {
            "inline_keyboard": [[{"text": "📖 Book Now", "url": booking_url}]]
        }

        logger.info(f"Dispatching alert for {len(new_slots)} new slots...")
        await self.send_telegram(message, reply_markup=reply_markup)
