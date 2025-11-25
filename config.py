import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_NAME = "chat_history.db"

# Use system DejaVu font which we know exists and supports Cyrillic
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
