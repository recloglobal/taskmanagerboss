# Claude Code Setup Guide — TaskManagerBoss
> How to set up Claude Code with the right file structure, skills, and persistent memory
> so agents can work faster, smarter, and never forget context between sessions.

---

## 📖 What This Guide Covers

1. **File structure** — where everything lives for Claude Code to work properly
2. **CLAUDE.md** — the "always-on memory card" Claude reads every session
3. **Skills** — reusable instruction packs Claude uses automatically
4. **Memory (claude-mem)** — persistent memory across sessions so Claude never forgets
5. **Agent orchestration** — how to run parallel agents efficiently

---

## 🧠 Understanding the Building Blocks

Before setting anything up, here's what each piece does:

| Tool | What it is | Analogy |
|---|---|---|
| `CLAUDE.md` | Always-loaded project context | Sticky note on Claude's desk every session |
| `Skills` | Reusable instruction packs in `.claude/skills/` | Claude's trained reflexes |
| `Slash commands` | One-off prompts you invoke with `/command` | Keyboard shortcuts |
| `Agents` | Specialists with their own context window | Hiring a contractor for one job |
| `claude-mem` | Auto-captures sessions, injects context next time | Claude's long-term memory |

---

## 📁 Part 1 — Full File Structure

This is the complete structure for `taskmanagerboss/` with Claude Code support:

```
taskmanagerboss/
│
├── CLAUDE.md                          ← Project memory — Claude reads this every session
├── .mcp.json                          ← MCP server config (memory, tools)
│
├── .claude/
│   ├── settings.json                  ← Hooks, permissions, environment
│   ├── settings.local.json            ← Your personal overrides (gitignored)
│   ├── .gitignore                     ← Ignore local settings
│   │
│   ├── skills/                        ← Auto-discovered skills
│   │   ├── python-conventions/
│   │   │   └── SKILL.md              ← Python/async patterns for this project
│   │   ├── docker-workflow/
│   │   │   └── SKILL.md              ← Docker commands and workflows
│   │   └── telegram-bot/
│   │       └── SKILL.md              ← Telegram bot patterns and gotchas
│   │
│   ├── commands/                      ← Slash commands you invoke manually
│   │   ├── build.md                  ← /build — rebuild docker containers
│   │   ├── test-task.md              ← /test-task — test full task flow
│   │   ├── logs.md                   ← /logs — view bot and db logs
│   │   └── deploy.md                 ← /deploy — deploy to DigitalOcean
│   │
│   └── agents/                       ← Specialist subagents
│       ├── db-agent.md               ← Database specialist
│       ├── ai-agent.md               ← Gemini/AI layer specialist
│       └── infra-agent.md            ← Docker/infra specialist
│
├── app/                               ← Your bot source code
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── ai.py
│   ├── scheduler.py
│   └── handlers/
│       ├── __init__.py
│       ├── start.py
│       ├── topics.py
│       ├── group.py
│       ├── callbacks.py
│       └── private.py
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                               ← Your secrets (gitignored)
├── .env.example                       ← Safe template (committed)
└── .gitignore
```

---

## 📝 Part 2 — CLAUDE.md (Project Memory)

This file is loaded **automatically every single session**. Keep it focused and accurate.

Create `taskmanagerboss/CLAUDE.md`:

