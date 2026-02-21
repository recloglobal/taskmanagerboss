# TaskManagerBoss — Full Build Specification
> A Telegram bot that manages your tasks like a strict boss.
> Built with Python, PostgreSQL, Gemini AI, and Docker.

---

## ⚡ Agent Orchestration Instructions

This project is split into **parallel workstreams**. Assign agents as follows for maximum speed:

| Agent | Responsibility | Can start immediately? |
|---|---|---|
| **Agent 1 — Infrastructure** | Dockerfile, docker-compose, .env, config.py | ✅ Yes |
| **Agent 2 — Database** | models.py, database.py, Alembic migrations | ✅ Yes (no dependency on Agent 3-4) |
| **Agent 3 — AI Layer** | ai.py — all Gemini calls | ✅ Yes (independent) |
| **Agent 4 — Bot Handlers** | handlers/start.py, group.py, private.py, callbacks.py | ⏳ After Agent 1 + 2 done |
| **Agent 5 — Scheduler** | scheduler.py — reminder engine | ⏳ After Agent 2 + 3 done |
| **Agent 6 — Integration** | main.py — wire everything together + test | ⏳ Last, after all agents done |

> **Rule:** Each agent must verify their piece works in isolation before Agent 6 integrates.

---

## 📋 Project Overview

### What it does
- You write a task in the `#general` topic of a Telegram group
- The bot reads it, sends it to Gemini AI for classification
- Bot routes the task into the correct topic (`#work`, `#personal`, `#health`, `#other`)
- Bot saves the task to PostgreSQL with optional due date
- Bot reminds you about pending tasks — tone escalates the longer you ignore it
- You reply ✅ Done or ❌ Not yet via inline buttons
- Bot also works as a private chat AI assistant (Gemini-powered, understands Uzbek)

### Key constraints
- Telegram bots **cannot create topics** — topics must be pre-created manually
- Bot must be **admin** in the group with Send Messages permission
- Fixed categories for MVP: `work`, `personal`, `health`, `other`
- Gemini free tier: 10 RPM, 250 RPD — sufficient for personal use

---

## 🏗️ Final Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| Telegram library | python-telegram-bot v21 (async) |
| AI | Gemini 2.5 Flash (free tier) |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Scheduler | APScheduler 3.x |
| Containerization | Docker + docker-compose |
| Secrets | .env file (never committed) |

---

## 📁 Project Structure

```
taskmanagerboss/
├── app/
│   ├── main.py              ← Entry point: starts bot + scheduler
│   ├── config.py            ← Loads all .env variables
│   ├── database.py          ← SQLAlchemy async engine + session
│   ├── models.py            ← Task table definition
│   ├── ai.py                ← All Gemini API calls
│   ├── scheduler.py         ← APScheduler reminder jobs
│   └── handlers/
│       ├── __init__.py
│       ├── start.py         ← /start command (private chat)
│       ├── topics.py        ← /topics command (detects topic IDs)
│       ├── group.py         ← Reads #general, routes tasks
│       ├── callbacks.py     ← Inline button YES/NO handler
│       └── private.py       ← Private chat AI conversation
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                     ← Your secrets (never commit)
└── .env.example             ← Safe template (commit this)
```

---

## 🔐 Environment Variables

### `.env` (never commit)
```env
BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here

POSTGRES_USER=taskbot
POSTGRES_PASSWORD=taskbot123
POSTGRES_DB=taskbot_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

OWNER_ID=your_telegram_numeric_user_id

TOPIC_GENERAL=        ← fill after /topics command
TOPIC_WORK=           ← fill after /topics command
TOPIC_PERSONAL=       ← fill after /topics command
TOPIC_HEALTH=         ← fill after /topics command
TOPIC_OTHER=          ← fill after /topics command
```

