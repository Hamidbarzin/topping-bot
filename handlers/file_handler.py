import os
from telegram import Update
from telegram.ext import ContextTypes
from database import db

TASKS_HUB_CHAT_ID = int(os.getenv("TASKS_HUB_CHAT_ID", "0"))
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.chat.id != TASKS_HUB_CHAT_ID:
        return
    if not msg.reply_to_message:
        return

    # Find task linked to the replied message
    task = db.get_task_by_message(msg.chat.id, msg.reply_to_message.message_id)
    if not task:
        return

    task_id = task["task_id"]

    # Get file object
    if msg.document:
        file_obj = msg.document
        file_name = file_obj.file_name or f"doc_{file_obj.file_unique_id}"
    elif msg.photo:
        file_obj = msg.photo[-1]  # largest
        file_name = f"photo_{file_obj.file_unique_id}.jpg"
    else:
        return

    save_dir = os.path.join(STORAGE_DIR, f"task_{task_id}")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, file_name)

    tg_file = await file_obj.get_file()
    await tg_file.download_to_drive(save_path)

    db.update_task_file(task_id, save_path)

    await msg.reply_text(f"📎 File attached to TASK-{task_id:04d}\n📄 {file_name}")
