import aiosqlite
from datetime import datetime, timedelta
import config

async def init_db():
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                text TEXT,
                created_at DATETIME
            )
        """)
        await db.commit()

async def log_message(user_id, username, text):
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute("""
            INSERT INTO messages (user_id, username, text, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            username,
            text,
            datetime.now()
        ))
        await db.commit()

async def get_messages(timeframe):
    async with aiosqlite.connect(config.DB_NAME) as db:
        now = datetime.now()
        delta = timedelta(0)
        
        if timeframe == "1h":
            delta = timedelta(hours=1)
        elif timeframe == "1d":
            delta = timedelta(days=1)
        elif timeframe == "1w":
            delta = timedelta(weeks=1)
        elif timeframe == "1m":
            delta = timedelta(days=30)
        elif timeframe == "all":
            # For 'all', we just use a very old date or skip the where clause
            # But to keep SQL simple, let's just use a large delta
            delta = timedelta(days=365*10)
            
        cutoff = now - delta
        
        cursor = await db.execute("""
            SELECT username, text, created_at FROM messages
            WHERE created_at >= ?
            ORDER BY created_at ASC
        """, (cutoff,))
            
        rows = await cursor.fetchall()
        return rows
