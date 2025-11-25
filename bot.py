import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
import ai_service
import pdf_service

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Router
router = Router()

@router.message(Command("summary"))
async def cmd_summary(message: types.Message):
    """
    Handle /summary command.
    Usage: /summary [timeframe]
    """
    args = message.text.split()
    timeframe = "1h" # Default
    if len(args) > 1:
        timeframe = args[1]
    
    if timeframe not in ["1h", "1d", "1w", "1m", "all"]:
        await message.reply("Invalid timeframe. Use: 1h, 1d, 1w, 1m, all")
        return

    status_msg = await message.reply(f"Generating summary for the last {timeframe}...")
    
    try:
        # Fetch messages
        messages = await db.get_messages(timeframe)
        
        if not messages:
            await status_msg.edit_text("No messages found for this period.")
            return

        # Prepare text for AI
        chat_text = "\n".join([f"{user}: {text}" for user, text, _ in messages])
        
        # Generate Summary
        await status_msg.edit_text("Analyzing chat history (this may take a moment)...")
        summary = await ai_service.summarize_chat(chat_text)
        
        # Generate PDF
        await status_msg.edit_text("Creating PDF...")
        pdf_filename = f"summary_{message.chat.id}_{timeframe}.pdf"
        pdf_service.generate_pdf(summary, pdf_filename)
        
        # Send PDF
        await status_msg.edit_text("Sending document...")
        pdf_file = FSInputFile(pdf_filename)
        await message.reply_document(pdf_file, caption=f"Here is the summary for the last {timeframe}.")
        
        # Cleanup
        if os.path.exists(pdf_filename):
            os.remove(pdf_filename)
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error in summary command: {e}")
        await status_msg.edit_text(f"An error occurred: {str(e)}")

@router.message(F.text)
async def log_all_messages(message: types.Message):
    """
    Log all text messages to the database.
    """
    # Ignore bot's own messages (handled by aiogram usually, but good to be explicit if needed)
    # Also ignore commands if you don't want to log them as chat content
    if message.text.startswith('/'):
        return

    await db.log_message(
        user_id=message.from_user.id,
        username=message.from_user.username or "Unknown",
        text=message.text
    )

async def main():
    # Initialize Bot and Dispatcher
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register Router
    dp.include_router(router)
    
    # Initialize DB
    await db.init_db()
    logging.info("Database initialized.")
    
    # Start Polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
