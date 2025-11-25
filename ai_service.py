import os
import logging
from openai import OpenAI, AsyncOpenAI
import config

# Initialize Groq client using OpenAI-compatible API
# Groq provides fast, free inference with generous rate limits
client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=config.GROQ_API_KEY
)

# Model selection - Groq's fast models
# Options: "llama3-8b-8192" (faster) or "mixtral-8x7b-32768" (more capable)
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
Ты эксперт бизнес-аналитик. Проанализируй следующий лог чата с командной встречи. Игнорируй светские разговоры и спам.
Структурируй вывод в формате Markdown со следующими заголовками:
🎯 Основные Цели
💡 Ключевые Идеи
✅ Задачи (Кто - Что)
🤝 Принятые Решения

Отвечай ТОЛЬКО на русском языке.
"""

MAX_CHARS = 15000

def chunk_text(text, max_chars=MAX_CHARS):
    """Splits text into chunks of max_chars, respecting line breaks."""
    chunks = []
    current_chunk = ""
    
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 > max_chars:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
            
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

async def summarize_chunk(text):
    """Summarize a single chunk of text using Groq."""
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Chat Log:\n\n{text}"}
            ],
            temperature=0.5,
            max_tokens=2000,  # Limit response length
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error in summarize_chunk: {e}")
        return f"⚠️ Ошибка AI сервиса: Не удалось создать сводку. Попробуйте позже."

async def summarize_chat(chat_text):
    """Generate a summary of chat history, with chunking support."""
    if not chat_text:
        return "Нет сообщений для создания сводки."

    try:
        if len(chat_text) <= MAX_CHARS:
            return await summarize_chunk(chat_text)
        
        # Chunking logic for long conversations
        chunks = chunk_text(chat_text)
        chunk_summaries = []
        
        for chunk in chunks:
            summary = await summarize_chunk(chunk)
            # Check if summary is an error message
            if summary.startswith("⚠️"):
                return summary  # Return error immediately
            chunk_summaries.append(summary)
            
        # Summarize the summaries if there are multiple chunks
        combined_summary_text = "\n\n".join(chunk_summaries)
        
        final_response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are consolidating multiple meeting summaries into one cohesive report. Keep the same structure: Goals, Ideas, Action Items, Decisions."},
                {"role": "user", "content": f"Summaries to consolidate:\n\n{combined_summary_text}"}
            ],
            temperature=0.5,
            max_tokens=2000,
        )
        return final_response.choices[0].message.content
        
    except Exception as e:
        logging.error(f"Error in summarize_chat: {e}")
        return "⚠️ AI сервисы сейчас заняты. Попробуйте через минуту."

# Intent Detection System Prompt
INTENT_SYSTEM_PROMPT = """
Ты классификатор намерений для Telegram бота, который создает сводки встреч.

Проанализируй сообщение пользователя и определи его намерение:

1. **Запрос сводки**: Пользователь хочет получить сводку истории чата
   - Ищи ключевые слова: сводка, резюме, обзор, отчет, что произошло, что обсуждали, итоги
   - Извлеки временной период если упомянут: вчера, сегодня, последний час, последняя неделя, последний месяц и т.д.
   - Сопоставь периоды: "вчера" -> "1d", "последний час" -> "1h", "последняя неделя" -> "1w", "последний месяц" -> "1m"
   - По умолчанию используй "1h" если период не указан

2. **Общение/Вопрос**: Пользователь хочет пообщаться или задать вопрос
   - Приветствия, вопросы о возможностях бота, общение
   - Предоставь полезный, дружелюбный ответ НА РУССКОМ ЯЗЫКЕ

Ты ДОЛЖЕН ответить ТОЛЬКО валидным JSON объектом (без markdown, без дополнительного текста):

Для запросов сводки:
{"action": "summary", "timeframe": "1d"}

Для общения/вопросов:
{"action": "chat", "reply": "Твой полезный ответ здесь НА РУССКОМ"}

Примеры:
Пользователь: "Дай сводку за вчера"
Ответ: {"action": "summary", "timeframe": "1d"}

Пользователь: "Что ты умеешь?"
Ответ: {"action": "chat", "reply": "Я могу создавать сводки вашей истории чата! Просто попросите меня о сводке или используйте команду /summary с периодом времени: 1h, 1d, 1w, 1m, или all."}

Пользователь: "Покажи что было на прошлой неделе"
Ответ: {"action": "summary", "timeframe": "1w"}

ВСЕ ответы в поле reply ДОЛЖНЫ быть на РУССКОМ языке.
"""

async def detect_intent(user_text: str) -> dict:
    """
    Detect user intent using Groq.
    
    Args:
        user_text: The user's message text
        
    Returns:
        dict: {"action": "summary", "timeframe": "1d"} or
              {"action": "chat", "reply": "response text"}
    """
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3,  # Lower temperature for more consistent JSON output
            max_tokens=500,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON
        import json
        try:
            intent_data = json.loads(result_text)
            
            # Validate the response structure
            if "action" not in intent_data:
                raise ValueError("Missing 'action' field in response")
                
            if intent_data["action"] == "summary":
                # Ensure timeframe exists and is valid
                if "timeframe" not in intent_data:
                    intent_data["timeframe"] = "1h"  # Default
                elif intent_data["timeframe"] not in ["1h", "1d", "1w", "1m", "all"]:
                    intent_data["timeframe"] = "1h"  # Fallback to default
                    
            elif intent_data["action"] == "chat":
                # Ensure reply exists
                if "reply" not in intent_data or not intent_data["reply"]:
                    intent_data["reply"] = "Я здесь, чтобы помочь! Вы можете попросить меня о сводке истории чата."
            else:
                # Unknown action, default to chat
                intent_data = {
                    "action": "chat",
                    "reply": "Не уверен, что вы просите. Вы можете запросить сводку или задать мне вопросы!"
                }
                
            return intent_data
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from LLM: {result_text}")
            # Fallback to chat with generic response
            return {
                "action": "chat",
                "reply": "У меня проблемы с пониманием. Вы можете использовать /summary для получения сводки чата!"
            }
            
    except Exception as e:
        logging.error(f"Error in detect_intent: {str(e)}")
        # Fallback response
        return {
            "action": "chat",
            "reply": "Извините, у меня проблемы с подключением к AI сервисам. Попробуйте снова или используйте команду /summary."
        }
