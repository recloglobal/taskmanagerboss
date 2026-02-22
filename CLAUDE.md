# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A Telegram bot ("TaskManagerBoss") that acts like a strict boss for personal task management.
- Reads tasks posted in a Telegram group's `#general` topic
- Classifies them with AI into categories: `work`, `personal`, `health`, `other`
- Routes each task into the matching group topic
- Sends escalating reminders until tasks are marked done
- Private chat mode: full AI assistant with boss personality in Uzbek/English

Full spec: `TASKMANAGERBOSS_SPEC.md` | Claude Code setup guide: `CLAUDE_CODE_SETUP.md`

## Stack

- Python 3.11, python-telegram-bot v21 (async)
- **OpenRouter** via `openai` client library (free-tier models with fallback chain): llama-3.3-70b → llama-4-scout → deepseek-r1 → gemma-3n → hermes-3-405b
- PostgreSQL 16, SQLAlchemy 2.0 async (`asyncpg`), Alembic migrations
- APScheduler 3.x (`AsyncIOScheduler` — required for async bot)
- Docker + docker-compose (development and DigitalOcean deployment)

## Key Commands

```bash
# Start / build
docker-compose up --build          # Full rebuild and start
docker-compose up -d               # Start in background
docker-compose restart bot         # Restart bot only after Python changes
docker-compose down && docker-compose up --build  # Full reset

# Logs
docker-compose logs -f bot
docker-compose logs -f db

# Shell access
docker-compose exec bot bash
docker-compose exec db psql -U taskbot -d taskbot_db

# Migrations (always run inside bot container)
docker-compose exec bot bash
alembic revision --autogenerate -m "description"
alembic upgrade head
exit

# Inspect tasks
docker-compose exec db psql -U taskbot -d taskbot_db -c "SELECT id, text, category, status FROM tasks ORDER BY created_at DESC LIMIT 10;"
```

## Architecture

```
app/main.py          ← Entry point: registers all handlers, starts scheduler
app/config.py        ← All env vars (import from here, never os.getenv() in handlers)
app/database.py      ← SQLAlchemy async engine + SessionLocal
app/models.py        ← Task ORM model
app/ai.py            ← All AI calls via OpenRouter: classify_task(), generate_reminder(),
                       generate_done_response(), generate_why_response(), chat(), clear_history()
app/scheduler.py     ← APScheduler reminder engine (runs every 60 min)
app/handlers/
  start.py           ← /start command (private chat welcome)
  topics.py          ← /topics command (returns thread ID for .env setup)
  group.py           ← Reads #general, classifies via AI, routes to topic, saves to DB
  callbacks.py       ← Inline ✅/❌ button handlers + snooze reason collector
  private.py         ← Private chat AI conversation
alembic/             ← DB migrations (run inside container only)
```

**Request flow (group task):** User posts in `#general` → `group.py` filters by `OWNER_ID` + `TOPIC_GENERAL` → `classify_task()` in `ai.py` → saves `Task` to DB → posts to destination topic with inline buttons.

**Reminder logic:** Scheduler runs every 60 min → queries all `pending` tasks:
- Tasks **with** due date: remind 1 day before due
- Tasks **without** due date: remind every 48 hours after last reminder
- `overdue_count` drives tone escalation: 0=firm, 1=impatient, 2=sarcastic, 3+=aggressive caps

**AI fallback chain:** `ai.py::_call()` and `_chat_call()` try each model in `MODELS` list in order. On any failure, waits 2 seconds and tries the next. All synchronous AI calls are wrapped in `asyncio.to_thread()` to avoid blocking the event loop.

**Conversation history** for private chat is stored in `ai.py::_histories` dict (last 20 turns kept, last 10 sent to model) — lost on restart.

**Snooze flow:** Pressing ❌ sets `context.user_data["pending_notyet_task_id"]` → `reason_message_handler` in `callbacks.py` picks it up (handler group=1, before `private_message_handler` in group=2).

## Critical Rules

- **All DB calls must be async:** `async with SessionLocal() as session:`
- **Never run Alembic outside the bot container** — it needs the container's Python path and env
- **All AI calls must go through `app/ai.py`** — never call OpenRouter directly from handlers
- **Wrap all AI calls in `asyncio.to_thread()`** — they are synchronous and will block the event loop
- **`AsyncIOScheduler`** (not `BackgroundScheduler`) is required because the bot is async
- **Handler registration order in `main.py` matters** — callbacks before group/private filters; `reason_message_handler` (group=1) before `private_message_handler` (group=2)
- **Topics cannot be created via the API** — pre-create them in Telegram, then get IDs via `/topics`
- **Bot must be group admin** with Send Messages permission
- **`DATABASE_URL_SYNC`** exists in `config.py` for Alembic (uses `psycopg2`, not `asyncpg`)

## Environment Variables

See `.env.example` for all required vars. Key ones:
- `BOT_TOKEN`, `OPENROUTER_API_KEY`, `OWNER_ID`
- `TOPIC_GENERAL`, `TOPIC_WORK`, `TOPIC_PERSONAL`, `TOPIC_HEALTH`, `TOPIC_OTHER` — get these by running `/topics` inside each group topic after bot starts
- `DATABASE_URL` is constructed in `config.py` from the `POSTGRES_*` vars (never set `DATABASE_URL` directly in `.env`)

## Current Build Status

- [x] Step 1 — Docker + postgres + `/start` working
- [x] Step 2 — `config.py`, `database.py`, `models.py` written; migration ready
- [x] Step 3 — `ai.py` complete (classify, remind, done/why responses, multi-turn chat via OpenRouter)
- [x] Step 4 — `handlers/topics.py` written
- [x] Step 5 — `handlers/group.py` complete (task routing)
- [x] Step 6 — `handlers/callbacks.py` complete (✅/❌ buttons + snooze reason)
- [x] Step 7 — `scheduler.py` complete (escalating reminders)
- [x] Step 8 — `handlers/private.py` complete (AI chat in Uzbek/English)
- [ ] Step 9 — Deploy to DigitalOcean

## Setup Sequence (first run)

1. `docker-compose up --build`
2. Run migration inside container:
   ```bash
   docker-compose exec bot bash
   alembic revision --autogenerate -m "create tasks table"
   alembic upgrade head
   exit
   ```
3. Run `/topics` inside each Telegram group topic → copy IDs into `.env`
4. `docker-compose restart bot`
