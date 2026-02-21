import os
from telegram import Update
from telegram.ext import ContextTypes
from database import db
from utils.formatter import format_task_card, build_task_keyboard

GM_DASHBOARD_CHAT_ID = int(os.getenv("GM_DASHBOARD_CHAT_ID", "0"))


def parse_callback(data: str):
    parts = data.split("_", 2)
    return parts if len(parts) == 3 else (None, None, None)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kind, action, id_str = parse_callback(q.data)
    if not id_str:
        return

    task_id = int(id_str)
    task = db.get_task(task_id)
    if not task:
        await q.answer("Task not found.", show_alert=True)
        return

    user = update.effective_user
    username = user.username or str(user.id)

    if kind == "STATUS":
        new_status = "InProgress" if action == "PROGRESS" else "Done"
        task = db.update_task_status(task_id, status=new_status)
        gm_msg = f"{'✅' if new_status == 'Done' else '🟡'} TASK-{task_id:04d} → {new_status} (by @{username})"

    elif kind == "ASSIGN":
        task = db.update_task_status(task_id, assigned_to=username)
        gm_msg = f"👤 TASK-{task_id:04d} assigned to @{username}"

    elif kind == "ESCALATE":
        task = db.update_task_status(task_id, status="Escalated")
        gm_msg = f"🚨 TASK-{task_id:04d} ESCALATED by @{username}"

    else:
        return

    text = format_task_card(task)
    keyboard = build_task_keyboard(task_id)

    await q.edit_message_text(text, reply_markup=keyboard)

    if GM_DASHBOARD_CHAT_ID and GM_DASHBOARD_CHAT_ID != q.message.chat_id:
        await context.bot.send_message(GM_DASHBOARD_CHAT_ID, gm_msg)
