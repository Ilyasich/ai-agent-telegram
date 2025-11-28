import asyncio
import aiosqlite
import config

async def clear_db():
    print(f"Connecting to database: {config.DB_NAME}")
    async with aiosqlite.connect(config.DB_NAME) as db:
        print("Deleting all messages...")
        await db.execute("DELETE FROM messages")
        await db.commit()
        print("Vacuuming database...")
        await db.execute("VACUUM")
        await db.commit()
        
        # Verify
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        count = await cursor.fetchone()
        print(f"Messages remaining: {count[0]}")

if __name__ == "__main__":
    asyncio.run(clear_db())
