"""
Topping Internal Ticket Bot — PTB v20+
- Receives tickets from private or group chats.
- IT → Amir's group (Queue | Algorithm & Pricing) only.
- Marketing → Arian's NodeWest group only.
- No CEO copy to Hamid PV (Hamid is in both groups).
- Commands: /ticket, /task, /status <id>, /close <id>
"""
print("BOT VERSION: 2026-02-23 IT-ROUTING v1")

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # بارگذاری .env قبل از هر os.getenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("topping_bot")

# ---------------------------------------------------------------------------
# Config from ENV (validated on startup)
# ---------------------------------------------------------------------------
DATA_FILE = Path("tickets.json")


def _parse_int(val):
    """Parse env var to int (منفی برای chat_id گروه مجاز); return None if missing/invalid."""
    if val is None or val == "":
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


BOT_TOKEN = os.getenv("BOT_TOKEN")
HAMID_ID = _parse_int(os.getenv("HAMID_ID"))  # CEO / Admin (for /close auth; no ticket PV)
AMIR_ID = _parse_int(os.getenv("AMIR_ID"))    # IT Manager (optional DM; primary = group)
MOTAB_ID = _parse_int(os.getenv("MOTAB_ID"))  # Marketing Manager (optional DM; primary = group)

# Hardcoded group destinations (tickets posted here only; no Hamid PV copy)
AMIR_IT_GROUP_CHAT_ID = -1003894609250           # Queue | Algorithm & Pricing
NODEWEST_MARKETING_GROUP_CHAT_ID = -1003532849922  # Arian's NodeWest


def _manager_ids_ok():
    """True if we have at least Hamid and token."""
    return BOT_TOKEN and HAMID_ID is not None


def _dept_manager_ids():
    """Map department -> manager user_id. Uses Hamid for missing managers."""
    return {
        "IT": AMIR_ID if AMIR_ID is not None else HAMID_ID,
        "MARKETING": MOTAB_ID if MOTAB_ID is not None else HAMID_ID,
    }


def _format_ticket_card(ticket: dict) -> str:
    """Build ticket card text from ticket record (for send and edit)."""
    tid = ticket.get("ticket_id", "?")
    by_ = ticket.get("created_by", {}) or {}
    uid = by_.get("user_id", "?")
    uname = by_.get("username", uid)
    from_str = f"{uname} (id={uid})"
    source_title = ticket.get("source_chat_title", "?")
    source_id = ticket.get("source_chat_id", "?")
    dept = ticket.get("department", "?")
    status = ticket.get("status", "OPEN")
    msg_text = ticket.get("message_text", "")
    return (
        f"New Ticket: {tid}\n"
        f"From: {from_str}\n"
        f"Chat: {source_title} (id={source_id})\n"
        f"Dept: {dept}\n"
        f"Status: {status}\n\n{msg_text}"
    )


def _status_keyboard(ticket_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for In Progress / Done."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("In Progress", callback_data=f"S_p_{ticket_id}"),
            InlineKeyboardButton("Done", callback_data=f"S_d_{ticket_id}"),
        ],
    ])


