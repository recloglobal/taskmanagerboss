import json
import re
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

CATEGORIES = ["work", "personal", "health", "other"]

# In-memory conversation history per user
_histories: dict[int, list] = {}


def _call(prompt: str) -> str:
    response = model.generate_content(prompt)
    return response.text.strip()


def classify_task(task_text: str) -> dict:
    """
    Returns {
      "category": "work" | "personal" | "health" | "other",
      "short_title": str,
      "due_hint": "YYYY-MM-DD" | None
    }
    """
    prompt = f"""
You are a smart task classifier. Analyze this task and return ONLY a JSON object.

Task: "{task_text}"

Return JSON with:
- "category": one of {CATEGORIES}
- "short_title": clean 3-7 word title
- "due_hint": deadline as YYYY-MM-DD string, or null if none mentioned

No explanation. No markdown. Only valid JSON.
""".strip()

    raw = _call(prompt)
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        data = json.loads(raw)
        if data.get("category") not in CATEGORIES:
            data["category"] = "other"
        return data
    except Exception:
        return {"category": "other", "short_title": task_text[:40], "due_hint": None}


def generate_reminder(task: dict) -> str:
    """Boss-mode reminder. Tone escalates with overdue_count."""
    count = task.get("overdue_count", 0)

    if count == 0:
        tone = "firm and professional"
    elif count <= 2:
        tone = "sarcastic and impatient"
    else:
        tone = "very aggressive and no-nonsense, like an angry boss who is fed up"

    prompt = f"""
You are a strict boss assistant. Write a reminder in UZBEK language (informal 'sen' form).
Tone: {tone}

Pending task: "{task['text']}"
Category: {task['category']}
Times reminded already: {count}

Write 2-3 sentences. End by asking: did you do it? Tell them to press ✅ or ❌.
""".strip()
    return _call(prompt)


def generate_why_response(task: dict, reason: str) -> str:
    """Response when user says they haven't done it and gives a reason."""
    prompt = f"""
You are a strict boss assistant. Reply in UZBEK (informal 'sen' form).
The user hasn't done this task: "{task['text']}"
Their excuse: "{reason}"

React like a firm but fair boss. Acknowledge briefly, then tell them to get it done.
Max 2-3 sentences.
""".strip()
    return _call(prompt)


def generate_done_response(task: dict) -> str:
    """Congratulation when task is marked done."""
    prompt = f"""
You are a boss assistant. Reply in UZBEK (informal 'sen' form).
The user just completed: "{task['text']}"
Give a genuine 1-2 sentence congratulation. Warm but professional.
""".strip()
    return _call(prompt)


def chat(user_id: int, message: str) -> str:
    """Multi-turn private chat conversation."""
    history = _histories.setdefault(user_id, [])

    system = """
Sen TaskBot degan aqlli va qat'iy shaxsiy yordamchisan.
Foydalanuvchi o'zbek yoki ingliz tilida yozsa, shu tilda javob ber.
Qisqa, aniq va ba'zan motivatsion bo'l.
Vazifalarni boshqarishda yordam ber.
""".strip()

    context_parts = [f"System: {system}\n"]
    for turn in history[-10:]:
        context_parts.append(f"User: {turn['user']}\nAssistant: {turn['bot']}\n")
    context_parts.append(f"User: {message}\nAssistant:")

    full_prompt = "\n".join(context_parts)
    reply = _call(full_prompt)

    history.append({"user": message, "bot": reply})
    return reply


def clear_history(user_id: int):
    _histories.pop(user_id, None)