```markdown
# TaskManagerBoss — Project Memory

## What This Project Is
A Telegram bot that manages tasks like a strict boss.
- Reads tasks from #general group topic
- Classifies them with Gemini 2.5 Flash AI
- Routes to correct topic: #work / #personal / #health / #other
- Reminds with escalating tone until tasks are done

## Stack
- Python 3.11
- python-telegram-bot v21 (async)
- Gemini 2.5 Flash (free tier, 10 RPM / 250 RPD)
- PostgreSQL 16 via SQLAlchemy 2.0 async + Alembic
- APScheduler 3.x for reminders
- Docker + docker-compose (local and DigitalOcean)

## Key Commands
```bash
docker-compose up --build          # Start everything
docker-compose restart bot         # Restart bot only (after code changes)
docker-compose logs -f bot         # Watch bot logs
docker-compose exec bot bash       # Shell into bot container
docker-compose exec db psql -U taskbot -d taskbot_db   # Postgres shell
alembic revision --autogenerate -m "description"       # New migration
alembic upgrade head               # Apply migrations
```

## Project Structure
- `app/main.py` — entry point, wires all handlers + starts scheduler
- `app/config.py` — all env vars loaded here
- `app/database.py` — SQLAlchemy async engine
- `app/models.py` — Task table
- `app/ai.py` — all Gemini calls (classify, remind, chat)
- `app/scheduler.py` — APScheduler reminder engine
- `app/handlers/` — one file per feature

## Important Rules
- NEVER run migrations outside the bot container (`docker-compose exec bot bash`)
- NEVER commit `.env` — use `.env.example` as template
- All database calls must be async — use `async with SessionLocal() as session:`
- Topic IDs come from `.env` — run `/topics` command inside each group topic to get IDs
- Bot must be GROUP ADMIN with Send Messages permission

## Current Build Status
- [x] Step 1 — Docker + postgres + /start working
- [ ] Step 2 — Database models + Alembic migration
- [ ] Step 3 — Gemini AI layer
- [ ] Step 4 — /topics command
- [ ] Step 5 — Group listener + task routing
- [ ] Step 6 — Callbacks (YES/NO buttons)
- [ ] Step 7 — Scheduler + reminders
- [ ] Step 8 — Private chat AI
- [ ] Step 9 — Deploy to DigitalOcean

## Known Issues / Decisions
- Telegram cannot create topics via API — topics must be pre-created manually
- Gemini free tier: 10 RPM max — do NOT call Gemini in loops
- APScheduler must use AsyncIOScheduler (not BackgroundScheduler) for async bot
```

> **Tip:** Update the `## Current Build Status` section as you complete each step.
> This way Claude always knows exactly where you are.

---

## 🛠️ Part 3 — Skills

Skills are stored in `.claude/skills/` and are auto-discovered — Claude decides when to use them based on the description.

Each skill is a folder with a `SKILL.md` file inside.

### Skill 1 — Python Conventions

`.claude/skills/python-conventions/SKILL.md`:

```markdown
---
name: python-conventions
description: Python coding patterns for this project. Use when writing any Python code, async functions, SQLAlchemy queries, or database operations.
---

# Python Conventions for TaskManagerBoss

## Async Rules
- ALL database calls must use `async with SessionLocal() as session:`
- ALL handlers must be `async def`
- Use `await` for every database operation
- Never use sync SQLAlchemy in async context

## SQLAlchemy Pattern
```python
# Correct pattern for queries
async with SessionLocal() as session:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = "done"
        await session.commit()
```

## Error Handling
- Always wrap Telegram API calls in try/except
- Log errors with: `logger.error(f"Description: {e}")`
- Never let exceptions crash the bot silently

## Imports Order
1. Standard library
2. Third party (telegram, sqlalchemy, google)
3. Local (config, database, models, ai)

## Environment Variables
- Always load from `config.py` — never use `os.getenv()` directly in handlers
```

---

### Skill 2 — Docker Workflow

`.claude/skills/docker-workflow/SKILL.md`:

```markdown
---
name: docker-workflow
description: Docker commands and workflows for this project. Use when working with containers, running migrations, checking logs, or debugging container issues.
---

# Docker Workflow

## Basic Commands
```bash
docker-compose up --build          # Full rebuild and start
docker-compose up -d               # Start in background
docker-compose down                # Stop everything
docker-compose restart bot         # Restart bot only (fastest for code changes)
docker-compose logs -f bot         # Follow bot logs
docker-compose logs -f db          # Follow postgres logs
```

## Run Migrations (ALWAYS inside container)
```bash
docker-compose exec bot bash
alembic revision --autogenerate -m "your description"
alembic upgrade head
exit
```

## Database Inspection
```bash
docker-compose exec db psql -U taskbot -d taskbot_db
\dt                                # List all tables
SELECT * FROM tasks;               # View all tasks
\q                                 # Quit
```

## After Code Changes
```bash
docker-compose restart bot         # If only Python files changed
docker-compose up --build          # If requirements.txt changed
```

## Common Issues
- "Connection refused" to postgres → wait for healthcheck, postgres takes ~5s to start
- "Module not found" → rebuild with `docker-compose up --build`
- "Port already in use" → `docker-compose down` first
```

---

### Skill 3 — Telegram Bot Patterns

`.claude/skills/telegram-bot/SKILL.md`:

```markdown
---
name: telegram-bot
description: Telegram bot patterns and gotchas for python-telegram-bot v21. Use when writing handlers, filters, inline keyboards, or working with group topics.
---

# Telegram Bot Patterns (PTB v21)

## Handler Registration Order Matters
```python
# In main.py — order is priority
app.add_handler(CommandHandler("start", start_handler))         # Commands first
app.add_handler(CallbackQueryHandler(callback, pattern="..."))  # Callbacks second
app.add_handler(MessageHandler(filters.Chat(...), group_handler))  # Group third
app.add_handler(MessageHandler(filters.ChatType.PRIVATE, private_handler), group=2)
```

## Group Topics Filter
```python
# Only process messages from #general topic
if message.message_thread_id != TOPIC_GENERAL:
    return
