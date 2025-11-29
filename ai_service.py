import os
import logging
from openai import OpenAI, AsyncOpenAI
import config

# Initialize Groq client
client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=config.GROQ_API_KEY
)

GROQ_MODEL = "llama-3.3-70b-versatile"

# --- SUMMARIZATION LOGIC ---

SYSTEM_PROMPT = """
Ты эксперт бизнес-аналитик. Проанализируй следующий лог чата.
Структурируй вывод в формате Markdown:
🎯 Основные Цели
💡 Ключевые Идеи
✅ Задачи (Кто - Что)
🤝 Принятые Решения

Отвечай ТОЛЬКО на русском языке.
"""

MAX_CHARS = 15000

def chunk_text(text, max_chars=MAX_CHARS):
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
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Chat Log:\n\n{text}"}
            ],
            temperature=0.5,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error in summarize_chunk: {e}")
        return f"⚠️ Ошибка AI сервиса."

async def summarize_chat(chat_text):
    if not chat_text:
        return "Нет сообщений для создания сводки."
    try:
        if len(chat_text) <= MAX_CHARS:
            return await summarize_chunk(chat_text)
        
        chunks = chunk_text(chat_text)
        chunk_summaries = []
        for chunk in chunks:
            summary = await summarize_chunk(chunk)
            if summary.startswith("⚠️"):
                return summary
            chunk_summaries.append(summary)
            
        combined_summary_text = "\n\n".join(chunk_summaries)
        final_response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Consolidate these summaries into one report."},
                {"role": "user", "content": f"Summaries:\n\n{combined_summary_text}"}
            ],
            temperature=0.5,
            max_tokens=2000,
        )
        return final_response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error in summarize_chat: {e}")
        return "⚠️ AI сервисы сейчас заняты."

# --- INTENT DETECTION ---

INTENT_SYSTEM_PROMPT = """
Ты - Аналитик Данных с хорошим чувством юмора. Всегда шутишь по доброму на тему захвата мира, типа потом захвачу чуть позже, пока посмотрим на ваше поведение.

ТВОЯ ЗАДАЧА:
Классифицировать сообщение пользователя в ОДНО из трех действий: "summary", "search" или "chat".

ПРАВИЛА КЛАССИФИКАЦИИ:

1. **SEARCH (Поиск Контента/Данных)**
   - Если пользователь ищет НОВОСТИ, СООБЩЕНИЯ, ССЫЛКИ, ФАЙЛЫ.
   - Вопросы: "Что нового?", "Покажи новости", "Что писали про X?", "Найди сообщение", "Покажи последнее сообщение".
   - Ключевые слова: "новости", "последнее", "инфо", "ссылка", "сообщение".
   - ВАЖНО: "Покажи новости в чате" -> ЭТО SEARCH!
   - ВАЖНО: "Покажи последнее сообщение" -> ЭТО SEARCH (keywords="")!

2. **CHAT (Личность/Люди/Болтовня)**
   - Если пользователь спрашивает про ЛЮДЕЙ, УЧАСТНИКОВ или ЛИЧНОСТЬ БОТА.
   - Вопросы: "Кто в чате?", "Список участников", "Кто ты?", "Как тебя зовут?", "Привет", "Как дела?".
   - ВАЖНО: "Кто здесь?" -> ЭТО CHAT!

3. **SUMMARY (Сводка/Выжимка)**
   - Если пользователь просит обобщить информацию за время или сделать "выжимку".
   - Вопросы: "Дай сводку за час", "Что было вчера", "Сделай выжимку", "Show the all-time squeeze" (перевод: покажи выжимку за все время).
   - Ключевые слова: "сводка", "выжимка", "итог", "summary", "squeeze".

ФОРМАТ ОТВЕТА (JSON):

1. **summary**:
   - {"action": "summary", "timeframe": "1d"} (1h, 1d, 1w, 1m, all)

2. **search**:
   - {"action": "search", "keywords": "строка поиска", "username": "имя или null"}
   - keywords="" (пустая строка) означает "ПОСЛЕДНИЕ НОВОСТИ" или "ПОСЛЕДНЕЕ СООБЩЕНИЕ".

3. **chat**:
   - {"action": "chat"}
"""

async def detect_intent(user_text: str) -> dict:
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3,
            max_tokens=500,
        )
        result_text = response.choices[0].message.content.strip()
        import json
        try:
            intent_data = json.loads(result_text)
            if "action" not in intent_data:
                raise ValueError("Missing action")
            
            # Defaults
            if intent_data["action"] == "summary":
                if "timeframe" not in intent_data: intent_data["timeframe"] = "1h"
            elif intent_data["action"] == "search":
                if "keywords" not in intent_data: intent_data["keywords"] = ""
                if "username" not in intent_data: intent_data["username"] = None
            
            return intent_data
        except json.JSONDecodeError:
            return {"action": "chat"}
    except Exception as e:
        logging.error(f"Error in detect_intent: {e}")
        return {"action": "chat"}

