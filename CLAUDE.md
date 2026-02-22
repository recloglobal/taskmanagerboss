# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A Telegram bot ("TaskManagerBoss") that acts like a strict boss for personal task management.
- Reads tasks posted in a Telegram group's `#general` topic
- Classifies them with Gemini AI into categories: `work`, `personal`, `health`, `other`
- Routes each task into the matching group topic
- Sends escalating reminders until tasks are marked done
- Private chat mode: full AI assistant with boss personality in Uzbek/English

Full spec: `TASKMANAGERBOSS_SPEC.md` | Audit log: `.claude/audit.md`

## Stack

- Python 3.11, python-telegram-bot v21 (async)
- **Google Gemini** via `google-genai` SDK: `gemini-2.0-flash-lite` → `gemini-2.0-flash` fallback
- PostgreSQL 16, SQLAlchemy 2.0 async (`asyncpg`), Alembic migrations
- APScheduler 3.x (`AsyncIOScheduler` — required for async bot)
- Docker + docker-compose

## Key Commands

```bash
# Build and start
docker-compose up --build          # Full rebuild
docker-compose restart bot         # Restart bot only after Python changes

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
app/ai.py            ← All AI calls via Gemini: classify_task(), generate_reminder(),
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
- Tasks **without** due date: remind every 48 hours since last reminder
- `overdue_count` (incremented by scheduler only) drives tone: 0=firm, 1=impatient, 2=sarcastic, 3+=aggressive caps

**AI pattern:** `ai.py` exposes only sync functions. All callers wrap them in `asyncio.to_thread()` to avoid blocking the event loop. `_call()` handles single-turn prompts; `_chat_call()` manages multi-turn chat with `client.chats.create(history=...)`. Fallback: if `gemini-2.0-flash-lite` fails or rate-limits (429), retries once after 35s then falls back to `gemini-2.0-flash`.

**Conversation history** for private chat is stored in `ai.py::_histories` dict (last 20 turns kept, last 10 sent to model as `types.Content` objects) — lost on restart.

**Snooze flow:** Pressing ❌ sets `context.user_data["pending_notyet_task_id"]` → `reason_message_handler` in `callbacks.py` picks it up (handler group=1, before `private_message_handler` in group=2). `overdue_count` is NOT incremented in `callbacks.py` — only the scheduler does this.

## Critical Rules

- **All DB calls must be async:** `async with SessionLocal() as session:`
- **Never run Alembic outside the bot container** — it needs the container's Python path and env
- **All AI calls must go through `app/ai.py`** — never call Gemini directly from handlers
- **Wrap all AI calls in `asyncio.to_thread()`** — they are synchronous and will block the event loop
- **`AsyncIOScheduler`** (not `BackgroundScheduler`) is required because the bot is async
- **Handler registration order in `main.py` matters** — callbacks before group/private filters; `reason_message_handler` (group=1) before `private_message_handler` (group=2)
- **Topics cannot be created via the API** — pre-create them in Telegram, then get IDs via `/topics`
- **Bot must be group admin** with Send Messages permission
- **`DATABASE_URL_SYNC`** exists in `config.py` for Alembic (uses `psycopg2`, not `asyncpg`)
- **`TOPIC_GENERAL=0`** means "accept all group messages from owner" — set it to a real thread ID to restrict to #general only

## Environment Variables

See `.env.example` for all required vars. Key ones:
- `BOT_TOKEN`, `GEMINI_API_KEY`, `OWNER_ID`
- `TOPIC_GENERAL`, `TOPIC_WORK`, `TOPIC_PERSONAL`, `TOPIC_HEALTH`, `TOPIC_OTHER` — get these by running `/topics` inside each group topic after bot starts
- `DATABASE_URL` is constructed in `config.py` from the `POSTGRES_*` vars (never set `DATABASE_URL` directly in `.env`)

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

## Current State

- [x] Docker + postgres + `/start` working
- [x] `config.py`, `database.py`, `models.py` written
- [x] `ai.py` complete (Gemini via `google-genai` SDK, fallback chain, multi-turn chat)
- [x] All handlers complete (group routing, callbacks, private chat)
- [x] `scheduler.py` complete (escalating reminders)
- [ ] Alembic migration not yet generated/applied — run Step 2 above
- [ ] `TOPIC_GENERAL` in `.env` not yet filled — run Step 3 above
- [ ] Deploy to DigitalOcean
