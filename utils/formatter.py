from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

DEPARTMENTS = {
    "IT": "🖥 IT",
    "MARKETING": "📣 Marketing",
    "OPS": "⚙️ Operations",
    "RD": "🔬 R&D",
    "GENERAL": "🏢 General",
}

STATUS_EMOJI = {
    "Open": "🔴",
    "InProgress": "🟡",
    "Done": "🟢",
    "Escalated": "🚨",
}


def format_task_card(task: dict) -> str:
    dept_label = DEPARTMENTS.get(task["department"], task["department"])
    status_label = f"{STATUS_EMOJI.get(task['status'], '⚪')} {task['status']}"
    assigned = f"\n👤 Assigned: @{task['assigned_to']}" if task.get("assigned_to") else ""
    file_note = "\n📎 File attached" if task.get("file_path") else ""
    created = task.get("created_at", "")
    try:
        dt = datetime.fromisoformat(str(created))
        time_str = dt.strftime("%H:%M - %d %b %Y")
    except Exception:
        time_str = str(created)[:16]

    return (
        f"🎫 TASK-{task['task_id']:04d}\n"
        f"📁 Department: {dept_label}\n"
        f"👤 From: @{task['creator']}\n"
        f"📝 {task['description']}\n"
        f"🕐 {time_str}\n"
        f"📊 Status: {status_label}"
        f"{assigned}"
        f"{file_note}"
    )


def build_task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟡 In Progress", callback_data=f"STATUS_PROGRESS_{task_id}"),
            InlineKeyboardButton("🟢 Done",        callback_data=f"STATUS_DONE_{task_id}"),
        ],
        [
            InlineKeyboardButton("👤 Assign to Me", callback_data=f"ASSIGN_{task_id}"),
            InlineKeyboardButton("🔁 Escalate",     callback_data=f"ESCALATE_{task_id}"),
        ],
    ])


def parse_task_command(text: str):
    """
    /task IT Website is down
    Returns (department, description) or (None, None) on error.
    """
    parts = text.strip().split(None, 2)
    # parts[0] = /task, parts[1] = DEPT, parts[2] = description
    if len(parts) < 3:
        return None, None
    dept = parts[1].upper()
    if dept not in DEPARTMENTS:
        return None, None
    return dept, parts[2]
