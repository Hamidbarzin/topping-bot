import os
import uuid
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Conversation states
SELECT_DEPT, SELECT_NODE, ASK_TITLE, ASK_DESC = range(4)

DEPTS = [
    ("IT", "🧰 IT"),
    ("MARKETING", "📣 Marketing"),
    ("SEO", "🔎 SEO & Google"),
    ("LOGISTICS", "🚚 Logistics"),
    ("ALGO", "🧠 Algorithm & Pricing"),
    ("MEETING", "📅 Book Meeting"),
    ("URGENT", "🚨 Urgent Escalation"),
]

# 5 Nodes (همون‌هایی که ساختی)
NODES = [
    ("WEST", "Node | West"),
    ("EAST", "Node | East"),
    ("MIDTOWN", "Node | Midtown"),
    ("NORTH", "Node | North"),
    ("DOWNTOWN", "Node | Downtown"),
    ("NA", "N/A (No Node)"),
]

def make_ticket_id() -> str:
    return datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Type /menu to submit a request.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(label, callback_data=key)] for key, label in DEPTS]
    await update.message.reply_text(
        "Select request type (Dept):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SELECT_DEPT

async def select_dept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["dept"] = query.data

    node_keyboard = [[InlineKeyboardButton(label, callback_data=f"NODE::{key}")] for key, label in NODES]
    await query.edit_message_text(
        "Select node (if applicable):",
        reply_markup=InlineKeyboardMarkup(node_keyboard),
    )
    return SELECT_NODE

async def select_node(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    node_key = query.data.split("::", 1)[1]
    context.user_data["node"] = node_key

    await query.edit_message_text("Title? (short)")
    return ASK_TITLE

async def ask_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("Description? (details + deadline if any)")
    return ASK_DESC

async def ask_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()

    dept = context.user_data.get("dept", "UNKNOWN")
    node = context.user_data.get("node", "NA")
    title = context.user_data.get("title", "")
    ticket_id = make_ticket_id()

    user = update.effective_user
    requester = f"{user.full_name} (@{user.username})" if user.username else user.full_name

    ticket_msg = (
        f"🟦 **NEW TICKET**  |  `{ticket_id}`\n"
        f"**Dept:** {dept}\n"
        f"**Node:** {node}\n"
        f"**Title:** {title}\n"
        f"**From:** {requester}\n\n"
        f"**Description:**\n{desc}\n\n"
        f"**Status:** OPEN"
    )

    await update.message.reply_text(ticket_msg, parse_mode="Markdown")

    for k in ("dept", "node", "title"):
        context.user_data.pop(k, None)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN environment variable first (BOT_TOKEN).")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("menu", menu)],
        states={
            SELECT_DEPT: [CallbackQueryHandler(select_dept)],
            SELECT_NODE: [CallbackQueryHandler(select_node, pattern=r"^NODE::")],
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_title)],
            ASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_desc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("Bot running... Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

