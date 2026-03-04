import asyncio
import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from lembayung.adapters.provider import ProviderAdapter, RateLimitHit, UnauthorizedError
from lembayung.core.config import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────
#  Command Handlers
# ──────────────────────────────────


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    if not update.message:
        return
    await update.message.reply_text(
        "🌅 *Welcome to Lembayung!*\n\n"
        "I monitor availability and alert you in real-time.\n\n"
        "Commands:\n"
        "/status — Current monitoring config\n"
        "/check — Run an immediate check\n"
        "/book — Browse dates and book a resource",
        parse_mode="Markdown",
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current monitoring config."""
    time_desc = "all day"
    if settings.time_range_start and settings.time_range_end:
        time_desc = f"{settings.time_range_start}–{settings.time_range_end}"

    if not update.message:
        return
    await update.message.reply_text(
        f"📊 *Monitoring Status*\n\n"
        f"🏠 Target: `{settings.target_slug}`\n"
        f"👥 Pax range: {settings.min_pax}–{settings.max_pax}\n"
        f"📅 Days: {settings.day_filter}\n"
        f"🕐 Time window: {time_desc}\n"
        f"🔄 Poll interval: {settings.poll_interval_seconds}s\n"
        f"📆 Days ahead: {settings.fetch_days_ahead}",
        parse_mode="Markdown",
    )


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run a single ad-hoc availability check."""
    if not update.message:
        return

    await update.message.reply_text("🔍 Checking availability now...")

    adapter = ProviderAdapter(
        settings.provider_base_url,
        settings.provider_api_key,
        settings.target_slug,
        settings.provider_origin,
        settings.provider_referer,
    )
    try:
        today = datetime.date.today()
        results = []

        rate_limited = False
        for i in range(min(settings.fetch_days_ahead, 14)):  # Cap at 14 days for ad-hoc
            curr = today + datetime.timedelta(days=i)
            if curr.weekday() not in settings.allowed_weekdays:
                continue

            for pax in settings.pax_range:
                try:
                    slots = await adapter.get_slots(pax, curr)
                    if slots:
                        # Filter by time
                        if settings.time_range_start and settings.time_range_end:
                            slots = [
                                s
                                for s in slots
                                if settings.is_time_in_range(
                                    s.get("time", s.get("start_time", ""))
                                )
                            ]
                        if slots:
                            times = [
                                s.get("time", s.get("start_time", "?")) for s in slots
                            ]
                            results.append(f"📅 {curr} (pax {pax}): {', '.join(times)}")
                except RateLimitHit:
                    logger.warning(f"Ad-hoc check hit 428 on {curr}")
                    rate_limited = True
                    break
                except UnauthorizedError as e:
                    logger.error(f"Ad-hoc check unauthorized: {e}")
                    await update.message.reply_text(
                        "❌ *Unauthorized Error*\n\nYour API key or Slug appears to be invalid.",
                        parse_mode="Markdown",
                    )
                    return
                except Exception as e:
                    logger.warning(f"Ad-hoc check error: {e}")

                await asyncio.sleep(1.5)  # Be gentle

            if rate_limited:
                break

        if results:
            msg = "✅ *Available Slots Found:*\n\n" + "\n".join(results)
            if rate_limited:
                msg += "\n\n⚠️ *Note:* Check was cut short due to provider rate limiting (verification challenge)."
        elif rate_limited:
            msg = (
                "⚡ *Rate Limit Hit*\n\n"
                "The provider is currently challenging our requests with a verification (Altcha/PoW).\n\n"
                "I couldn't complete the full scan. Please try again in 5-10 minutes."
            )
        else:
            msg = "😔 No available slots found in your configured window."

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in check_now: {e}")
        await update.message.reply_text("❌ An error occurred during the check.")
    finally:
        await adapter.close()


# ──────────────────────────────────
#  /book Flow — Date → Pax → Slots
# ──────────────────────────────────


async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the booking flow with a date picker keyboard."""
    if not update.message:
        return

    today = datetime.date.today()
    buttons = []
    row: list[InlineKeyboardButton] = []

    for i in range(settings.fetch_days_ahead):
        curr = today + datetime.timedelta(days=i)
        if curr.weekday() not in settings.allowed_weekdays:
            continue

        label = curr.strftime("%a %d %b")  # e.g. "Sat 08 Mar"
        row.append(
            InlineKeyboardButton(label, callback_data=f"book_date:{curr.isoformat()}")
        )

        if len(row) == 3:  # 3 buttons per row
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await update.message.reply_text(
        "📅 *Choose a date:*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """After user picks a date, show pax selector."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not query.data or context.user_data is None:
        return

    date_str = query.data.split(":")[1]
    context.user_data["book_date"] = date_str

    buttons = [
        [
            InlineKeyboardButton(f"👥 {pax} pax", callback_data=f"book_pax:{pax}")
            for pax in settings.pax_range
        ]
    ]

    await query.edit_message_text(
        f"📅 Date: *{date_str}*\n\n👥 *How many guests?*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def handle_pax_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """After user picks pax, fetch and display available time slots."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    pax = int(query.data.split(":")[1])
    date_str = (
        context.user_data.get("book_date", "") if context.user_data is not None else ""
    )

    await query.edit_message_text(
        f"🔍 Checking {date_str} for {pax} guests...",
        parse_mode="Markdown",
    )

    adapter = ProviderAdapter(
        settings.provider_base_url,
        settings.provider_api_key,
        settings.target_slug,
        settings.provider_origin,
        settings.provider_referer,
    )
    try:
        target_date = datetime.date.fromisoformat(date_str)
        slots = await adapter.get_slots(pax, target_date)

        # Filter by time range
        if slots and settings.time_range_start and settings.time_range_end:
            slots = [
                s
                for s in slots
                if settings.is_time_in_range(s.get("time", s.get("start_time", "")))
            ]

        if not slots:
            await query.edit_message_text(
                f"😔 No slots available for {date_str} ({pax} pax).\n\n"
                "Try /book to pick a different date.",
            )
            return

        # Show each slot as a button
        buttons = []
        for s in slots:
            time_val = s.get("time", s.get("start_time", "?"))
            slot_id = s.get("id", f"{date_str}_{time_val}")
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"🕐 {time_val}",
                        callback_data=f"book_slot:{slot_id}:{time_val}",
                    )
                ]
            )

        buttons.append(
            [InlineKeyboardButton("↩️ Back to dates", callback_data="book_back")]
        )

        await query.edit_message_text(
            f"📅 *{date_str}* — 👥 {pax} pax\n\n"
            "🕐 *Available times:*\n"
            "Tap a time to open the booking page:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
        )
    except RateLimitHit:
        await query.edit_message_text(
            "⚡ *Rate Limit Hit*\n\n"
            "The provider is currently challenging our automated requests with a verification (Altcha/PoW).\n\n"
            "Please try again in a few minutes or use the official website to book directly.",
            parse_mode="Markdown",
        )
    except UnauthorizedError as e:
        logger.error(f"Booking flow unauthorized: {e}")
        await query.edit_message_text(
            "❌ *Unauthorized Error*\n\nYour API key or Slug appears to be invalid.",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error in handle_pax_selection: {e}")
        await query.edit_message_text(
            "❌ *An error occurred* while checking availability. Please try again later.",
            parse_mode="Markdown",
        )
    finally:
        await adapter.close()


async def handle_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When user taps a time slot, provide the booking link."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split(":")
    time_val = parts[2] if len(parts) > 2 else "?"
    date_str = (
        context.user_data.get("book_date", "") if context.user_data is not None else ""
    )
    booking_url = f"https://reservation.provider.com/en/block/{settings.target_slug}"

    await query.edit_message_text(
        f"✅ *Great choice!*\n\n"
        f"📅 Date: {date_str}\n"
        f"🕐 Time: {time_val}\n\n"
        f"👉 [Open booking page]({booking_url})\n\n"
        "_Note: Complete the booking on the provider website. "
        "The slot may require a verification challenge._",
        parse_mode="Markdown",
    )


async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to date selection."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    # Simpler: just tell them to use /book again
    await query.edit_message_text(
        "↩️ Use /book to pick a new date.",
    )


# ──────────────────────────────────
#  Bot Runner
# ──────────────────────────────────


def run_bot():
    """Start the Telegram bot (standalone)."""
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set. Cannot start bot.")
        return

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(CommandHandler("book", book))

    # Register callback query handlers for inline keyboards
    app.add_handler(CallbackQueryHandler(handle_date_selection, pattern=r"^book_date:"))
    app.add_handler(CallbackQueryHandler(handle_pax_selection, pattern=r"^book_pax:"))
    app.add_handler(CallbackQueryHandler(handle_slot_selection, pattern=r"^book_slot:"))
    app.add_handler(CallbackQueryHandler(handle_back, pattern=r"^book_back$"))

    logger.info("🤖 Telegram bot starting...")
    print("🌅 Lembayung Telegram Bot is active and polling for updates...")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