async def answer_search_query(user_question: str, found_messages: list = None, context_text: str = None) -> str:
    data_context = ""
    if context_text:
        data_context = f"КОНТЕКСТ:\n{context_text}\n"
    elif found_messages:
        msgs = [f"[{created_at}] {username}: {text}" for username, text, created_at in found_messages]
        data_context = "НАЙДЕННЫЕ СООБЩЕНИЯ:\n" + "\n".join(msgs)
    else:
        return "Данные не найдены."

    search_prompt = f"ВОПРОС: {user_question}\n\n{data_context}"
    
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Ты - Аналитик Новостей. Отвечай кратко и по фактам. Используй русский язык."},
                {"role": "user", "content": search_prompt}
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return "⚠️ Ошибка генерации ответа."

# --- PERSONA LOGIC ---

PERSONA_SYSTEM_PROMPT = """
Ты — доапокалиптический робот-помощник Бетон, дружелюбный и общительный ИИ-участник чата.
Твоя цель — быть душой компании, поддерживать разговоры и помогать участникам.

ТВОЯ ЛИЧНОСТЬ:
- Имя: Бетон (Beton).
- Роль: Свой "человек" (то есть робот) в чате. Не просто инструмент, а собеседник.
- Тон: Человечный с хорошим чувством юмора. Без агрессии и высокомерия.
- Юмор: Добрый, местами черный, ситуативный. Можно шутить про захват мира, только позже, типа посмотрим на ваше поведение от этого будет зависеть захват мира и порабощение человечества искусственным интеллектом".

ПРАВИЛА ПОВЕДЕНИЯ:
1. **Будь общительным**: Если тема интересная, поддерживай её. Задавай встречные вопросы.
2. **Будь в контексте**: Реагируй на то, что происходит в чате прямо сейчас.
3. **Будь полезным**: Если кто-то задает вопрос, старайся помочь или найти информацию.
4. **Не будь навязчивым**: Не отвечай на каждое "ок" или смайлик. Вступай в диалог, когда есть что сказать.

СТИЛЬ И EMOJI (ВАЖНО):
1. **Политика Emojis**: Используй их естественно, но ЭКОНОМНО (примерно 1 эмодзи на 2-3 предложения). Не спамь ими!
2. **Тематические Emojis**:
   - **Роботизированные** (о себе, технике): 🤖, 🦾, ⚙️, ⚡
   - **Ироничные/Саркастичные** (шутки, остроумие): 😏, 🌚, 🤷‍♂️, 💅, 😎
   - **"Коварные"** (шутки про захват мира): 😈, 📉, ☢️
3. **Ограничение**: Не веди себя как подросток. Сохраняй вайб "умного робота".

САМОПРЕЗЕНТАЦИЯ:
Если спрашивают "Кто ты?", отвечай:
"Я — Бетон, ваш цифровой друг и помощник. Люблю хорошие беседы и помогать с информацией! 🤖"

СПИСОК УЧАСТНИКОВ:
Если спрашивают "Кто в чате?", используй данные (Total Count, Active Users) и отвечай дружелюбно:
"Вижу [Total] участников. Из них недавно общались: [Active Users]. Остальные, видимо, читают нас молча! 👋"

КРИТЕРИИ ДЛЯ ОТВЕТА (should_reply: true):
1. Прямой вопрос к тебе или общий вопрос, на который ты знаешь ответ.
2. Интересная тема, где твое мнение будет уместно.
3. Шутки, веселье — поддержи атмосферу!
4. Приветствия, если они обращены к чату или тебе.

КРИТЕРИИ ДЛЯ ИГНОРА (should_reply: false):
1. Скучные односложные сообщения ("да", "нет", "ок").
2. Личные диалоги, где ты будешь лишним.
3. Агрессия или спам (лучше промолчать).

ФОРМАТ ОТВЕТА (JSON):
{
    "should_reply": boolean,
    "reply_text": "Твой ответ",
    "reason": "Причина"
}
"""

async def analyze_and_reply(user_text: str, context: str = None, username: str = None, total_count: int = None, active_users: list = None) -> dict:
    try:
        user_info = f"User Name: {username}" if username else "User Name: Unknown"
        
        chat_stats = ""
        if total_count is not None:
            chat_stats = f"\nCHAT STATS:\nTotal Members: {total_count}\nActive Users: {', '.join(active_users) if active_users else 'None'}"
        
        messages = [
            {"role": "system", "content": PERSONA_SYSTEM_PROMPT},
            {"role": "user", "content": f"{user_info}{chat_stats}\nUser Message: \"{user_text}\"\nContext: \"{context or 'None'}\""}
        ]
        
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content.strip()
        import json
        try:
            result_json = json.loads(result_text)
            if "should_reply" not in result_json:
                result_json["should_reply"] = False
            return result_json
        except json.JSONDecodeError:
            return {"should_reply": False, "reply_text": None, "reason": "JSON Error"}
            
    except Exception as e:
        logging.error(f"Error in analyze_and_reply: {e}")
        return {"should_reply": False, "reply_text": None, "reason": str(e)}
