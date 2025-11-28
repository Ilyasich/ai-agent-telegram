import asyncio
import logging
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

# Global bot instance for mention detection
bot_instance = None

def split_message(text: str, max_length: int = 4096) -> list[str]:
    """
    Split a long message into chunks that fit Telegram's message limit.
    
    Args:
        text: The text to split
        max_length: Maximum length per message (default 4096 for Telegram)
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by lines to avoid breaking in the middle of sentences
    lines = text.split('\n')
    
    for line in lines:
        # If a single line is longer than max_length, split it by words
        if len(line) > max_length:
            words = line.split(' ')
            for word in words:
                if len(current_chunk) + len(word) + 1 > max_length:
                    chunks.append(current_chunk)
                    current_chunk = word + " "
                else:
                    current_chunk += word + " "
        # If adding this line would exceed the limit, start a new chunk
        elif len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    # Add the last chunk if it's not empty
    if current_chunk.strip():
        chunks.append(current_chunk)
    
    return chunks

async def process_summary_request(message: types.Message, timeframe: str, bot: Bot):
    """
    Generate and send a summary as text message(s) for the specified timeframe.
    
    Args:
        message: The Telegram message object
        timeframe: Time period for summary (1h, 1d, 1w, 1m, all)
        bot: Bot instance
    """
    status_msg = await message.reply(f"Генерирую сводку за последние {timeframe}...")
    
    try:
        # Fetch messages
        messages = await db.get_messages(timeframe)
        
        if not messages:
            await status_msg.edit_text("Сообщений за этот период не найдено.")
            return

        # Prepare text for AI
        chat_text = "\n".join([f"{user}: {text}" for user, text, _ in messages])
        
        # Generate Summary
        await status_msg.edit_text("Анализирую историю чата (это может занять некоторое время)...")
        summary = await ai_service.summarize_chat(chat_text)
        
        # Delete status message
        await status_msg.delete()
        
        # Split summary into chunks if needed (Telegram limit: 4096 chars)
        chunks = split_message(summary)
        
        # Send summary chunks
        for i, chunk in enumerate(chunks):
            if i == 0:
                # First message includes header
                await message.reply(f"📊 **Сводка за последние {timeframe}**\n\n{chunk}")
            else:
                # Subsequent messages are continuations
                await message.reply(f"_(продолжение {i+1}/{len(chunks)})_\n\n{chunk}")
        
    except Exception as e:
        logging.error(f"Error in process_summary_request: {e}")
        await status_msg.edit_text(f"Произошла ошибка: {str(e)}")

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Handle /start command.
    Sends a greeting message describing the bot's purpose.
    """
    await message.reply("Привет я бот аналитик в чате. Помогаю с информацией в чате.")

@router.message(Command("summary"))
async def cmd_summary(message: types.Message, bot: Bot):
    """
    Handle /summary command.
    Usage: /summary [timeframe]
    """
    args = message.text.split()
    timeframe = "1h" # Default
    if len(args) > 1:
        timeframe = args[1]
    
    if timeframe not in ["1h", "1d", "1w", "1m", "all"]:
        await message.reply("Неверный период времени. Используйте: 1h, 1d, 1w, 1m, all")
        return

    await process_summary_request(message, timeframe, bot)

@router.channel_post()
async def log_channel_posts(message: types.Message):
    """
    Log all posts from channels where the bot is admin.
    Captures text or caption. Handles media groups (albums) by ignoring empty captions.
    Channels don't have individual users, so we use chat.title as username.
    """
    try:
        # 1. Universal Text Extraction
        content = message.text or message.caption or ""
        
        # 2. Debug Print
        print(f"--- NEW POST IN {message.chat.title}: {content[:20]}... ---")
        
        # 3. Handle Albums & Empty Content
        if not content.strip():
            return

        # 4. Save to DB
        # Use chat.id and chat.title because from_user might be None in channels
        await db.log_message(
            user_id=message.chat.id,
            username=message.chat.title or "Channel",
            text=content
        )
    except Exception as e:
        logging.error(f"Error in log_channel_posts: {e}")

