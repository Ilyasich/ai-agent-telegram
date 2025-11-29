import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
import ai_service

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Router
router = Router()
bot_instance = None

def split_message(text: str, max_length: int = 4096) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks = []
    current_chunk = ""
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk.strip():
        chunks.append(current_chunk)
    return chunks

async def process_summary_request(message: types.Message, timeframe: str, bot: Bot):
    status_msg = await message.reply(f"Генерирую сводку за последние {timeframe}...")
    try:
        # Pass chat_id
        messages = await db.get_messages(message.chat.id, timeframe)
        if not messages:
            await status_msg.edit_text("Сообщений за этот период не найдено.")
            return

        chat_text = "\n".join([f"{user}: {text}" for user, text, _ in messages])
        await status_msg.edit_text("Анализирую историю чата...")
        summary = await ai_service.summarize_chat(chat_text)
        await status_msg.delete()
        
        chunks = split_message(summary)
        for i, chunk in enumerate(chunks):
            header = f"📊 **Сводка за последние {timeframe}**\n\n" if i == 0 else ""
            await message.reply(f"{header}{chunk}")
    except Exception as e:
        logging.error(f"Error in summary: {e}")
        await status_msg.edit_text("Ошибка при генерации сводки.")

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply("Я — Бетон, ваш доапокалиптический робот-помощник. 🤖")

@router.message(Command("summary"))
async def cmd_summary(message: types.Message, bot: Bot):
    args = message.text.split()
    timeframe = args[1] if len(args) > 1 else "1h"
    await process_summary_request(message, timeframe, bot)

@router.channel_post()
async def log_channel_posts(message: types.Message):
    """Log all posts from channels."""
    try:
        content = message.text or message.caption or ""
        if not content.strip(): return
        
        print(f"--- NEW POST IN {message.chat.title}: {content[:20]}... ---")
        # Pass chat_id
        await db.log_message(
            chat_id=message.chat.id,
            user_id=message.chat.id,
            username=message.chat.title or "Channel",
            text=content
        )
    except Exception as e:
        logging.error(f"Error logging channel post: {e}")

@router.message(F.text | F.caption)
async def log_all_messages(message: types.Message, bot: Bot):
    """Main Message Handler"""
    content = message.text or message.caption or ""
    if not content or content.startswith('/'): return

    # 1. Log to DB with chat_id
    user_id = message.from_user.id if message.from_user else message.chat.id
    username = message.from_user.username if message.from_user else "Unknown"
    await db.log_message(message.chat.id, user_id, username, content)

    # 2. Check Spam/Autonomy
    bot_info = await bot.get_me()
    is_direct = (
        (message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id) or
        (f"@{bot_info.username}" in content) or
        (message.chat.type == "private")
    )
    
    # 20% chance to process if not direct
    if not is_direct and random.random() > 0.2:
        return

    # 3. Detect Intent
    intent = await ai_service.detect_intent(content)
    
    # --- BRANCHING LOGIC ---
    
    if intent["action"] == "summary":
        await process_summary_request(message, intent.get("timeframe", "1h"), bot)
        return

    elif intent["action"] == "search":
        status_msg = await message.reply("🤔 Ищу информацию...")
        keywords = intent.get("keywords", "")
        username_filter = intent.get("username")
        
        # Context from reply
        context_text = None
        if message.reply_to_message:
            msg = message.reply_to_message
            context_text = msg.text or msg.caption or ""

        found_messages = []
        if not context_text:
            # Pass chat_id
            found_messages = await db.search_messages(
                chat_id=message.chat.id,
                query=keywords,
                username=username_filter,
                limit=5,
                exclude_user_id=user_id
            )
        
        answer = await ai_service.answer_search_query(content, found_messages, context_text)
        await status_msg.delete()
        await message.reply(answer)
        return

    elif intent["action"] == "chat":
        # Check if we need stats (Who is in chat?)
        total_count = None
        active_users = None
        
        msg_lower = content.lower()
        if any(w in msg_lower for w in ["кто", "участник", "люди", "народ", "сколько", "who", "users", "members"]):
            try:
                total_count = await bot.get_chat_member_count(message.chat.id)
                # Pass chat_id
                active_users = await db.get_active_users(message.chat.id, limit=50)
            except Exception as e:
                logging.error(f"Stats error: {e}")

        # Context
        context_text = None
        if message.reply_to_message:
            msg = message.reply_to_message
            context_text = msg.text or msg.caption or ""

        ai_decision = await ai_service.analyze_and_reply(
            content, 
            context=context_text, 
            username=username,
            total_count=total_count,
            active_users=active_users
        )
        
        if ai_decision.get("should_reply"):
            reply_text = ai_decision.get("reply_text")
            if reply_text:
                print(f"--- AI REPLY: {reply_text} ---")
                await message.reply(reply_text)
        else:
            print(f"--- AI SILENCE: {ai_decision.get('reason')} ---")

async def main():
    global bot_instance
    bot_instance = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    await db.init_db()
    logging.info("Database initialized.")
    
    await dp.start_polling(bot_instance)

if __name__ == "__main__":
    asyncio.run(main())