### `.env.example` (commit this)
```env
BOT_TOKEN=
GEMINI_API_KEY=

POSTGRES_USER=taskbot
POSTGRES_PASSWORD=
POSTGRES_DB=taskbot_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

OWNER_ID=

TOPIC_GENERAL=
TOPIC_WORK=
TOPIC_PERSONAL=
TOPIC_HEALTH=
TOPIC_OTHER=

> **How to get OWNER_ID:** Message @userinfobot on Telegram → it returns your numeric ID
> **How to get topic IDs:** Run `/topics` inside each group topic after bot is running

---

## 🗄️ Database Schema

```sql
CREATE TABLE tasks (
    id            SERIAL PRIMARY KEY,
    text          TEXT NOT NULL,
    category      VARCHAR(20) DEFAULT 'other',
    status        VARCHAR(20) DEFAULT 'pending',  -- pending | done
    group_id      BIGINT NOT NULL,
    topic_id      INTEGER,                         -- destination topic thread ID
    owner_id      BIGINT NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW(),
    due_at        TIMESTAMP,                       -- user-defined deadline (nullable)
    reminded_at   TIMESTAMP,                       -- last reminder timestamp
    overdue_count INTEGER DEFAULT 0,               -- increments each reminder
    snooze_reason TEXT                             -- why user said not yet
);
```

---

## 📦 requirements.txt

```
python-telegram-bot==21.6
google-generativeai==0.7.2
sqlalchemy==2.0.36
asyncpg==0.29.0
alembic==1.13.3
apscheduler==3.10.4
psycopg2-binary==2.9.9
python-dotenv==1.0.1
```

---

## 🐳 Agent 1 — Infrastructure Files

### `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

CMD ["python", "main.py"]
```

### `docker-compose.yml`
```yaml
services:
  db:
    image: postgres:16
    restart: always
    env_file: .env
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

  bot:
    build: .
    restart: always
    env_file: .env
    depends_on:
      db:
        condition: service_healthy

volumes:
  postgres_data:
```

### `app/config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

DATABASE_URL_SYNC = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

TOPIC_GENERAL = int(os.getenv("TOPIC_GENERAL", 0))
TOPIC_WORK = int(os.getenv("TOPIC_WORK", 0))
TOPIC_PERSONAL = int(os.getenv("TOPIC_PERSONAL", 0))
TOPIC_HEALTH = int(os.getenv("TOPIC_HEALTH", 0))
TOPIC_OTHER = int(os.getenv("TOPIC_OTHER", 0))

CATEGORY_TOPIC_MAP = {
    "work": TOPIC_WORK,
    "personal": TOPIC_PERSONAL,
    "health": TOPIC_HEALTH,
    "other": TOPIC_OTHER,
}

REMINDER_INTERVAL_MINUTES = 60
```

---

## 🗄️ Agent 2 — Database Layer

### `app/database.py`
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass
```

### `app/models.py`
```python
from datetime import datetime
from sqlalchemy import BigInteger, Integer, Text, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="other")
    status: Mapped[str] = mapped_column(String(20), default="pending")

    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0)
    snooze_reason: Mapped[str] = mapped_column(Text, nullable=True)
```

### Alembic Setup (run these commands in order)

```bash
# 1. Open shell inside bot container
docker-compose exec bot bash

# 2. Initialize alembic (run once)
alembic init alembic

# 3. Exit container
exit
```

### `alembic/env.py` — replace the relevant section

Find and replace `target_metadata = None` with:
```python
import sys
sys.path.insert(0, '/app')
from database import Base
import models  # noqa
target_metadata = Base.metadata
```

Add at the top of `alembic/env.py`:
```python
from config import DATABASE_URL_SYNC
```

Find `run_migrations_online()` function and add before `connectable = engine_from_config(`:
```python
config.set_main_option("sqlalchemy.url", DATABASE_URL_SYNC)
```

### Run Migration
```bash
docker-compose exec bot bash
alembic revision --autogenerate -m "create tasks table"
alembic upgrade head
exit
```

### Verify table exists
```bash
docker-compose exec db psql -U taskbot -d taskbot_db -c "\dt"
# Should show: tasks table
```

---

## 🤖 Agent 3 — AI Layer

### `app/ai.py`
```python
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
```

---

## 📨 Agent 4 — Bot Handlers

### `app/handlers/__init__.py`
```python
# empty
```

### `app/handlers/start.py`
```python
from telegram import Update
from telegram.ext import ContextTypes

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men TaskManagerBoss — sening shaxsiy vazifa menejeringman.\n\n"
        "📌 Guruhda #general mavzusiga vazifa yoz — men uni tasniflab, to'g'ri mavzuga qo'yaman.\n"
        "⏰ Muddatingni o'tkazib yuborsang, men senga xabar beraman.\n"
        "💬 Bu yerda esa men bilan erkin suhbatlashishingiz mumkin!"
    )
```

### `app/handlers/topics.py`
```python
from telegram import Update
from telegram.ext import ContextTypes

async def topics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Run this inside each topic to get its thread ID.
    """
    thread_id = update.message.message_thread_id
    chat_id = update.message.chat_id

    if thread_id:
        await update.message.reply_text(
            f"📋 Bu mavzuning ID si:\n\n"
            f"`{thread_id}`\n\n"
            f"Buni `.env` faylingizga to'g'ri o'zgaruvchiga qo'ying.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"Bu asosiy guruh eki #general mavzusi.\n"
            f"Chat ID: `{chat_id}`",
            parse_mode="Markdown"
        )
```