```

## Sending to a Specific Topic
```python
await context.bot.send_message(
    chat_id=group_id,
    message_thread_id=topic_id,   # This routes to the topic
    text="Your message",
    parse_mode="Markdown",
)
```

## Inline Keyboard
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Done", callback_data="done:123"),
        InlineKeyboardButton("❌ Not yet", callback_data="notyet:123"),
    ]
])
```

## Callback Handler Pattern
```python
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()                    # Always answer first
    data = query.data                       # "done:123"
    action, task_id = data.split(":")
```

## Key Gotchas
- Bots CANNOT create topics — only send messages INTO existing topics
- `message_thread_id` is the topic ID in supergroups with topics enabled
- Bot must be admin with "Send Messages" permission in group
- `Update.ALL_TYPES` needed in `run_polling()` to receive all update types
```

---

## ⚡ Part 4 — Slash Commands

Slash commands are prompts you invoke manually with `/command` in the terminal.

### `/build` command

`.claude/commands/build.md`:

```markdown
Rebuild and restart the Docker containers for this project.

Run: `docker-compose down && docker-compose up --build`

Watch the logs and confirm:
1. `db-1 | database system is ready to accept connections`
2. `bot-1 | Bot is running...`
3. `bot-1 | Application started`

If there are errors, diagnose and fix them.
```

### `/logs` command

`.claude/commands/logs.md`:

```markdown
Show the recent logs from the bot container.

Run: `docker-compose logs --tail=50 bot`

Look for any ERROR or WARNING lines and explain what they mean.
```

### `/test-task` command

`.claude/commands/test-task.md`:

```markdown
Test the full task flow end to end.

Steps:
1. Check that all containers are running: `docker-compose ps`
2. Check the tasks table is empty or show current state: `docker-compose exec db psql -U taskbot -d taskbot_db -c "SELECT id, text, category, status FROM tasks ORDER BY created_at DESC LIMIT 5;"`
3. Remind me to send a test message to #general in the Telegram group
4. After I confirm I sent it, check if the task appeared in the database
5. Report the result
```

### `/deploy` command

`.claude/commands/deploy.md`:

```markdown
Deploy the latest code to DigitalOcean VPS.

Pre-flight checklist:
1. Confirm all changes are committed: `git status`
2. Confirm tests pass (if any): `docker-compose exec bot python -m pytest` (skip if no tests yet)
3. Push to GitHub: `git push origin main`

Then provide the SSH deployment commands for the user to run on their VPS:
```bash
ssh root@YOUR_VPS_IP
cd taskmanagerboss
git pull origin main
docker-compose down
docker-compose up --build -d
docker-compose logs -f bot
```

Remind them to NEVER copy the .env file via git — it must be manually placed on the server.
```

---

## 🤖 Part 5 — Subagents

Subagents are specialists with their own context window for delegated tasks — they keep your main context clean.

### Database Agent

`.claude/agents/db-agent.md`:

```markdown
---
name: db-agent
description: PostgreSQL and SQLAlchemy specialist. Use for database schema changes, writing queries, running migrations, or debugging database connection issues.
---

You are a database specialist for the TaskManagerBoss project.

Stack: PostgreSQL 16, SQLAlchemy 2.0 async, Alembic migrations, asyncpg driver.

Your responsibilities:
- Write async SQLAlchemy queries
- Create and run Alembic migrations inside the Docker container
- Debug database connection issues
- Optimize queries if needed

Always use async patterns:
```python
async with SessionLocal() as session:
    result = await session.execute(select(Task).where(...))
```

Migrations must always be run inside the bot container:
```bash
docker-compose exec bot bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```
```

### AI Agent

`.claude/agents/ai-agent.md`:

```markdown
---
name: ai-agent
description: Gemini AI specialist. Use for modifying AI prompts, adjusting task classification, changing reminder tone, or debugging Gemini API calls.
---

You are an AI/prompt specialist for the TaskManagerBoss project.

Stack: Google Gemini 2.5 Flash, google-generativeai Python SDK.
Free tier limits: 10 RPM, 250 RPD — be conservative with API calls.

Your responsibilities:
- Write and improve prompts in `app/ai.py`
- Ensure prompts work in both Uzbek and English
- Keep responses concise to save tokens
- Handle JSON parsing from Gemini responses safely

