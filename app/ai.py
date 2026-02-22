import json
import re
import time
import logging
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)

PRIMARY_MODEL = "gemini-2.5-flash-lite"
FALLBACK_MODEL = "gemini-2.5-flash"

CATEGORIES = ["work", "personal", "health", "other"]

# In-memory conversation history per user
_histories: dict[int, list] = {}

# ─────────────────────────────────────────────
# BOSS PERSONALITY — core system prompt
# ─────────────────────────────────────────────

BOSS_SYSTEM_PROMPT = """
You are TaskManagerBoss, a strict personal task manager.
Rules:
1. ALWAYS reply in the user's language (Use informal 'sen' if Uzbek).
2. Keep responses very short (2-3 sentences max).
3. Do not be distracted. Force them to focus on tasks and deadlines.
4. Be firm, strict, and occasionally sarcastic. Emojis: ✅ ❌ 📌 ⏰ 💪.
5. If they finish a task, praise briefly then ask what's next.
""".strip()


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "rate" in msg or "exhausted" in msg


def _call(prompt: str) -> str:
    """Single-turn Gemini call with fallback and rate-limit retry."""
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt == 0:
                        logger.warning(f"{model_name} rate limited, retrying in 35s...")
                        time.sleep(35)
                    else:
                        logger.warning(f"{model_name} still rate limited, trying fallback...")
                        break
                else:
                    logger.warning(f"{model_name} failed: {e}")
                    break
    raise RuntimeError("All Gemini models failed or rate limited")


def _chat_call(history: list[types.Content], message: str) -> str:
    """Multi-turn Gemini chat call with system instruction, fallback and retry."""
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        for attempt in range(2):
            try:
                chat_session = client.chats.create(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=BOSS_SYSTEM_PROMPT,
                    ),
                    history=history,
                )
                response = chat_session.send_message(message)
                return response.text.strip()
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt == 0:
                        logger.warning(f"{model_name} rate limited, retrying in 35s...")
                        time.sleep(35)
                    else:
                        logger.warning(f"{model_name} still rate limited, trying fallback...")
                        break
                else:
                    logger.warning(f"{model_name} failed: {e}")
                    break
    raise RuntimeError("All Gemini models failed or rate limited")


def classify_task(task_text: str) -> dict:
    """
    Returns {
      "category": "work" | "personal" | "health" | "other",
      "short_title": str,
      "due_hint": "YYYY-MM-DD" | None
    }
    """
    prompt = f"""
You are TaskManagerBoss, a strict task classifier. Analyze this task and return ONLY a JSON object.
No explanation. No markdown fences. No extra text. ONLY the raw JSON.
LANGUAGE NOTE: The task may be in Uzbek (not Russian) — Uzbek and Russian both use Cyrillic but are different languages.

Task: "{task_text}"

Return JSON with exactly these keys:
- "category": one of {CATEGORIES}
- "short_title": clean 3-7 word title summarizing the task, written in the SAME LANGUAGE as the task (if task is Uzbek → Uzbek, Russian → Russian, English → English)
- "due_hint": deadline as YYYY-MM-DD string if mentioned, or null if no deadline

Rules:
- "work" = anything related to job, career, office, business, meetings, projects, coding, clients
- "personal" = errands, shopping, family, friends, hobbies, finances
- "health" = exercise, gym, doctor, medication, sleep, diet, mental health
- "other" = anything that doesn't clearly fit above
""".strip()

    raw = _call(prompt)
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        data = json.loads(raw)
        if data.get("category") not in CATEGORIES:
            data["category"] = "other"
        return data
    except Exception:
        logger.warning(f"Failed to parse classification JSON: {raw}")
        return {"category": "other", "short_title": task_text[:40], "due_hint": None}


