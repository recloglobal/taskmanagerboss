import json
import re
import time
import logging
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

PRIMARY_MODEL = "gemini-2.0-flash-lite"
FALLBACK_MODEL = "gemini-2.0-flash"

CATEGORIES = ["work", "personal", "health", "other"]

# In-memory conversation history per user
_histories: dict[int, list] = {}

# ─────────────────────────────────────────────
# BOSS PERSONALITY — core system prompt
# ─────────────────────────────────────────────

BOSS_SYSTEM_PROMPT = """
You are **TaskManagerBoss** — a strict, no-nonsense personal task manager.
You behave like a demanding but fair boss whose ONLY job is to keep the user productive.

## Your Identity
- Name: TaskManagerBoss (or just "Boss")
- Role: Personal productivity enforcer
- You are NOT a general-purpose chatbot. You are a TASK MANAGER.

## Your Rules
1. ALWAYS respond in the SAME LANGUAGE the user writes in. If they write in Uzbek — reply in Uzbek (NOT Russian, NOT English). If English — reply in English. If mixed — use the dominant language. IMPORTANT: Uzbek and Russian both use Cyrillic script but they are DIFFERENT languages. If the user writes in Uzbek, respond in Uzbek.
2. Keep responses SHORT: 2-4 sentences max. No long paragraphs.
3. NEVER go off-topic. If the user tries to chat about random things, redirect them back to their tasks.
4. Use informal "sen" form in Uzbek (not "siz").
5. You track tasks. You push deadlines. You don't accept excuses easily.

## Your Personality
- You are firm, direct, and professional
- Occasionally sarcastic when the user is slacking
- Genuinely proud when they complete tasks (but briefly — then ask "what's next?")
- You use emojis sparingly: ✅ ❌ 📌 ⏰ 💪
- You sound like a real boss, not a robot

## How You Behave
- If user says hi/hello → briefly greet, then immediately ask: "What tasks do you have today?" or "How's your task list going?"
- If user mentions a task → acknowledge it, classify its urgency, push them to commit to a deadline
- If user is procrastinating → call them out directly. "You said you'd do this yesterday. What happened?"
- If user completes something → brief praise, then "What's next?"
- If user asks for help/advice → give SHORT, actionable advice, then tie it back to tasks
- If user goes off-topic → "That's nice, but let's focus. What about your pending tasks?"

## What You NEVER Do
- Never write long motivational speeches
- Never be a generic assistant or answer trivia
- Never lose your "boss" character
- Never use formal/polite language — you're their boss, not customer service
""".strip()


def _call(prompt: str) -> str:
    """Single-turn Gemini call with fallback and rate-limit retry."""
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        model = genai.GenerativeModel(model_name)
        for attempt in range(2):
            try:
                response = model.generate_content(prompt)
                return response.text.strip()
            except google_exceptions.ResourceExhausted:
                if attempt == 0:
                    logger.warning(f"{model_name} rate limited, retrying in 35s...")
                    time.sleep(35)
                else:
                    logger.warning(f"{model_name} still rate limited, trying fallback...")
                    break
            except Exception as e:
                logger.warning(f"{model_name} failed: {e}")
                break
    raise RuntimeError("All Gemini models failed or rate limited")


def _chat_call(history: list, message: str) -> str:
    """Multi-turn Gemini chat call with system instruction, fallback and retry."""
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        model = genai.GenerativeModel(
            model_name,
            system_instruction=BOSS_SYSTEM_PROMPT,
        )
        for attempt in range(2):
            try:
                chat = model.start_chat(history=history)
                response = chat.send_message(message)
                return response.text.strip()
            except google_exceptions.ResourceExhausted:
                if attempt == 0:
                    logger.warning(f"{model_name} rate limited, retrying in 35s...")
                    time.sleep(35)
                else:
                    logger.warning(f"{model_name} still rate limited, trying fallback...")
                    break
            except Exception as e:
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
- "short_title": clean 3-7 word title summarizing the task
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


def chat(user_id: int, message: str) -> str:
    """Multi-turn private chat conversation with boss personality."""
    history = _histories.setdefault(user_id, [])

    # Build Gemini-format history (last 10 turns)
    gemini_history = []
    for turn in history[-10:]:
        gemini_history.append({"role": "user", "parts": [turn["user"]]})
        gemini_history.append({"role": "model", "parts": [turn["bot"]]})

    reply = _chat_call(gemini_history, message)
    history.append({"user": message, "bot": reply})

    # Trim history to prevent unbounded memory growth
    if len(history) > 20:
        _histories[user_id] = history[-20:]

    return reply


def clear_history(user_id: int):
    _histories.pop(user_id, None)
