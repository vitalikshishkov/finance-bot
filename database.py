import json
import aiosqlite
from datetime import datetime, timedelta

from config import DB_PATH, INITIAL_ADMIN


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                counterparty TEXT,
                payment_method TEXT,
                comment TEXT,
                user_id INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                data TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_admin INTEGER DEFAULT 0,
                added_by INTEGER,
                added_at TEXT
            )
        """)
        await db.commit()

        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (INITIAL_ADMIN,)) as cur:
            if not await cur.fetchone():
                await db.execute(
                    "INSERT INTO users (user_id, is_admin, added_at) VALUES (?, 1, ?)",
                    (INITIAL_ADMIN, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                await db.commit()


# --- Пользователи ---

async def is_authorized(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
            return bool(await cur.fetchone())


async def is_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


async def add_user(user_id, username, added_by):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, added_by, added_at) VALUES (?, ?, ?, ?)",
            (user_id, username, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()


async def remove_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ? AND is_admin = 0", (user_id,))
        await db.commit()
        async with db.execute("SELECT changes()") as cur:
            return (await cur.fetchone())[0] > 0


async def make_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        async with db.execute("SELECT changes()") as cur:
            return (await cur.fetchone())[0] > 0


async def list_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY is_admin DESC, added_at") as cur:
            return await cur.fetchall()


# --- Записи ---

async def save_record(record):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO records (type, amount, counterparty, payment_method, comment, user_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record["type"], record["amount"], record.get("counterparty"),
            record.get("payment_method"), record.get("comment"),
            record["user_id"], record["created_at"]
        ))
        await db.commit()


# --- Состояния ---

async def get_state(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row:
            return row["state"], json.loads(row["data"])
    return None, {}


async def set_state(user_id, state, data=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_states (user_id, state, data) VALUES (?, ?, ?)",
            (user_id, state, json.dumps(data or {}))
        )
        await db.commit()


async def clear_state(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        await db.commit()


async def clear_records(user_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id:
            await db.execute("DELETE FROM records WHERE user_id = ?", (user_id,))
        else:
            await db.execute("DELETE FROM records")
        await db.commit()
        async with db.execute("SELECT changes()") as cur:
            return (await cur.fetchone())[0]


# --- Запросы с данными пользователей ---

async def get_all_today_records():
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT r.*, u.username, u.is_admin 
               FROM records r 
               LEFT JOIN users u ON r.user_id = u.user_id 
               WHERE r.created_at LIKE ? 
               ORDER BY r.created_at DESC""",
            (f"{today}%",)
        ) as cur:
            return await cur.fetchall()


async def get_last_3days_records():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        dates = []
        for i in range(3):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            dates.append(f"{d}%")
        conditions = " OR ".join(["r.created_at LIKE ?" for _ in dates])
        async with db.execute(
            f"""SELECT r.*, u.username FROM records r 
                LEFT JOIN users u ON r.user_id = u.user_id 
                WHERE {conditions} ORDER BY r.created_at DESC""",
            dates
        ) as cur:
            return await cur.fetchall()


async def get_today_totals():
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT type, SUM(amount) as total FROM records "
            "WHERE created_at >= ? AND created_at < ? "
            "GROUP BY type",
            (today_start.strftime("%Y-%m-%d %H:%M:%S"), today_end.strftime("%Y-%m-%d %H:%M:%S"))
        ) as cur:
            rows = await cur.fetchall()
            
        income = expense = 0
        for r in rows:
            if r["type"] == "income":
                income = r["total"] or 0
            else:
                expense = r["total"] or 0
        return income, expense



async def get_all_records():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT r.*, u.username, u.is_admin 
               FROM records r 
               LEFT JOIN users u ON r.user_id = u.user_id 
               ORDER BY r.created_at DESC"""
        ) as cur:
            return await cur.fetchall()


async def update_username(user_id, username):
    if not username:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET username = ? WHERE user_id = ?",
            (username, user_id)
        )
        await db.commit()
