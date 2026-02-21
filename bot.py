import logging
import os
import json
import time
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, TimedOut, Conflict
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


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only handle messages from private chats.
    if update.effective_chat and update.effective_chat.type != "private":
        logger.info("Ignoring non-private chat in on_message: chat_type=%s chat_id=%s",
                    update.effective_chat.type, update.effective_chat.id)
        return

    if update.message is None:
        logger.warning("on_message called without a message object: %s", update)
        return

    # Preserve existing business logic: store draft and prompt for department.
    context.user_data["draft"] = update.message.text
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("IT", callback_data="DEPT_IT")],
            [InlineKeyboardButton("Marketing", callback_data="DEPT_MARKETING")],
            [InlineKeyboardButton("Operations", callback_data="DEPT_OPS")],
            [InlineKeyboardButton("Sales", callback_data="DEPT_SALES")],
        ]
    )
    await update.message.reply_text("Select department:", reply_markup=kb)


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


def format_task_message(task: dict) -> str:
    """Build a modern, formatted task summary based solely on stored task fields."""
    created_at = task.get("created_at", "")
    status = task.get("status", "new").upper()

    creator_username = task.get("creator_username")
    creator_name = task.get("creator_name")

    if creator_username:
        creator_display = f"@{creator_username}"
    elif creator_name:
        creator_display = creator_name
    else:
        creator_display = "(unknown user)"

    assigned = task.get("assigned_to")
    if isinstance(assigned, dict) and assigned.get("username"):
        assigned_display = f"@{assigned['username']}"
    elif isinstance(assigned, dict) and assigned.get("name"):
        assigned_display = assigned["name"]
    else:
        assigned_display = "—"

    lines = [
        "🚀 NEW INTERNAL TASK",
        "────────────────────",
        f"🆔 Task: {task.get('task_id', '')}",
        f"👤 From: {creator_display}",
        f"📂 Department: {task.get('department', '')}",
        f"📅 Created: {created_at}",
        f"📌 Status: {status}",
        f"👥 Assigned: {assigned_display}",
        "",
        "📝 Message:",
        "--------------------------------",
        task.get("original_message", ""),
        "--------------------------------",
    ]
    return "\n".join(lines)


def build_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for task lifecycle actions."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🟡 In Progress", callback_data=f"STATUS_PROGRESS_{task_id}"),
                InlineKeyboardButton("🟢 Done", callback_data=f"STATUS_DONE_{task_id}"),
            ],
            [
                InlineKeyboardButton("👤 Assign to Me", callback_data=f"ASSIGN_{task_id}"),
                InlineKeyboardButton("🔁 Escalate", callback_data=f"ESCALATE_{task_id}"),
            ],
        ]
    )


def get_task(task_id: str):
    """Helper to load a single task and its backing data structure."""
    data = load_data()
    tickets = data.setdefault("tickets", {})
    task = tickets.get(task_id)
    return task, data, tickets


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Temporary debug to confirm the message handler is firing.
    logger.info(
        "DEBUG message handler: chat_type=%s chat_id=%s",
        getattr(update.effective_chat, "type", None),
        getattr(update.effective_chat, "id", None),
    )

    if update.message is not None:
        await update.message.reply_text("DEBUG: message received")
    else:
        logger.debug("receive_message called without a message object: %s", update)

    # Wrapper to keep original on_message business logic intact.
    await on_message(update, context)


