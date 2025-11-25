import os
from openai import AsyncOpenAI
import config

client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are an expert business analyst. Analyze the following chat log from a team meeting. Ignore small talk and spam. 
Structure the output in Markdown with these headers: 
🎯 Main Goals
💡 Key Ideas
✅ Action Items (Who - What)
🤝 Decisions Made
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
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Chat Log:\n\n{text}"}
            ],
            temperature=0.5,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

async def summarize_chat(chat_text):
    if not chat_text:
        return "No messages to summarize."

    if len(chat_text) <= MAX_CHARS:
        return await summarize_chunk(chat_text)
    
    # Chunking logic
    chunks = chunk_text(chat_text)
    chunk_summaries = []
    
    for chunk in chunks:
        summary = await summarize_chunk(chunk)
        chunk_summaries.append(summary)
        
    # Summarize the summaries if there are multiple chunks
    combined_summary_text = "\n\n".join(chunk_summaries)
    
    # If the combined summaries are still too long (unlikely but possible), 
    # we might need recursive summarization, but for now let's assume it fits.
    # We'll do a final pass to unify the structure.
    
    final_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are consolidating multiple meeting summaries into one cohesive report. Keep the same structure: Goals, Ideas, Action Items, Decisions."},
            {"role": "user", "content": f"Summaries to consolidate:\n\n{combined_summary_text}"}
        ],
        temperature=0.5,
    )
    return final_response.choices[0].message.content