### `app/handlers/group.py`
```python
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select

from config import OWNER_ID, TOPIC_GENERAL, CATEGORY_TOPIC_MAP
from database import SessionLocal
from models import Task
from ai import classify_task


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    # Only process messages from owner in #general topic
    if message.from_user.id != OWNER_ID:
        return
    if message.message_thread_id != TOPIC_GENERAL:
        return

    task_text = message.text
    group_id = message.chat_id

    # Classify with Gemini
    classification = classify_task(task_text)
    category = classification.get("category", "other")
    short_title = classification.get("short_title", task_text[:40])
    due_hint = classification.get("due_hint")

    due_at = None
    if due_hint:
        try:
            due_at = datetime.strptime(due_hint, "%Y-%m-%d")
        except ValueError:
            pass

    # Get destination topic ID
    destination_topic = CATEGORY_TOPIC_MAP.get(category, CATEGORY_TOPIC_MAP["other"])

    # Save to database
    async with SessionLocal() as session:
        task = Task(
            text=task_text,
            category=category,
            status="pending",
            group_id=group_id,
            topic_id=destination_topic,
            owner_id=OWNER_ID,
            due_at=due_at,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # Post task into correct topic
    category_emoji = {"work": "💼", "personal": "🙋", "health": "💪", "other": "📌"}
    emoji = category_emoji.get(category, "📌")

    due_text = f"\n📅 Muddat: {due_at.strftime('%d.%m.%Y')}" if due_at else ""
    task_message = (
        f"{emoji} *{short_title}*\n\n"
        f"📝 {task_text}"
        f"{due_text}\n\n"
        f"🆔 Task #{task_id}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Bajarildi", callback_data=f"done:{task_id}"),
            InlineKeyboardButton("❌ Bajarilmadi", callback_data=f"notyet:{task_id}"),
        ]
    ])

    await context.bot.send_message(
        chat_id=group_id,
        message_thread_id=destination_topic,
        text=task_message,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    # Confirm in #general
    await message.reply_text(
        f"✅ Vazifa qabul qilindi!\n"
        f"📂 Kategoriya: *{category}*\n"
        f"📨 #{category} mavzusiga joylashtirildi.",
        parse_mode="Markdown"
    )
```

### `app/handlers/callbacks.py`
```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select

from database import SessionLocal
from models import Task
from ai import generate_done_response, generate_why_response


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # "done:123" or "notyet:123"
    action, task_id_str = data.split(":")
    task_id = int(task_id_str)

    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            await query.edit_message_text("❌ Vazifa topilmadi.")
            return

        if action == "done":
            task.status = "done"
            await session.commit()
            reply = generate_done_response({"text": task.text, "category": task.category})
            await query.edit_message_text(f"✅ *Bajarildi!*\n\n{reply}", parse_mode="Markdown")

        elif action == "notyet":
            # Ask for reason
            context.user_data[f"awaiting_reason_{task_id}"] = True
            await query.edit_message_text(
                "❌ Nima uchun bajarilmadi? Sababini yozing:",
            )
            context.user_data["pending_notyet_task_id"] = task_id


async def reason_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles user's text reply after pressing ❌ Not yet."""
    task_id = context.user_data.get("pending_notyet_task_id")
    if not task_id:
        return

    reason = update.message.text

    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        task.snooze_reason = reason
        task.overdue_count += 1
        await session.commit()
        task_dict = {"text": task.text, "category": task.category, "overdue_count": task.overdue_count}

    reply = generate_why_response(task_dict, reason)
    await update.message.reply_text(reply)
    context.user_data.pop("pending_notyet_task_id", None)
```

### `app/handlers/private.py`
```python
from telegram import Update
from telegram.ext import ContextTypes
from config import OWNER_ID
from ai import chat, clear_history


async def private_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    if message.from_user.id != OWNER_ID:
        return
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    user_text = message.text

    if user_text.lower() in ["/reset", "reset", "clear"]:
        clear_history(user_id)
        await message.reply_text("🔄 Suhbat tarixi tozalandi.")
        return

    reply = chat(user_id, user_text)
    await message.reply_text(reply)
```

---

## ⏰ Agent 5 — Scheduler