def should_respond_to_message(message: types.Message, bot_username: str) -> bool:
    """
    Determine if the bot should respond to this message.
    
    Bot responds if:
    - It's a private chat (DM)
    - Message is a reply to the bot
    - Message mentions the bot (@botusername)
    
    Args:
        message: The Telegram message
        bot_username: The bot's username
        
    Returns:
        bool: True if bot should respond
    """
    # Private chat (DM)
    if message.chat.type == "private":
        return True
    
    # Message is a reply to the bot
    if message.reply_to_message and message.reply_to_message.from_user.is_bot:
        return True
    
    # Message mentions the bot
    if bot_username and f"@{bot_username}" in message.text:
        return True
    
    return False

@router.message(F.text | F.caption)
async def log_all_messages(message: types.Message, bot: Bot):
    """
    Log all text messages and handle interactions.
    Supports Replies and Forwards as Context.
    """
    # Extract content (text or caption)
    content = message.text or message.caption or ""
    
    # Ignore commands and empty messages
    if not content or content.startswith('/'):
        return

    # 1. Log User Message to DB
    # Handle cases where from_user might be None (though rare in message handler)
    user_id = message.from_user.id if message.from_user else message.chat.id
    username = message.from_user.username if message.from_user else "Unknown"
    
    await db.log_message(
        user_id=user_id,
        username=username,
        text=content
    )
    
    # 2. Check if Bot Should Respond
    bot_info = await bot.get_me()
    if not should_respond_to_message(message, bot_info.username):
        return
    
    # 3. Context Extraction (Reply or Forward)
    context_text = None
    
    # Check for Reply
    if message.reply_to_message:
        # Extract text/caption from the replied message
        replied_msg = message.reply_to_message
        context_text = replied_msg.text or replied_msg.caption or ""
        
    # Check for Forward (if it's a forward, the message itself has forward_date)
    # But usually users forward a message AND add a comment, which makes it a reply? 
    # Or they just forward it. If they just forward, message.text is the content.
    # If they reply TO a forward, handled above.
    
    # 4. Detect Intent
    status_msg = await message.reply("🤔 Анализирую...")
    
    try:
        intent = await ai_service.detect_intent(content)
        
        if intent["action"] == "summary":
            timeframe = intent.get("timeframe", "1h")
            await status_msg.delete() # Remove "Analyzing"
            await process_summary_request(message, timeframe, bot)
            
        elif intent["action"] == "search":
            keywords = intent.get("keywords", "")
            username_filter = intent.get("username")
            
            # If we have direct context (Reply), we might skip DB search or combine it
            # But the requirement says: "If YES: Extract text... pass as Context"
            
            found_messages = []
            
            if not context_text:
                # Perform DB Search
                # If keywords is empty, db.search_messages handles it as "LATEST"
                limit = 5
                found_messages = await db.search_messages(
                    query=keywords,
                    username=username_filter,
                    limit=limit,
                    exclude_user_id=user_id # Exclude the current user's messages
                )
            
            # Generate Answer
            answer = await ai_service.answer_search_query(
                user_question=content,
                found_messages=found_messages,
                context_text=context_text
            )
            
            await status_msg.delete()
            await message.reply(answer)
            
    except Exception as e:
        logging.error(f"Error in log_all_messages: {e}")
        await status_msg.edit_text("⚠️ Произошла ошибка. Попробуйте позже.")

async def main():
    # Initialize Bot and Dispatcher
    global bot_instance
    bot_instance = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register Router
    dp.include_router(router)
    
    # Initialize DB
    await db.init_db()
    logging.info("Database initialized.")
    
    # Start Polling
    await dp.start_polling(bot_instance)

if __name__ == "__main__":
    asyncio.run(main())
