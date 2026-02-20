print("🔥 FILE LOADED")

import os
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG (از Render Environment میاد)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
HAMID_ID = int(os.getenv("HAMID_ID", "0"))
FALLON_ID = int(os.getenv("FALLON_ID", "0"))

DEPARTMENT_MANAGER = {
    "IT":        111111111,
    "MARKETING": 222222222,
    "OPS":       333333333,
    "SALES":     444444444,
}

DATA_FILE = "tickets.json"

# =========================
# STORAGE
# =========================
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

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send your task message and I'll ask you to select a department."
    )

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID:\n`{update.effective_user.id}`")

# =========================
# STEP 1: کاربر پیام میده → انتخاب دپارتمان
# =========================
async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    text = update.message.text.strip()

    # اگر گروه بود، مستقیم تیکت بساز (بدون انتخاب دپارتمان)
    if chat.type in ("group", "supergroup"):
        context.user_data["draft"] = text

        # برای مثال: پیشفرض OPS
        dept = "OPS"
        ticket_id = generate_ticket_id(dept)

        data = load_data()
        data["tickets"][ticket_id] = {
            "text": text,
            "dept": dept,
            "status": "OPEN",
            "manager_id": DEPARTMENT_MANAGER.get(dept),
        }
        save_data(data)

        await update.message.reply_text(f"✅ Ticket created: {ticket_id}")
        return

    # اگر PV بود → انتخاب دپارتمان
    context.user_data["draft"] = text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💻 IT", callback_data="DEPT_IT")],
        [InlineKeyboardButton("📣 Marketing", callback_data="DEPT_MARKETING")],
        [InlineKeyboardButton("🚚 Operations", callback_data="DEPT_OPS")],
        [InlineKeyboardButton("💼 Sales", callback_data="DEPT_SALES")],
    ])

    await update.message.reply_text("Select department:", reply_markup=keyboard)
# =========================
# STEP 2: انتخاب دپارتمان → ساخت تیکت
# =========================
async def department_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # callback_data = "DEPT_IT" → dept = "IT"
    dept = query.data.replace("DEPT_", "")

    if dept not in DEPARTMENT_MANAGER:
        await query.edit_message_text("Unknown department.")
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
            InlineKeyboardButton("🟡 In Progress", callback_data=f"STATUS_progress_{ticket_id}"),
            InlineKeyboardButton("🟢 Done", callback_data=f"STATUS_done_{ticket_id}")
        ]
    ])

    formatted = (
        f"📩 *New Task*\n\n"
        f"*Ticket:* `{ticket_id}`\n"
        f"*From:* {update.effective_user.full_name}\n"
        f"*Dept:* {dept}\n\n"
        f"{message_text}"
    )

    # ارسال به مدیر دپارتمان
    try:
        await context.bot.send_message(
            chat_id=manager_id,
            text=formatted,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception:
        pass

    # ارسال کپی به Hamid (نظارت)
    if HAMID_ID and HAMID_ID != manager_id:
        try:
            await context.bot.send_message(
                chat_id=HAMID_ID,
                text=f"[COPY] {formatted}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ارسال کپی به Fallon (نظارت)
    if FALLON_ID and FALLON_ID != manager_id:
        try:
            await context.bot.send_message(
                chat_id=FALLON_ID,
                text=f"[COPY] {formatted}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    await query.edit_message_text(f"✅ Ticket created: `{ticket_id}`")

# =========================
# STEP 3: Status update توسط مدیر
# =========================
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # callback_data = "STATUS_progress_OPS-20260219-0001"
    parts = query.data.split("_", 2)
    if len(parts) < 3:
        return

    action = parts[1]      # "progress" یا "done"
    ticket_id = parts[2]   # "OPS-20260219-0001"

    data = load_data()
    ticket = data["tickets"].get(ticket_id)

    if not ticket:
        return

    if update.effective_user.id != ticket["manager_id"]:
        await query.answer("Not authorized.", show_alert=True)
        return

    if action == "progress":
        ticket["status"] = "IN_PROGRESS"
        save_data(data)
        await query.edit_message_text(f"🟡 `{ticket_id}`\nStatus: IN PROGRESS")

    elif action == "done":
        ticket["status"] = "DONE"
        save_data(data)
        await query.edit_message_text(f"🟢 `{ticket_id}`\nStatus: DONE")

# =========================
# MAIN
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))

    # انتخاب دپارتمان
    app.add_handler(CallbackQueryHandler(department_selected, pattern=r"^DEPT_"))

    # آپدیت وضعیت
    app.add_handler(CallbackQueryHandler(status_handler, pattern=r"^STATUS_"))

    # پیام های متنی (PV + Group)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message))

    print("Bot started.")
    app.run_polling(drop_pending_updates=True)
