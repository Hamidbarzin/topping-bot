import os
from telegram import Update
from telegram.ext import ContextTypes
from database import db
from utils.formatter import format_task_card, build_task_keyboard, parse_task_command

TASKS_HUB_CHAT_ID = int(os.getenv("TASKS_HUB_CHAT_ID", "0"))
GM_DASHBOARD_CHAT_ID = int(os.getenv("GM_DASHBOARD_CHAT_ID", "0"))
GENERAL_GROUP_CHAT_ID = int(os.getenv("GENERAL_GROUP_CHAT_ID", "0"))


async def create_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != TASKS_HUB_CHAT_ID:
        return

    dept, description = parse_task_command(update.message.text)
    if not dept or not description:
        await update.message.reply_text(
            "❌ Usage: /task [DEPARTMENT] [description]\n"
            "Departments: IT, MARKETING, OPS, RD, GENERAL\n\n"
            "Example: /task IT Website is down"
        )
        return

    user = update.effective_user
    creator = user.username or str(user.id)

    task = db.create_task(
        department=dept,
        creator=creator,
        description=description,
        chat_id=chat_id,
    )

    text = format_task_card(task)
    keyboard = build_task_keyboard(task["task_id"])
    sent = await update.message.reply_text(text, reply_markup=keyboard)

    db.update_task_message(task["task_id"], sent.chat_id, sent.message_id)

    if GM_DASHBOARD_CHAT_ID:
        await context.bot.send_message(
            GM_DASHBOARD_CHAT_ID,
            f"🆕 New task:\n\n{text}",
            reply_markup=keyboard,
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # GM sees all
    is_gm = (chat_id == GM_DASHBOARD_CHAT_ID)
    tasks = db.get_open_tasks() if is_gm else db.get_open_tasks(creator=user.username or str(user.id))

    if not tasks:
        await update.message.reply_text("✅ No open tasks.")
        return

    lines = [f"📋 Open Tasks ({len(tasks)})\n"]
    for t in tasks:
        from utils.formatter import STATUS_EMOJI
        emoji = STATUS_EMOJI.get(t["status"], "⚪")
        assigned = f" → @{t['assigned_to']}" if t.get("assigned_to") else ""
        lines.append(f"{emoji} TASK-{t['task_id']:04d} [{t['department']}] {t['description'][:40]}{assigned}")

    await update.message.reply_text("\n".join(lines))
