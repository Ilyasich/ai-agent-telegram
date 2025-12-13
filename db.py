import aiosqlite
from datetime import datetime, timedelta
import config

async def init_db():
    async with aiosqlite.connect(config.DB_NAME) as db:
        # Check if table exists and has chat_id
        # For simplicity in this upgrade, we'll create if not exists, 
        # but since we want to enforce the new schema, we might need to handle migration.
        # Given the previous "delete all data" instruction, we can be a bit aggressive 
        # but let's try to be safe: create table with new schema if it doesn't exist.
        # If it exists without chat_id, it might fail on insert. 
        # Ideally we'd check columns, but for this task let's assume we can recreate or the user handles it.
        # Actually, let's just create it correctly.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                text TEXT,
                reply_to_user_id INTEGER,
                reply_to_username TEXT,
                created_at DATETIME
            )
        """)
        
        # Migrations for existing tables
        try:
            await db.execute("SELECT chat_id FROM messages LIMIT 1")
        except Exception:
            try:
                await db.execute("ALTER TABLE messages ADD COLUMN chat_id INTEGER")
            except Exception as e:
                print(f"Migration warning (chat_id): {e}")

        try:
            await db.execute("SELECT reply_to_user_id FROM messages LIMIT 1")
        except Exception:
            try:
                await db.execute("ALTER TABLE messages ADD COLUMN reply_to_user_id INTEGER")
                await db.execute("ALTER TABLE messages ADD COLUMN reply_to_username TEXT")
            except Exception as e:
                print(f"Migration warning (reply_columns): {e}")
                
        await db.commit()

async def log_message(chat_id, user_id, username, text, reply_to_user_id=None, reply_to_username=None):
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute("""
            INSERT INTO messages (chat_id, user_id, username, text, reply_to_user_id, reply_to_username, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            user_id,
            username,
            text,
            reply_to_user_id,
            reply_to_username,
            datetime.now()
        ))
        await db.commit()

async def get_messages(chat_id, timeframe):
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
            delta = timedelta(days=365*10)
            
        cutoff = now - delta
        
        cursor = await db.execute("""
            SELECT username, text, created_at FROM messages
            WHERE chat_id = ? AND created_at >= ?
            ORDER BY created_at ASC
        """, (chat_id, cutoff))
            
        rows = await cursor.fetchall()
        return rows

async def search_messages(chat_id, query=None, username=None, limit=50, exclude_user_id=None):
    """
    Search messages by keywords and/or username within a specific chat.
    """
    async with aiosqlite.connect(config.DB_NAME) as db:
        conditions = ["chat_id = ?"]
        params = [chat_id]
        
        # 1. Exclude User ID
        if exclude_user_id:
            conditions.append("user_id != ?")
            params.append(exclude_user_id)
            
        # 2. Handle "LATEST" or Empty Query
        is_latest_search = not query or query.strip() == "" or query == "LATEST" or query == "LATEST_5"
        
        if is_latest_search:
            where_clause = " WHERE " + " AND ".join(conditions)
            sql = f"""
                SELECT username, text, created_at FROM messages
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
            """
            params.append(limit)
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return rows

        # 3. Normal Keyword Search
        if query and query.strip():
            conditions.append("text LIKE ?")
            params.append(f"%{query}%")
            
        if username:
            conditions.append("username LIKE ?")
            params.append(f"%{username}%")
        
        where_clause = " AND ".join(conditions)
        
        sql = f"""
            SELECT username, text, created_at FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return rows

async def get_active_users(chat_id, limit=50):
    """
    Get a list of unique usernames who have written in the specific chat.
    """
    async with aiosqlite.connect(config.DB_NAME) as db:
        cursor = await db.execute("""
            SELECT DISTINCT username FROM messages 
            WHERE chat_id = ? AND username IS NOT NULL AND username != 'Unknown'
            ORDER BY created_at DESC
            LIMIT ?
        """, (chat_id, limit))
        
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_top_talkers(chat_id, timeframe="1d", limit=5):
    """
    Get top active users in the given timeframe.
    """
    async with aiosqlite.connect(config.DB_NAME) as db:
        now = datetime.now()
        delta = timedelta(days=1)
        if timeframe == "1h": delta = timedelta(hours=1)
        elif timeframe == "1w": delta = timedelta(weeks=1)
        elif timeframe == "1m": delta = timedelta(days=30)
        elif timeframe == "all": delta = timedelta(days=3650)
            
        cutoff = now - delta
        
        # Top speakers
        cursor = await db.execute("""
            SELECT username, COUNT(*) as count 
            FROM messages 
            WHERE chat_id = ? AND created_at >= ? AND username != 'Unknown' AND username IS NOT NULL
            GROUP BY username 
            ORDER BY count DESC 
            LIMIT ?
        """, (chat_id, cutoff, limit))
        
        rows = await cursor.fetchall()
        return [{"username": r[0], "count": r[1]} for r in rows]
