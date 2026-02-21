import os
from telegram import Update
from telegram.ext import ContextTypes
from database import db

TASKS_HUB_CHAT_ID = int(os.getenv("TASKS_HUB_CHAT_ID", "0"))
GM_DASHBOARD_CHAT_ID = int(os.getenv("GM_DASHBOARD_CHAT_ID", "0"))
GENERAL_GROUP_CHAT_ID = int(os.getenv("GENERAL_GROUP_CHAT_ID", "0"))

ALLOWED_ANNOUNCE_CHATS = {TASKS_HUB_CHAT_ID, GM_DASHBOARD_CHAT_ID}


async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ALLOWED_ANNOUNCE_CHATS:
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /announce [message]")
        return

    user = update.effective_user
    sender = user.username or str(user.id)
    db.log_announcement(sender, msg)

    text = f"📢 Announcement from @{sender}:\n\n{msg}"
    sent_count = 0
    for chat_id in {TASKS_HUB_CHAT_ID, GENERAL_GROUP_CHAT_ID, GM_DASHBOARD_CHAT_ID}:
        if chat_id and chat_id != update.effective_chat.id:
            try:
                await context.bot.send_message(chat_id, text)
                sent_count += 1
            except Exception:
                pass

    await update.message.reply_text(f"✅ Announcement sent to {sent_count} group(s).")
