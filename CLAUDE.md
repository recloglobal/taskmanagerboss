# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A Telegram bot ("TaskManagerBoss") that acts like a strict boss for personal task management.
- Reads tasks posted in a Telegram group's `#general` topic
- Classifies them with Gemini 2.5 Flash AI into categories: `work`, `personal`, `health`, `other`
- Routes each task into the matching group topic
- Sends escalating reminders until tasks are marked done
- Private chat mode: full Gemini AI assistant in Uzbek/English

Full spec: `TASKMANAGERBOSS_SPEC.md` | Claude Code setup guide: `CLAUDE_CODE_SETUP.md`

## Stack

- Python 3.11, python-telegram-bot v21 (async)
- Gemini 2.5 Flash via `google-generativeai` (free tier: 10 RPM / 250 RPD)
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
app/ai.py            ← All Gemini calls: classify_task(), generate_reminder(), chat()
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

**Reminder flow:** Scheduler runs `send_reminders()` every 60 min → queries all `pending` tasks → calls `generate_reminder()` → tone escalates via `overdue_count` (0=firm, 1-2=sarcastic, 3+=aggressive boss).

**Conversation history** for private chat is stored in-memory in `ai.py::_histories` dict — lost on restart.

## Critical Rules

- **All DB calls must be async:** `async with SessionLocal() as session:`
- **Never run Alembic outside the bot container** — it needs container's Python path and env
- **Never call Gemini in loops** — rate limit is 10 RPM; one call per user action max
- **Topics cannot be created via the API** — they must be pre-created in Telegram, then IDs captured via `/topics` command
- **Bot must be group admin** with Send Messages permission
- **`AsyncIOScheduler`** (not `BackgroundScheduler`) is required because the bot is async
- Handler registration order in `main.py` matters — callbacks before group/private filters

## Environment Variables

See `.env.example` for all required vars. Key ones:
- `BOT_TOKEN`, `GEMINI_API_KEY`, `OWNER_ID`
- `TOPIC_GENERAL`, `TOPIC_WORK`, `TOPIC_PERSONAL`, `TOPIC_HEALTH`, `TOPIC_OTHER` — get these by running `/topics` inside each group topic after bot starts
- `DATABASE_URL` is constructed in `config.py` from the `POSTGRES_*` vars

## Current Build Status

- [x] Step 1 — Docker + postgres + `/start` working
- [x] Step 2 — `config.py`, `database.py`, `models.py` written; **run migration next** (see commands above)
- [x] Step 3 — `ai.py` complete (classify, remind, chat, done/why responses)
- [x] Step 4 — `handlers/topics.py` written; **run `/topics` in each group topic to get IDs, then fill `.env`**
- [x] Step 5 — `handlers/group.py` complete (task routing)
- [x] Step 6 — `handlers/callbacks.py` complete (✅/❌ buttons + snooze reason)
- [x] Step 7 — `scheduler.py` complete (escalating reminders every 60 min)
- [x] Step 8 — `handlers/private.py` complete (AI chat in Uzbek/English)
- [ ] Step 9 — Deploy to DigitalOcean

## Next Steps Before Bot Works

1. Build containers: `docker-compose up --build`
2. Run the Alembic migration inside container:
   ```bash
   docker-compose exec bot bash
   alembic revision --autogenerate -m "create tasks table"
   alembic upgrade head
   exit
   ```
3. Run `/topics` inside each Telegram group topic → copy IDs into `.env`
4. Restart bot: `docker-compose restart bot`
