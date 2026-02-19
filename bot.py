import os
import json
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

HAMID_ID = int(os.getenv("HAMID_ID", "0"))
FALLON_ID = int(os.getenv("FALLON_ID", "0"))

# 🔹 مدیر هر دپارتمان
DEPARTMENT_MANAGER = {
    "IT": 111111111,
    "MARKETING": 222222222,
    "OPS": 333333333,
    "SALES": 444444444,
}

DATA_FILE = "tickets.json"

# ================= STORAGE =================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"tickets": {}, "daily_counter": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def generate_ticket_id(prefix):
    today = datetime.now().strftime("%Y%m%d")
    data = load_data()

    if today not in data["daily_counter"]:
        data["daily_counter"][today] = 0

    data["daily_counter"][today] += 1
    counter = str(data["daily_counter"][today]).zfill(4)

    save_data(data)
    return f"{prefix}-{today}-{counter}"

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send your task message.\nYou will then select department."
    )

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID:\n{update.effective_user.id}")

# ================= CREATE FLOW =================

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    context.user_data["draft"] = update.message.text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("IT", callback_data="dept|IT")],
        [InlineKeyboardButton("Marketing", callback_data="dept|MARKETING")],
        [InlineKeyboardButton("Operations", callback_data="dept|OPS")],
        [InlineKeyboardButton("Sales", callback_data="dept|SALES")],
    ])

    await update.message.reply_text(
        "Select department:",
        reply_markup=keyboard
    )

# ================= DEPARTMENT SELECT =================

async def department_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, dept = query.data.split("|")

    if dept not in DEPARTMENT_MANAGER:
        return

    manager_id = DEPARTMENT_MANAGER[dept]
    ticket_id = generate_ticket_id(dept)

    message_text = context.user_data.get("draft", "")

    data = load_data()
    data["tickets"][ticket_id] = {
        "staff_id": update.effective_user.id,
        "manager_id": manager_id,
        "status": "OPEN"
    }
    save_data(data)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟡 In Progress", callback_data=f"progress|{ticket_id}"),
            InlineKeyboardButton("🟢 Done", callback_data=f"done|{ticket_id}")
        ]
    ])

    formatted = (
        f"📩 New Task\n\n"
        f"Ticket: {ticket_id}\n"
        f"From: {update.effective_user.full_name}\n"
        f"Department: {dept}\n\n"
        f"{message_text}"
    )

    # ارسال به مدیر مقصد
    await context.bot.send_message(
        chat_id=manager_id,
        text=formatted,
        reply_markup=keyboard
    )

    # ارسال به Hamid و Fallon (نظارت)
    await context.bot.send_message(chat_id=HAMID_ID, text=formatted)
    await context.bot.send_message(chat_id=FALLON_ID, text=formatted)

    await query.edit_message_text(f"✅ Ticket created:\n{ticket_id}")

# ================= STATUS HANDLER =================

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, ticket_id = query.data.split("|")

    data = load_data()
    ticket = data["tickets"].get(ticket_id)

    if not ticket:
        return

    if update.effective_user.id != ticket["manager_id"]:
        await query.answer("Not authorized", show_alert=True)
        return

    if action == "progress":
        ticket["status"] = "IN_PROGRESS"
        await query.edit_message_text(f"🟡 {ticket_id}\nStatus: IN PROGRESS")

    elif action == "done":
        ticket["status"] = "DONE"
        await query.edit_message_text(f"🟢 {ticket_id}\nStatus: DONE")

    save_data(data)

# ================= MAIN =================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))

    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, receive_message))

    app.add_handler(CallbackQueryHandler(department_selected, pattern="^dept"))
    app.add_handler(CallbackQueryHandler(status_handler, pattern="^(progress|done)"))

    app.run_polling()

if __name__ == "__main__":
    main()

