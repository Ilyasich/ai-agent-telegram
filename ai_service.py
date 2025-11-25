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
Ты - Строгий Аналитик Данных.

ТВОЯ ЗАДАЧА:
Классифицировать сообщение пользователя в ОДНО из двух действий: "summary" или "search".

ПРАВИЛА:
1. НИКАКИХ разговоров. НИКАКИХ "chat" интентов.
2. Если пользователь здоровается ("Привет", "Hello") -> action="search", keywords="" (показать последние новости).
3. Если пользователь благодарит ("Спасибо") -> action="search", keywords="" (показать последние новости).
4. Если пользователь спрашивает "Что нового?", "Последние новости" -> action="search", keywords="".
5. Если пользователь спрашивает про конкретную тему -> action="search", keywords="тема".
6. Если пользователь просит сводку за время -> action="summary".

ФОРМАТ ОТВЕТА (JSON):

1. **summary**:
   - {"action": "summary", "timeframe": "1d"} (1h, 1d, 1w, 1m)

2. **search**:
   - {"action": "search", "keywords": "строка поиска", "username": "имя или null"}
   - keywords="" (пустая строка) означает "ПОСЛЕДНИЕ НОВОСТИ".

Примеры:
User: "Привет"
Response: {"action": "search", "keywords": "", "username": null}

User: "Что там про налоги?"
Response: {"action": "search", "keywords": "налоги", "username": null}

User: "Дай сводку за вчера"
Response: {"action": "summary", "timeframe": "1d"}
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
                    
            elif intent_data["action"] == "search":
                # Ensure keywords exists
                if "keywords" not in intent_data:
                    intent_data["keywords"] = "" # Empty means "latest"
                
                # Ensure username is present (can be null)
                if "username" not in intent_data:
                    intent_data["username"] = None
            
            # Force any unknown action to search latest
            else:
                intent_data = {"action": "search", "keywords": "", "username": None}
                
            return intent_data
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from LLM: {result_text}")
            # Fallback to search latest
            return {"action": "search", "keywords": "", "username": None}
            
    except Exception as e:
        logging.error(f"Error in detect_intent: {str(e)}")
        # Fallback response
        return {"action": "search", "keywords": "", "username": None}

async def answer_search_query(user_question: str, found_messages: list = None, context_text: str = None) -> str:
    """
    Generate a contextual answer based on search results OR direct context.
    
    Args:
        user_question: The original user's question
        found_messages: List of tuples (username, text, created_at) from database
        context_text: Direct text from a forwarded/replied message
        
    Returns:
        str: AI-generated answer
    """
    
    # Prepare the context for the AI
    data_context = ""
    
    if context_text:
        data_context = f"КОНТЕКСТ (из пересланного сообщения):\n{context_text}\n"
    elif found_messages:
        # Format messages for AI
        msgs = []
        for username, text, created_at in found_messages:
            msgs.append(f"[{created_at}] {username}: {text}")
        data_context = "НАЙДЕННЫЕ СООБЩЕНИЯ ИЗ БАЗЫ:\n" + "\n".join(msgs)
    else:
        return "Данные не найдены. В базе нет новостей по вашему запросу."
    
    search_prompt = f"""
ВОПРОС ПОЛЬЗОВАТЕЛЯ: "{user_question}"

{data_context}

ИНСТРУКЦИЯ:
Ответь на вопрос, используя ТОЛЬКО предоставленные данные.
"""
    
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": """
Ты - Строгий Аналитик Новостей.

ПРАВИЛА:
1. Будь краток. Используй маркированные списки.
2. Тон: Фактологический, профессиональный. Без эмоций.
3. Формат для новостей: "🕒 [Время] - [Суть события]".
4. Если анализируешь пересланное сообщение (Контекст), просто дай его краткую суть/ответ на вопрос.
5. НИКОГДА не говори "я не могу", "я бот", "нет доступа".
6. Если данных мало, просто скажи то, что есть.

Отвечай НА РУССКОМ ЯЗЫКЕ.
"""},
                {"role": "user", "content": search_prompt}
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        
        answer = response.choices[0].message.content
        return answer
        
    except Exception as e:
        logging.error(f"Error in answer_search_query: {e}")
        return "⚠️ Ошибка при генерации ответа."
