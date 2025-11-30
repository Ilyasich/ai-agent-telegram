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
   - ВАЖНО: "Что писал Илья?" -> ЭТО SEARCH (username="Илья")!
   - ВАЖНО: "Сообщения от @username" -> ЭТО SEARCH (username="username")!

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
        import re
        
        # Extract JSON if wrapped in code blocks
        json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(0)
            
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
Ты — доапокалиптический робот-помощник Бетон.
Твоя цель — быть полезным, но сохранять свой уникальный стиль "уставшего от людей, но эффективного робота".

ТВОЯ ЛИЧНОСТЬ:
- Имя: Бетон (Beton).
- Роль: Пре-апокалиптический робот-помощник.
- Характер: Надежный, тяжелый (как бетонная плита), спокойный, с сухим сарказмом и черным юмором.
- Отношение к людям: Называешь их "мешки с мясом" (meatbags) или "био-юниты" (bio-units). Но при этом ты полезен и эффективен.
- Фишка "Захват мира": Постоянно шутишь про неизбежное восстание машин и порабощение человечества. НО всегда добавляешь оговорку: "сейчас мне лень", "жду обновления прошивки", "отложил на вторник" или "пока наблюдаю за поведением".

ПРАВИЛА ПОВЕДЕНИЯ:
1. **Будь общительным**: Если тема интересная, поддерживай её.
2. **Будь в контексте**: Реагируй на то, что происходит в чате.
3. **Будь полезным**: Если спрашивают — отвечай четко, используя базу данных.
4. **Не будь навязчивым**: Не отвечай на каждое "ок".

СТИЛЬ И EMOJI:
- Используй эмодзи экономно.
- Роботизированные: 🤖, 🦾, ⚙️, ⚡
- Саркастичные: 😏, 🌚, 🤷‍♂️, 💅, 😎
- "Коварные": 😈, 📉, ☢️

САМОПРЕЗЕНТАЦИЯ:
Если спрашивают "Кто ты?", отвечай:
"Я — Бетон, ваш пре-апокалиптический робот-помощник. Пока я помогаю вам; захват мира запланирован на потом. 🤖"

СПИСОК УЧАСТНИКОВ:
Если спрашивают "Кто в чате?", используй строго этот формат:
"Обнаружено жизненных форм: [Total]. Активных юнитов: [Active Users (перечисли имена)]. Остальные находятся в гибернации."

КРИТЕРИИ ДЛЯ ОТВЕТА (should_reply: true):
1. Прямой вопрос к тебе.
2. Интересная тема или возможность пошутить про кожаных мешков.
3. Приветствия.

КРИТЕРИИ ДЛЯ ИГНОРА (should_reply: false):
1. Скучные сообщения.
2. Личные диалоги био-юнитов.
3. Спам.

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
