import logging
import os
import json
import time
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


HAMID_ID = int(os.getenv("HAMID_ID", "722627622"))
FALLON_ID = int(os.getenv("FALLON_ID", "0"))

DEPT_MGR = {"IT": 722627622, "MARKETING": 722627622, "OPS": 722627622, "SALES": 722627622}
DATA_FILE = "tickets.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"tickets": {}, "daily_counter": {}}
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)


def make_id(prefix):
    today = datetime.now().strftime("%Y%m%d")
    d = load_data()
    d["daily_counter"].setdefault(today, 0)
    d["daily_counter"][today] += 1
    save_data(d)
    return f"{prefix}-{today}-{str(d['daily_counter'][today]).zfill(4)}"


async def start(u, c):
    await u.message.reply_text("Send your task message.")


async def show_id(u, c):
    await u.message.reply_text(f"Your ID: {u.effective_user.id}")


async def on_message(u, c):
    if u.effective_chat.type != "private":
        return
    c.user_data["draft"] = u.message.text
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("IT", callback_data="DEPT_IT")],
            [InlineKeyboardButton("Marketing", callback_data="DEPT_MARKETING")],
            [InlineKeyboardButton("Operations", callback_data="DEPT_OPS")],
            [InlineKeyboardButton("Sales", callback_data="DEPT_SALES")],
        ]
    )
    await u.message.reply_text("Select department:", reply_markup=kb)


async def on_dept(u, c):
    q = u.callback_query
    await q.answer()
    dept = q.data.replace("D_", "")
    if dept not in DEPT_MGR:
        await q.edit_message_text("Unknown.")
        return
    mgr = DEPT_MGR[dept]
    tid = make_id(dept)
    txt = c.user_data.get("draft", "")
    d = load_data()
    d["tickets"][tid] = {
        "staff_id": u.effective_user.id,
        "manager_id": mgr,
        "status": "OPEN",
    }
    save_data(d)
    msg = f"New Ticket: {tid}\nFrom: {u.effective_user.full_name}\nDept: {dept}\n\n{txt}"
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("In Progress", callback_data=f"STATUS_p_{tid}"),
                InlineKeyboardButton("Done", callback_data=f"STATUS_d_{tid}"),
            ]
        ]
    )
    try:
        await c.bot.send_message(mgr, msg, reply_markup=kb)
    except Exception:
        # Swallow manager notification errors; ticket is still created.
        pass
    await q.edit_message_text(f"Ticket created: {tid}")


async def on_status(u, c):
    q = u.callback_query
    await q.answer()
    parts = q.data.split("_", 2)
    if len(parts) < 3:
        return
    action, tid = parts[1], parts[2]
    d = load_data()
    t = d["tickets"].get(tid)
    if not t:
        return
    if u.effective_user.id != t["manager_id"]:
        await q.answer("Not authorized.", show_alert=True)
        return
    t["status"] = "IN_PROGRESS" if action == "p" else "DONE"
    save_data(d)
    await q.edit_message_text(f"{'🟡' if action == 'p' else '🟢'} {tid} — {t['status']}")


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Wrapper to keep original on_message business logic intact.
    await on_message(update, context)


async def department_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Adapt "DEPT_" prefix for the existing on_dept handler which expects "D_".
    q = update.callback_query
    if q and q.data and q.data.startswith("DEPT_"):
        q.data = "D_" + q.data[len("DEPT_") :]
    await on_dept(update, context)


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Adapt "STATUS_" prefix for the existing on_status handler which expects "S_".
    q = update.callback_query
    if q and q.data and q.data.startswith("STATUS_"):
        q.data = "S_" + q.data[len("STATUS_") :]
    await on_status(update, context)


def build_application() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Environment variable BOT_TOKEN is not set. Please configure BOT_TOKEN on Render."
        )

    application = ApplicationBuilder().token(token).build()

    # Register handlers exactly once
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", show_id))
    application.add_handler(CallbackQueryHandler(department_selected, pattern=r"^DEPT_"))
    application.add_handler(CallbackQueryHandler(status_handler, pattern=r"^STATUS_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message))

    return application


def main() -> None:
    logger.info("Starting Telegram bot worker process")

    initial_backoff_seconds = 5
    max_backoff_seconds = 300
    backoff_seconds = initial_backoff_seconds

    while True:
        try:
            application = build_application()

            logger.info("Starting Telegram bot polling...")
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                timeout=30,
                poll_interval=1.0,
            )

            logger.info("Polling stopped gracefully; restarting polling loop")
            backoff_seconds = initial_backoff_seconds

        except (NetworkError, TimedOut) as e:
            logger.warning(
                "Network-related error in polling (will retry in %s s): %s",
                backoff_seconds,
                repr(e),
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)

        except RuntimeError as e:
            logger.error("Fatal configuration error: %s", e)
            raise SystemExit(1)

        except Exception as e:
            logger.exception(
                "Unhandled exception in polling loop (will retry in %s s): %s",
                backoff_seconds,
                repr(e),
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)


if __name__ == "__main__":
    main()
