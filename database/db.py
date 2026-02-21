import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "topping_ops.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            department  TEXT NOT NULL,
            creator     TEXT,
            assigned_to TEXT,
            description TEXT,
            status      TEXT NOT NULL DEFAULT 'Open',
            file_path   TEXT,
            message_id  INTEGER,
            chat_id     INTEGER,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            sender   TEXT,
            message  TEXT,
            sent_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def create_task(department, creator, description, chat_id, message_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (department, creator, description, chat_id, message_id)
               VALUES (?, ?, ?, ?, ?)""",
            (department.upper(), creator, description, chat_id, message_id),
        )
        return get_task(cur.lastrowid)


def get_task(task_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return dict(row) if row else None


def update_task_message(task_id, chat_id, message_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET chat_id=?, message_id=?, updated_at=? WHERE task_id=?",
            (chat_id, message_id, datetime.utcnow(), task_id),
        )


def update_task_status(task_id, status=None, assigned_to=None):
    with get_conn() as conn:
        if status and assigned_to:
            conn.execute(
                "UPDATE tasks SET status=?, assigned_to=?, updated_at=? WHERE task_id=?",
                (status, assigned_to, datetime.utcnow(), task_id),
            )
        elif status:
            conn.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
                (status, datetime.utcnow(), task_id),
            )
        elif assigned_to:
            conn.execute(
                "UPDATE tasks SET assigned_to=?, updated_at=? WHERE task_id=?",
                (assigned_to, datetime.utcnow(), task_id),
            )
    return get_task(task_id)


def update_task_file(task_id, file_path):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET file_path=?, updated_at=? WHERE task_id=?",
            (file_path, datetime.utcnow(), task_id),
        )


def get_task_by_message(chat_id, message_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE chat_id=? AND message_id=?",
            (chat_id, message_id),
        ).fetchone()
        return dict(row) if row else None


def get_open_tasks(department=None, creator=None):
    with get_conn() as conn:
        if department:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status != 'Done' AND department=? ORDER BY task_id DESC",
                (department.upper(),),
            ).fetchall()
        elif creator:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status != 'Done' AND creator=? ORDER BY task_id DESC",
                (creator,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status != 'Done' ORDER BY task_id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_all_open_tasks():
    return get_open_tasks()


def log_announcement(sender, message):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO announcements (sender, message) VALUES (?, ?)",
            (sender, message),
        )