async def department_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new internal task and forward it to the department manager."""
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("DEPT_"):
        if q:
            await q.answer()
        return

    await q.answer()

    dept = q.data.replace("DEPT_", "", 1)
    if dept not in DEPT_MGR:
        await q.edit_message_text("Unknown department.")
        return

    user = update.effective_user

    # Original draft message from user_data, set in on_message
    original_text = context.user_data.get("draft", "")

    # Generate unique task ID
    task_id = make_id(dept)

    data = load_data()
    tickets = data.setdefault("tickets", {})

    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    task = {
        "task_id": task_id,
        "department": dept,
        "status": "new",
        "created_by": user.id if user else None,
        "creator_username": user.username if user else None,
        "creator_name": user.full_name if user else None,
        "created_at": created_at,
        "assigned_to": None,
        "messages": [],
        "original_message": original_text,
        "manager_chat_id": DEPT_MGR[dept],
        "manager_message_id": None,
    }

    if original_text:
        task["messages"].append(
            {
                "from": user.id if user else None,
                "text": original_text,
                "at": created_at,
            }
        )

    tickets[task_id] = task
    save_data(data)

    # Send formatted task to department manager
    mgr_chat_id = task["manager_chat_id"]
    text = format_task_message(task)
    keyboard = build_task_keyboard(task_id)

    try:
        sent = await context.bot.send_message(
            chat_id=mgr_chat_id,
            text=text,
            reply_markup=keyboard,
        )
        # Persist manager message metadata for future edits
        task["manager_message_id"] = sent.message_id
        tickets[task_id] = task
        save_data(data)
    except Exception as e:
        logger.exception("Failed to send task to manager chat: %s", e)

    await q.edit_message_text(f"Task created: {task_id}")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle status changes for tasks (in progress / done)."""
    q = update.callback_query
    if not q:
        return

    await q.answer()

    data_str = q.data or ""
    if not data_str.startswith("STATUS_"):
        return

    parts = data_str.split("_", 2)
    if len(parts) < 3:
        return

    _, action, task_id = parts
    task, data, tickets = get_task(task_id)
    if not task:
        await q.answer("Task not found.", show_alert=True)
        return

    if action == "PROGRESS":
        task["status"] = "in_progress"
    elif action == "DONE":
        task["status"] = "done"
    else:
        return

    tickets[task_id] = task
    save_data(data)

    text = format_task_message(task)
    keyboard = build_task_keyboard(task_id)

    chat_id = task.get("manager_chat_id")
    message_id = task.get("manager_message_id")

    try:
        if chat_id and message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
            )
        else:
            await q.edit_message_text(text=text, reply_markup=keyboard)
    except Exception as e:
        logger.exception("Failed to edit task message on status update: %s", e)


async def assign_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Assign the task to the callback user."""
    q = update.callback_query
    if not q:
        return

    await q.answer()

    data_str = q.data or ""
    if not data_str.startswith("ASSIGN_"):
        return

    _, task_id = data_str.split("_", 1)
    task, data, tickets = get_task(task_id)
    if not task:
        await q.answer("Task not found.", show_alert=True)
        return

    user = update.effective_user
    if not user:
        await q.answer("Cannot determine user.", show_alert=True)
        return

    task["assigned_to"] = {
        "id": user.id,
        "username": user.username,
        "name": user.full_name or (user.username or str(user.id)),
    }

    tickets[task_id] = task
    save_data(data)

    text = format_task_message(task)
    keyboard = build_task_keyboard(task_id)

    chat_id = task.get("manager_chat_id")
    message_id = task.get("manager_message_id")

    try:
        if chat_id and message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
            )
        else:
            await q.edit_message_text(text=text, reply_markup=keyboard)
    except Exception as e:
        logger.exception("Failed to edit task message on assign: %s", e)


async def escalate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log an escalation event on the task and refresh the message."""
    q = update.callback_query
    if not q:
        return

    await q.answer()

    data_str = q.data or ""
    if not data_str.startswith("ESCALATE_"):
        return

    _, task_id = data_str.split("_", 1)
    task, data, tickets = get_task(task_id)
    if not task:
        await q.answer("Task not found.", show_alert=True)
        return

    user = update.effective_user
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    task.setdefault("messages", []).append(
        {
            "event": "escalate",
            "by": user.id if user else None,
            "at": now,
        }
    )

    tickets[task_id] = task
    save_data(data)

    text = format_task_message(task)
    keyboard = build_task_keyboard(task_id)

    chat_id = task.get("manager_chat_id")
    message_id = task.get("manager_message_id")

    try:
        if chat_id and message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
            )
        else:
            await q.edit_message_text(text=text, reply_markup=keyboard)
    except Exception as e:
        logger.exception("Failed to edit task message on escalate: %s", e)


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
    application.add_handler(CallbackQueryHandler(assign_handler, pattern=r"^ASSIGN_"))
    application.add_handler(CallbackQueryHandler(escalate_handler, pattern=r"^ESCALATE_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message))

    return application


def main() -> None:
    logger.info("Starting Telegram bot worker process")

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
            conflict_backoff_seconds = conflict_initial_backoff_seconds

        except (NetworkError, TimedOut) as e:
            logger.warning(
                "Network-related error in polling (will retry in %s s): %s",
                backoff_seconds,
                repr(e),
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)

        except Conflict as e:
            logger.error(
                "getUpdates Conflict detected: %s. This usually means another instance "
                "is running with the same BOT_TOKEN (e.g. another Render worker, local "
                "process, or another host). Ensure ONLY ONE polling instance is active. "
                "Retrying in %s seconds.",
                repr(e),
                conflict_backoff_seconds,
            )
            time.sleep(conflict_backoff_seconds)
            conflict_backoff_seconds = min(
                conflict_backoff_seconds * 2,
                conflict_max_backoff_seconds,
            )

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
