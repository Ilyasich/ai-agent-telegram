# AI Meeting Assistant Telegram Bot

A production-ready Telegram bot that logs group chat messages, generates AI-powered summaries, and delivers them as PDF reports with Cyrillic support.

## Features

- **Message Logging**: Automatically logs all text messages to SQLite database
- **AI Summaries**: Uses OpenAI GPT-4o to extract Goals, Ideas, Action Items, and Decisions
- **PDF Reports**: Generates professional PDFs with timestamped headers
- **Smart Chunking**: Handles large chat histories by splitting into 15k character chunks
- **Timeframes**: Supports `1h`, `1d`, `1w`, `1m`, `all`

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get API Keys

#### Telegram Bot Token
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the API token provided

#### OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then edit `.env` and add your keys:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Run the Bot

```bash
python bot.py
```

## Usage

1. Add the bot to your Telegram group
2. The bot will automatically log all messages
3. Use `/summary <timeframe>` to generate a summary:
   - `/summary 1h` - Last hour
   - `/summary 1d` - Last day
   - `/summary 1w` - Last week
   - `/summary 1m` - Last month
   - `/summary all` - All messages

## Project Structure

- `bot.py` - Main entry point with aiogram routers
- `config.py` - Environment variable loading
- `db.py` - SQLite database operations
- `ai_service.py` - OpenAI integration with chunking
- `pdf_service.py` - PDF generation (currently has Cyrillic rendering issues - see Known Issues)
- `requirements.txt` - Python dependencies

## Troubleshooting

### "OpenAI API key not set" error
Make sure you've created the `.env` file and added your `OPENAI_API_KEY`.

### "Telegram bot token not set" error
Make sure you've created the `.env` file and added your `TELEGRAM_BOT_TOKEN`.

### Bot doesn't respond in group
Make sure you've:
1. Added the bot to the group
2. Given the bot permission to read messages (disable Privacy Mode in BotFather)
# ai-agent-telegram