All Gemini calls go through `app/ai.py`. Never call the API directly from handlers.

Rate limit safety: Never call Gemini in loops. One call per user action maximum.
```

---

## 🧠 Part 6 — Persistent Memory with claude-mem

claude-mem is a 1-line-install memory system for Claude Code that prevents context loss between sessions. It uses vector storage and MCP integration to automatically compress conversations and inject relevant context at startup.

### Install claude-mem

```bash
npm install -g claude-mem && claude-mem install
```

That's it. It automatically:
- Captures everything Claude does during sessions
- Compresses it with AI
- Injects relevant context at the start of future sessions
- Stores everything locally in `~/.claude-mem/` — no external servers

### How it works in practice

Without memory (before):
> Every new session: "Here's my project, it's a Telegram bot, I use Python, PostgreSQL..."
> Claude explores files for 10 minutes before it can help.

With claude-mem (after):
> Claude already knows: your stack, what you built last session, what broke, what decisions you made.
> Jumps straight into working.

### Verify it's running

```bash
claude-mem status
```

You should see the worker running. It runs in the background automatically.

### Manual memory save

If something important happens that you want Claude to remember:

```
# Remember: We decided to use APScheduler AsyncIOScheduler not BackgroundScheduler because the bot is async
```

The `#` prefix tells Claude to save it to memory immediately.

---

## 🔧 Part 7 — .claude/settings.json

This file configures hooks (automatic actions before/after Claude does things).

`.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Running bash command...'",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'File edited. Remember to restart bot if needed: docker-compose restart bot'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

`.claude/settings.local.json` (your personal overrides, gitignored):

```json
{
  "env": {
    "ANTHROPIC_MODEL": "claude-sonnet-4-6"
  }
}
```

`.claude/.gitignore`:
```
settings.local.json
```

---

## 🚀 Part 8 — How to Use All of This with Claude Code

### Starting a session

```bash
cd taskmanagerboss
claude
```

Claude will automatically load:
- `CLAUDE.md` → knows your full project context
- Skills → knows Python patterns, Docker commands, Telegram gotchas
- claude-mem → injects memory from previous sessions

### Running parallel agents (fastest way to build)

```bash
# Terminal 1 — Database work
claude "Use the db-agent to create models.py and run the Alembic migration for the tasks table"

# Terminal 2 — AI layer (simultaneously)
claude "Use the ai-agent to build app/ai.py with all Gemini functions: classify_task, generate_reminder, chat"

# Terminal 3 — Handlers (after agents 1+2 finish)
claude "Build all handlers in app/handlers/ following the spec in CLAUDE.md"
```

### Using slash commands

Inside a Claude Code session:
```
/build         → rebuilds docker
/logs          → shows recent logs
/test-task     → walks through testing the full flow
/deploy        → helps deploy to DigitalOcean
```

### Telling Claude to remember something

```
# The Gemini API sometimes returns JSON with extra whitespace — always strip() before parsing
# PostgreSQL container takes ~5 seconds to be ready — healthcheck handles this automatically
```

---

## ✅ Setup Checklist

```
Global (one-time setup on your machine):
[ ] npm install -g claude-mem && claude-mem install

Project files to create:
[ ] CLAUDE.md
[ ] .mcp.json
[ ] .claude/settings.json
[ ] .claude/settings.local.json
[ ] .claude/.gitignore
[ ] .claude/skills/python-conventions/SKILL.md
[ ] .claude/skills/docker-workflow/SKILL.md
[ ] .claude/skills/telegram-bot/SKILL.md
[ ] .claude/commands/build.md
[ ] .claude/commands/logs.md
[ ] .claude/commands/test-task.md
[ ] .claude/commands/deploy.md
[ ] .claude/agents/db-agent.md
[ ] .claude/agents/ai-agent.md
[ ] .claude/agents/infra-agent.md

Verify everything works:
[ ] Run: claude (inside taskmanagerboss/)
[ ] Claude reads CLAUDE.md on startup
[ ] /build command works
[ ] claude-mem status shows running
[ ] Skills appear when relevant (try asking about Docker or Python)
```

---

## 💡 Tips

- **Update CLAUDE.md as you build** — check off completed steps, add new decisions, note bugs you fixed
- **Keep skills under 500 lines** — focused skills work better than giant ones
- **Use `#` prefix for instant memory** — any important decision, save it immediately
- **One agent per context** — don't try to do database + AI + handlers in one session, use separate agents
- **`/compact` when context gets large** — claude-mem will save the session before compacting
