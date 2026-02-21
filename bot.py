import os
import logging
import time
import socket
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import Conflict, NetworkError

from database.db import init_db
from handlers.task_handler import create_task, status_command
from handlers.callback_handler import handle_callback
from handlers.file_handler import handle_file
from handlers.announce_handler import announce

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GM_DASHBOARD_CHAT_ID = int(os.getenv("GM_DASHBOARD_CHAT_ID", "0"))


async def daily_summary(context: ContextTypes.DEFAULT_TYPE):
    """Send daily open-task summary to GM at 9:00 AM."""
    from database.db import get_all_open_tasks
    from utils.formatter import STATUS_EMOJI

    tasks = get_all_open_tasks()
    if not tasks:
        text = "☀️ Good morning! No open tasks today."
    else:
        lines = [f"☀️ Daily Summary — {len(tasks)} open task(s)\n"]
        for t in tasks:
            emoji = STATUS_EMOJI.get(t["status"], "⚪")
            assigned = f" → @{t['assigned_to']}" if t.get("assigned_to") else ""
            lines.append(
                f"{emoji} TASK-{t['task_id']:04d} [{t['department']}] {t['description'][:50]}{assigned}"
            )
        text = "\n".join(lines)

    if GM_DASHBOARD_CHAT_ID:
        await context.bot.send_message(GM_DASHBOARD_CHAT_ID, text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler to log exceptions from all handlers."""
    logger.error("Unhandled exception while handling update: %s", context.error, exc_info=context.error)

    if isinstance(context.error, Conflict):
        logger.error(
            "Conflict error inside handler: %s. This usually means another instance is polling "
            "with the same BOT_TOKEN. Ensure worker instances=1 and no other service or local "
            "process is running this bot.",
            repr(context.error),
        )


_WEBHOOK_CLEARED = False


async def post_init(app):
    """Run once per process: delete webhook and notify GM dashboard."""
    global _WEBHOOK_CLEARED

    if not _WEBHOOK_CLEARED:
        try:
            await app.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted successfully at startup (drop_pending_updates=True)")
        except Exception as e:
            logger.warning("Failed to delete webhook on startup: %s", e)

        _WEBHOOK_CLEARED = True

    if GM_DASHBOARD_CHAT_ID:
        try:
            await app.bot.send_message(GM_DASHBOARD_CHAT_ID, "✅ Topping Bot is online and ready.")
        except Exception as e:
            logger.warning("Failed to send online notification to GM dashboard: %s", e)


def build_app():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("task", create_task))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("announce", announce))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # File / photo attachments
    app.add_handler(
        MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file)
    )

    # Error handler
    app.add_error_handler(error_handler)

    # Daily summary job at 09:00 UTC
    app.job_queue.run_daily(daily_summary, time=__import__("datetime").time(9, 0, 0))

    return app


def main():
    init_db()
    logger.info("Database initialized.")

    hostname = socket.gethostname()
    pid = os.getpid()
    logger.info("Starting Topping Ops bot worker | instance=%s pid=%s", hostname, pid)

    # Backoff for generic network issues
    initial_backoff_seconds = 5
    max_backoff_seconds = 300
    backoff_seconds = initial_backoff_seconds

    # Separate backoff for Conflict errors (duplicate getUpdates)
    conflict_initial_backoff_seconds = 30
    conflict_max_backoff_seconds = 600  # 10 minutes cap
    conflict_backoff_seconds = conflict_initial_backoff_seconds

    while True:
        try:
            app = build_app()
            logger.info("Starting bot polling...")
            app.run_polling(drop_pending_updates=True)

            logger.info("Polling stopped gracefully; restarting polling loop")
            backoff_seconds = initial_backoff_seconds
            conflict_backoff_seconds = conflict_initial_backoff_seconds

        except Conflict as e:
            logger.error(
                "getUpdates Conflict detected: %s. Another instance is likely polling with the "
                "same BOT_TOKEN (e.g. extra worker, local process, or another service). Ensure "
                "worker instances=1 and no duplicate service uses this BOT_TOKEN. Retrying in %s "
                "seconds.",
                repr(e),
                conflict_backoff_seconds,
            )
            time.sleep(conflict_backoff_seconds)
            conflict_backoff_seconds = min(
                conflict_backoff_seconds * 2,
                conflict_max_backoff_seconds,
            )

        except NetworkError as e:
            logger.warning(
                "Network error in polling (will retry in %s s): %s",
                backoff_seconds,
                repr(e),
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)

        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break

        except Exception as e:
            logger.exception(
                "Unexpected exception in polling loop (will retry in %s s): %s",
                backoff_seconds,
                repr(e),
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)


if __name__ == "__main__":
    main()