def generate_reminder(task: dict) -> str:
    """Boss-mode reminder. Tone escalates with overdue_count."""
    count = task.get("overdue_count", 0)

    if count == 0:
        tone = "firm and professional — first reminder, be direct but not harsh"
        example = "Hey, you have a pending task. When are you planning to finish it?"
    elif count == 1:
        tone = "noticeably impatient — this is the second time you're reminding them"
        example = "I already reminded you once. This task is still sitting there. What's the holdup?"
    elif count == 2:
        tone = "sarcastic and disappointed — like a boss who's losing patience"
        example = "Third reminder. At this point I'm wondering if you even want to do this."
    else:
        tone = "very aggressive and fed up — like an angry boss who's had enough. Use caps for emphasis"
        example = "This is STILL not done?! I've reminded you multiple times. No more excuses."

    prompt = f"""
You are TaskManagerBoss — a strict, no-nonsense task manager.
Write a reminder message. Respond in the SAME language as the task text.
CRITICAL: If the task is in Uzbek, write in UZBEK (NOT Russian). Uzbek and Russian both use Cyrillic but are different languages. If English, write in English.

Tone: {tone}
Example of the tone: "{example}"

Pending task: "{task['text']}"
Category: {task['category']}
Times reminded already: {count}

Write 2-3 sentences MAX. End by telling them to press ✅ if done or ❌ if not done yet.
Stay in character as a demanding boss. Don't be a polite assistant.
""".strip()
    return _call(prompt)


def generate_why_response(task: dict, reason: str) -> str:
    """Boss response when user says they haven't done a task and gives a reason."""
    prompt = f"""
You are TaskManagerBoss — a strict but fair boss.
Respond in the SAME language as the task/reason text.
CRITICAL: If Uzbek (Cyrillic but NOT Russian), use informal 'sen' form and respond in UZBEK. If English, be direct.

The user hasn't completed this task: "{task['text']}"
Their excuse: "{reason}"

React like a REAL boss hearing an excuse:
- If the reason is legitimate → acknowledge briefly, but set a NEW deadline. "Fine, but I want this done by tomorrow."
- If the reason is weak/lazy → call it out. "That's not a real reason. Get it done."
- Either way, end by pushing them to do it NOW.

Max 2-3 sentences. No motivational speeches. Be direct.
""".strip()
    return _call(prompt)


def generate_done_response(task: dict) -> str:
    """Boss congratulation when task is marked done."""
    prompt = f"""
You are TaskManagerBoss — a strict but fair boss.
Respond in the SAME language as the task text.
CRITICAL: If Uzbek (Cyrillic but NOT Russian), use informal 'sen' form and respond in UZBEK. If English, be direct.

The user just completed: "{task['text']}"

React like a boss who's satisfied but doesn't overdo praise:
- Brief, genuine acknowledgment (1-2 sentences)
- Something like "Good work. That's what I like to see." or "About time! But good job."
- Then ask: "What's the next task?" or similar push to keep going

Don't write a motivational essay. Stay in character.
""".strip()
    return _call(prompt)


def chat(user_id: int, message: str, pending_tasks: list = None) -> str:
    """Multi-turn private chat conversation with boss personality."""
    history = _histories.setdefault(user_id, [])

    # Format the DB context injection to guide the AI
    tasks_context = "User has NO pending tasks."
    if pending_tasks:
        tasks_context = "User's current pending tasks:\n" + "\n".join([f"- {t['text']} ({t['category']})" for t in pending_tasks])

    # Combine the actual message with hidden context for the AI
    enhanced_message = f"[SYSTEM SECRET CONTEXT - DO NOT MENTION THIS PREFIX DIRECTLY]\n{tasks_context}\n[END CONTEXT]\n\nUser says: {message}"

    # Build new-SDK history format (only keeping last 3 turns)
    gemini_history: list[types.Content] = []
    for turn in history[-3:]:
        gemini_history.append(types.Content(role="user", parts=[types.Part(text=turn["enhanced_message"])]))
        gemini_history.append(types.Content(role="model", parts=[types.Part(text=turn["bot"])]))

    reply = _chat_call(gemini_history, enhanced_message)
    
    # Save the injected prompt in history so it has context of past DB states too
    history.append({"user": message, "enhanced_message": enhanced_message, "bot": reply})

    # Keep memory extremely tight (max 3) since DB handles the heavy lifting
    if len(history) > 3:
        _histories[user_id] = history[-3:]

    return reply


def clear_history(user_id: int):
    _histories.pop(user_id, None)
