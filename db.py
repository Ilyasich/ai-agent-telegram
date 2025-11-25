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

async def search_messages(query=None, username=None, limit=50, exclude_user_id=None):
    """
    Search messages by keywords and/or username.
    
    Args:
        query: Text to search for. If "" or "LATEST", returns most recent messages.
        username: Filter by specific username
        limit: Maximum number of results (default 50)
        exclude_user_id: ID of user to exclude (to avoid self-referencing)
        
    Returns:
        List of tuples: (username, text, created_at)
    """
    async with aiosqlite.connect(config.DB_NAME) as db:
        conditions = []
        params = []
        
        # 1. Exclude User ID (Critical for "Show me news" queries)
        if exclude_user_id:
            conditions.append("user_id != ?")
            params.append(exclude_user_id)
            
        # 2. Handle "LATEST" or Empty Query
        is_latest_search = not query or query.strip() == "" or query == "LATEST" or query == "LATEST_5"
        
        if is_latest_search:
            # For latest news, we just want the most recent items
            # We still respect exclude_user_id
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            
            sql = f"""
                SELECT username, text, created_at FROM messages
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
            """
            params.append(limit) # Use the limit passed in
            
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
        
        # Build WHERE clause
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
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