### `app/scheduler.py`
```python
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from database import SessionLocal
from models import Task
from ai import generate_reminder

logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot):
    """Check all pending tasks and send reminders if needed."""
    now = datetime.utcnow()

    async with SessionLocal() as session:
        result = await session.execute(
            select(Task).where(Task.status == "pending")
        )
        tasks = result.scalars().all()

    for task in tasks:
        should_remind = False

        if task.due_at:
            # Remind 1 day before due
            one_day_before = task.due_at - timedelta(days=1)
            if now >= one_day_before:
                should_remind = True
        else:
            # No due date: remind every 48 hours
            last = task.reminded_at or task.created_at
            if now >= last + timedelta(hours=48):
                should_remind = True

        if not should_remind:
            continue

        task_dict = {
            "text": task.text,
            "category": task.category,
            "overdue_count": task.overdue_count,
        }

        reminder_text = generate_reminder(task_dict)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Bajarildi", callback_data=f"done:{task.id}"),
                InlineKeyboardButton("❌ Bajarilmadi", callback_data=f"notyet:{task.id}"),
            ]
        ])

        try:
            await bot.send_message(
                chat_id=task.group_id,
                message_thread_id=task.topic_id,
                text=reminder_text,
                reply_markup=keyboard,
            )

            # Update reminder tracking
            async with SessionLocal() as session:
                result = await session.execute(select(Task).where(Task.id == task.id))
                t = result.scalar_one_or_none()
                if t:
                    t.reminded_at = now
                    t.overdue_count += 1
                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to send reminder for task {task.id}: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=60,
        args=[bot],
        id="reminder_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler
```

---

## 🔌 Agent 6 — Main Entry Point (integrate last)

### `app/main.py`
```python
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN
from handlers.start import start_handler
from handlers.topics import topics_handler
from handlers.group import group_message_handler
from handlers.callbacks import button_callback_handler, reason_message_handler
from handlers.private import private_message_handler
from scheduler import start_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("topics", topics_handler))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(done|notyet):"))

    # Group messages (reads #general topic)
    app.add_handler(MessageHandler(
        filters.Chat(chat_type=["group", "supergroup"]) & filters.TEXT & ~filters.COMMAND,
        group_message_handler
    ))

    # Private chat: reason replies after ❌
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        reason_message_handler,
    ), group=1)

    # Private chat: general AI conversation
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        private_message_handler,
    ), group=2)

    # Start scheduler
    start_scheduler(app.bot)

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
```

---

## 🪜 Step-by-Step Build Order

| Step | What | Test |
|---|---|---|
| ✅ 1 | Docker + postgres + bare bot | `/start` replies in private chat |
| ⬜ 2 | config.py + database.py + models.py + Alembic | `tasks` table visible in postgres |
| ⬜ 3 | ai.py | Gemini classifies a test task correctly |
| ⬜ 4 | handlers/topics.py | `/topics` returns thread ID in each topic |
| ⬜ 5 | Fill `.env` TOPIC_ values from Step 4 | All 5 topic IDs in .env |
| ⬜ 6 | handlers/group.py | Task in #general → appears in #work/#personal/etc |
| ⬜ 7 | handlers/callbacks.py | ✅/❌ buttons update task status in DB |
| ⬜ 8 | scheduler.py | Reminder sent, tone escalates |
| ⬜ 9 | handlers/private.py | Full AI chat works in private |
| ⬜ 10 | Deploy to DigitalOcean | Same docker-compose, new server |

---

## 🚀 Deployment to DigitalOcean (Step 10)

```bash
# On your DigitalOcean droplet:
git clone https://github.com/yourusername/taskmanagerboss.git
cd taskmanagerboss

# Copy your .env file (never store in git)
nano .env   # paste your values

# Build and run
docker-compose up --build -d

# Check logs
docker-compose logs -f bot
```

---

## 🧪 Useful Debug Commands

```bash
# View bot logs
docker-compose logs -f bot

# View postgres logs
docker-compose logs -f db

# Open postgres shell
docker-compose exec db psql -U taskbot -d taskbot_db

# Check tasks table
docker-compose exec db psql -U taskbot -d taskbot_db -c "SELECT * FROM tasks;"

# Restart bot only (after code change)
docker-compose restart bot

# Full rebuild
docker-compose down && docker-compose up --build

# Open bot container shell
docker-compose exec bot bash
```

---

## ✅ Checklist Before Going Live

- [ ] All 5 topic IDs filled in `.env`
- [ ] Bot is admin in the group
- [ ] `/start` works in private chat
- [ ] `/topics` returns correct IDs in each topic
- [ ] Task in #general → routes to correct topic
- [ ] ✅/❌ buttons work
- [ ] Reminder fires after 48h (test by setting `hours=0.01` temporarily)
- [ ] Private chat responds in Uzbek
- [ ] `.env` is in `.gitignore` and never pushed
