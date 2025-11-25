import os
import asyncio
import unittest.mock

# Set mock env vars BEFORE importing modules that use them
os.environ["OPENAI_API_KEY"] = "mock_key"
os.environ["TELEGRAM_BOT_TOKEN"] = "mock_token"

import db
import config
from pdf_service import generate_pdf, ensure_font
from ai_service import chunk_text
from datetime import datetime

# Ensure config is patched if it was already imported (though it shouldn't be with this order)
config.OPENAI_API_KEY = "mock_key"
config.TELEGRAM_BOT_TOKEN = "mock_token"
config.DB_NAME = "test_chat_history.db"

# Mock message object for testing
class MockUser:
    id = 12345
    username = "test_user"

class MockChat:
    id = -987654321

class MockMessage:
    message_id = 1
    from_user = MockUser()
    chat = MockChat()
    text = "Hello, this is a test message for the summary bot."

async def test_db():
    print("Testing Database...")
    # Use a test DB file
    if os.path.exists(config.DB_NAME):
        os.remove(config.DB_NAME)
        
    await db.init_db()
    
    # Log a message
    await db.log_message(MockUser.id, MockUser.username, MockMessage.text)
    print("Logged message.")
    
    # Retrieve messages
    messages = await db.get_messages("1h")
    print(f"Retrieved {len(messages)} messages.")
    assert len(messages) >= 1
    print("Database test passed!")
    
    # Cleanup
    if os.path.exists(config.DB_NAME):
        os.remove(config.DB_NAME)

def test_chunking():
    print("Testing Chunking...")
    text = "a" * 20000
    chunks = chunk_text(text, max_chars=15000)
    print(f"Text length: {len(text)}, Chunks: {len(chunks)}")
    assert len(chunks) == 2
    print("Chunking test passed!")

def test_pdf():
    print("Testing PDF Generation...")
    # Ensure font
    ensure_font()
    
    summary_text = """
# Meeting Summary

## Main Goals
* Verify the bot components.

## Key Ideas
* Use a script to test DB and PDF.
* Ensure Cyrillic support: Привет, мир!

## Action Items
* [ ] Run this script.

## Decisions Made
* Approved the plan.
    """
    filename = "test_summary_fpdf2.pdf"
    generate_pdf(summary_text, filename)
    
    if os.path.exists(filename):
        print(f"PDF generated successfully: {filename}")
        # Clean up
        os.remove(filename)
    else:
        print("PDF generation failed.")

async def main():
    await test_db()
    test_chunking()
    test_pdf()

if __name__ == "__main__":
    asyncio.run(main())