# ---------------------------------------------------------------------------
# JSON storage (async-safe: run in thread to avoid blocking)
# ---------------------------------------------------------------------------
def _load_data_sync():
    if not DATA_FILE.exists():
        return {"tickets": {}, "daily_counter": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_data_sync(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


async def load_data():
    return await asyncio.to_thread(_load_data_sync)


async def save_data(data):
    await asyncio.to_thread(_save_data_sync, data)


async def make_ticket_id(prefix: str) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    data = await load_data()
    data.setdefault("daily_counter", {})
    data["daily_counter"].setdefault(today, 0)
    data["daily_counter"][today] += 1
    await save_data(data)
    n = data["daily_counter"][today]
    return f"{prefix}-{today}-{str(n).zfill(4)}"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome and hint to use /ticket or /task."""
    if not update.message:
        return
    await update.message.reply_text(
        "Send /ticket or /task to create a ticket. "
        "Then send your task message and choose the department."
    )


async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user_id, chat_id, chat_type. برای گرفتن chat_id گروه همینجا /id بزن."""
    if not update.message:
        return
    chat = update.message.chat
    user = update.message.from_user or update.effective_user
    user_id = user.id if user else "?"
    chat_id = chat.id if chat else "?"
    chat_type = getattr(chat, "type", "?") if chat else "?"
    await update.message.reply_text(
        f"user_id: {user_id}\n"
        f"chat_id: {chat_id}\n"
        f"chat_type: {chat_type}"
    )


async def cmd_testit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug: send a test message to IT group. /testit works in any chat."""
    if not update.message:
        return
    chat_id = -1003894609250
    text = "✅ IT group test: bot can post here."
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
        await update.message.reply_text("SENT to IT group")
    except Exception as e:
        logger.exception("testit failed: chat_id=%s", chat_id)
        await update.message.reply_text(f"FAILED: {type(e).__name__}")


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user_id, chat_id, chat_type. از message.chat استفاده می‌کنیم که همیشه هست."""
    if not update.message:
        return
    try:
        # منبع اصلی: message.chat و message.from_user (همیشه با پیام می‌آیند)
        chat = update.message.chat
        user = update.message.from_user or update.effective_user
        user_id = user.id if user else "?"
        chat_id = chat.id if chat else "?"
        chat_type = getattr(chat, "type", "?") if chat else "?"
        text = (
            f"user_id: {user_id}\n"
            f"chat_id: {chat_id}\n"
            f"chat_type: {chat_type}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        logger.exception("whoami failed: %s", e)
        await update.message.reply_text(f"Error: {e}")


async def debug_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """برای تست: هر پیام در گروه/سوپرگروه در ترمینال چاپ می‌شود. اگر این را می‌بینی = ربات پیام گروه را می‌گیرد."""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        print("GROUP MESSAGE RECEIVED:", chat_id)
        logger.info("GROUP MESSAGE RECEIVED: %s", chat_id)


async def cmd_ticket_or_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start ticket flow: ask for task message. Works in private and groups."""
    if not update.message or not update.effective_user:
        return
    context.user_data["awaiting_task"] = True
    await update.message.reply_text("Send your task message (one message), then I'll ask for the department.")


def _dept_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard: IT and Marketing only."""
    depts = [
        ("IT", "D_IT"),
        ("Marketing", "D_MARKETING"),
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=cb)] for label, cb in depts
    ])


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text message: only when user just sent /ticket or /task (draft + dept)."""
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    # In groups, only react if user is in "awaiting task" flow
    if update.effective_chat.type != "private" and not context.user_data.get("awaiting_task"):
        return
    if not context.user_data.get("awaiting_task"):
        return
    context.user_data["draft"] = update.message.text or "(no text)"
    context.user_data["awaiting_task"] = False
    await update.message.reply_text("Select department:", reply_markup=_dept_keyboard())


async def on_dept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose department: create ticket. Full card ONLY in destination group; source chat gets short confirmation only."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    raw = query.data or ""
    if not raw.startswith("D_"):
        return
    dept = raw.replace("D_", "")
    # Normalize: OTHER -> Hamid as manager
    dept_key = "OTHER" if dept == "OTHER" else dept
    dept_managers = _dept_manager_ids()
    if dept == "OTHER":
        manager_id = HAMID_ID
    else:
        manager_id = dept_managers.get(dept)
    if manager_id is None:
        await query.edit_message_text("Configuration error: no manager for this department. Contact admin.")
        return

    user = update.effective_user
    if not user:
        return
    draft = context.user_data.get("draft", "")
    context.user_data.pop("draft", None)

    logger.info("TICKET DEPT SELECT: dept_key=%s callback_data=%s", dept_key, raw)

    # Only IT and Marketing are supported; OTHER goes nowhere and no ticket is created
    if dept_key not in ("IT", "MARKETING"):
        await query.edit_message_text("Unsupported department. Use IT or Marketing.")
        return

    prefix = dept if dept != "OTHER" else "GEN"
    ticket_id = await make_ticket_id(prefix)
    chat = update.effective_chat
    source_chat_id = chat.id if chat else 0
    source_chat_title = getattr(chat, "title", None) or ("Private" if chat and chat.type == "private" else "")

    created_at = datetime.utcnow().isoformat() + "Z"
    ticket = {
        "ticket_id": ticket_id,
        "created_at": created_at,
        "created_by": {"user_id": user.id, "username": user.username or user.full_name or str(user.id)},
        "source_chat_id": source_chat_id,
        "source_chat_title": source_chat_title,
        "department": dept_key,
        "message_text": draft,
        "status": "OPEN",
        "manager_id": manager_id,
    }
    data = await load_data()
    data.setdefault("tickets", {})
    data["tickets"][ticket_id] = ticket
    await save_data(data)

    msg_body = _format_ticket_card(ticket)
    status_kb = _status_keyboard(ticket_id)

    # --- ROUTING: full ticket card ONLY in destination group. Store dest message_id for later edits. ---
    destination_chat_id = AMIR_IT_GROUP_CHAT_ID if dept_key == "IT" else NODEWEST_MARKETING_GROUP_CHAT_ID
    source_chat_id_log = update.effective_chat.id if update.effective_chat else None
    logger.info(
        "ROUTE DEBUG: ticket_id=%s dept_key=%r destination_chat_id=%s source_chat_id=%s",
        ticket_id, dept_key, destination_chat_id, update.effective_chat.id if update.effective_chat else None,
    )
    try:
        # 1) Send ticket card to destination group only
        sent_msg = await context.bot.send_message(destination_chat_id, msg_body, reply_markup=status_kb)
        # 2) Store destination_message_id for later status edits
        destination_message_id = sent_msg.message_id
        ticket["destination_chat_id"] = destination_chat_id
        ticket["destination_message_id"] = destination_message_id
        data["tickets"][ticket_id] = ticket
        await save_data(data)
        # 3) Log
        logger.info(
            "Ticket routed: ticket_id=%s dept=%s source_chat=%s dest_chat=%s dest_msg=%s",
            ticket_id, dept_key, source_chat_id_log, destination_chat_id, destination_message_id,
        )
        # 4) Only then send confirmation to source chat (only on success)
        confirmation = f"✅ Ticket {ticket_id} routed to IT group." if dept_key == "IT" else f"✅ Ticket {ticket_id} routed to NodeWest marketing group."
        await query.edit_message_text(confirmation)
    except Exception as e:
        logger.exception("Failed to send ticket %s to chat_id=%s: %s", ticket_id, destination_chat_id, e)
        await query.edit_message_text("❌ Failed to route ticket to department group.")


async def on_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """In Progress / Done: update status in storage and edit the same ticket message in the destination group."""
    query = update.callback_query
    if not query:
        return
    raw = query.data or ""
    if not raw.startswith("S_") or raw.count("_") < 2:
        return
    parts = raw.split("_", 2)
    action, ticket_id = parts[1], parts[2]
    data = await load_data()
    ticket = data.get("tickets", {}).get(ticket_id)
    if not ticket:
        await query.answer("Ticket not found.", show_alert=True)
        return
    manager_id = ticket.get("manager_id")
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id != manager_id and user_id != HAMID_ID:
        await query.answer("Not authorized to change status.", show_alert=True)
        return
    ticket["status"] = "IN_PROGRESS" if action == "p" else "DONE"
    await save_data(data)

    destination_chat_id = ticket.get("destination_chat_id")
    destination_message_id = ticket.get("destination_message_id")
    if destination_chat_id is None or destination_message_id is None:
        await query.answer("Cannot update ticket message (missing message_id).", show_alert=True)
        return
    new_msg_body = _format_ticket_card(ticket)
    updated_kb = _status_keyboard(ticket_id)
    try:
        await context.bot.edit_message_text(
            chat_id=destination_chat_id,
            message_id=destination_message_id,
            text=new_msg_body,
            reply_markup=updated_kb,
        )
        await query.answer("Updated")
    except Exception as e:
        logger.exception("Failed to edit ticket message %s: %s", ticket_id, e)
        await query.answer("Status saved but could not update message.", show_alert=True)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show status of a ticket: /status <ticket_id>."""
    if not update.message:
        return
    args = (context.args or [])
    if not args:
        await update.message.reply_text("Usage: /status <ticket_id>")
        return
    ticket_id = args[0].strip()
    data = await load_data()
    ticket = data.get("tickets", {}).get(ticket_id)
    if not ticket:
        await update.message.reply_text(f"Ticket not found: {ticket_id}")
        return
    created = ticket.get("created_at", "?")[:16]
    by_ = ticket.get("created_by", {})
    by_str = by_.get("username", by_.get("user_id", "?"))
    text = (
        f"Ticket: {ticket_id}\n"
        f"Status: {ticket.get('status', '?')}\n"
        f"Department: {ticket.get('department', '?')}\n"
        f"Created: {created} by {by_str}\n"
        f"Message: {ticket.get('message_text', '')[:200]}"
    )
    await update.message.reply_text(text)


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Close a ticket. Only Hamid or the ticket's department manager."""
    if not update.message or not update.effective_user:
        return
    args = (context.args or [])
    if not args:
        await update.message.reply_text("Usage: /close <ticket_id>")
        return
    ticket_id = args[0].strip()
    data = await load_data()
    ticket = data.get("tickets", {}).get(ticket_id)
    if not ticket:
        await update.message.reply_text(f"Ticket not found: {ticket_id}")
        return
    user_id = update.effective_user.id
    manager_id = ticket.get("manager_id")
    if user_id != manager_id and user_id != HAMID_ID:
        await update.message.reply_text("You are not allowed to close this ticket.")
        return
    ticket["status"] = "CLOSED"
    await save_data(data)
    await update.message.reply_text(f"Ticket {ticket_id} closed.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors (no PV notifications to Hamid)."""
    logger.error("Update %s caused error: %s", update, context.error, exc_info=context.error)


def main() -> None:
    """Validate config, build app, run polling."""
    print("BOT LOADED FROM:", __file__)  # اگر این را ندیدی یعنی فایل دیگری اجرا می‌شود
    print("DEBUG BOT_TOKEN:", "OK" if (BOT_TOKEN and BOT_TOKEN.strip()) else "NOT SET")
    if not BOT_TOKEN or not BOT_TOKEN.strip():
        logger.error("BOT_TOKEN is not set. Set it in the environment and restart.")
        raise SystemExit(1)
    if HAMID_ID is None:
        logger.error("HAMID_ID is not set. Set it in the environment (e.g. HAMID_ID=722627622).")
        raise SystemExit(1)
    if AMIR_ID is None:
        logger.warning("AMIR_ID is not set. IT tickets will be assigned to Hamid. Set AMIR_ID for IT manager.")
    if MOTAB_ID is None:
        logger.warning("MOTAB_ID is not set. Set MOTAB_ID for Marketing manager (routing uses hardcoded groups).")

    app = (
        Application.builder()
        .token(BOT_TOKEN.strip())
        .post_init(_drop_webhook)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("testit", cmd_testit))
    app.add_handler(CommandHandler("ticket", cmd_ticket_or_task))
    app.add_handler(CommandHandler("task", cmd_ticket_or_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CallbackQueryHandler(on_dept_callback, pattern=r"^D_"))
    app.add_handler(CallbackQueryHandler(on_status_callback, pattern=r"^S_"))
    app.add_handler(
        MessageHandler(
            (filters.ChatType.PRIVATE | filters.ChatType.GROUP | filters.ChatType.SUPERGROUP)
            & filters.TEXT
            & ~filters.COMMAND,
            on_message,
        )
    )
    # دیباگ: هر پیام در گروه/سوپرگروه → چاپ در ترمینال (group=1 تا هندلرهای دیگر بلاک نشوند)
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUP | filters.ChatType.SUPERGROUP,
            debug_group,
        ),
        group=1,
    )
    app.add_error_handler(error_handler)

    # Webhook در post_init (_drop_webhook) صفر می‌شود. allowed_updates=ALL_TYPES تا گروه/سوپرگروه بیاید.
    logger.info("Starting polling (drop_pending_updates=True, allowed_updates=Update.ALL_TYPES).")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


async def _drop_webhook(application: Application) -> None:
    """Ensure no webhook is set so polling works."""
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared for polling.")
    except Exception as e:
        logger.warning("Could not delete webhook (may be fine if never set): %s", e)


if __name__ == "__main__":
    main()
