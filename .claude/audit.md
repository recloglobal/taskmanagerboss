# TaskManagerBoss — Project Audit

> **Audit date:** 2026-02-21
> **Auditor:** Antigravity AI
> **Scope:** Full codebase review — architecture, bugs, logic, docs, deployment readiness

---

## 📊 Summary Scorecard

| Dimension          | Rating   | Notes                                                    |
|--------------------|----------|----------------------------------------------------------|
| **Architecture**   | ⭐⭐⭐⭐⭐ | Clean separation, good patterns                          |
| **Documentation**  | ⭐⭐⭐⭐   | Excellent spec, but drifted from code (Gemini→OpenRouter) |
| **Bug-free**       | ⭐⭐      | Sync AI calls blocking event loop is a showstopper       |
| **Deployment-ready** | ⭐⭐    | No migration files, missing `TOPIC_GENERAL`              |
| **Error handling** | ⭐⭐⭐    | Scheduler has try/except, but handlers don't             |

---

## ✅ What's Good

1. **Clean architecture** — Separation of concerns is excellent: `config.py` for env vars, `database.py` for ORM setup, `ai.py` for all AI calls, one handler file per feature.
2. **Spec document is thorough** — `TASKMANAGERBOSS_SPEC.md` is highly detailed with step-by-step, copy-paste ready instructions and agent orchestration.
3. **Docker setup is solid** — Healthcheck on Postgres, `depends_on` with condition, restart policy. No common pitfalls.
4. **Safety practices** — `.env` in `.gitignore`, `.env.example` committed, `OWNER_ID` gating on handlers, AI call rate-limit awareness.
5. **Claude Code tooling** — Skills, commands, agents, settings — all properly structured under `.claude/`.

---

## 🔴 CRITICAL — Will crash or break at runtime

---

### BUG-1: `classify_task()` is sync but called in async handlers

**Severity:** 🔴 Critical
**Files:** `app/handlers/group.py:27`, `app/handlers/callbacks.py:29,55`, `app/handlers/private.py:24`
**Impact:** Blocks the entire async event loop. The bot will freeze for every user while waiting for the OpenRouter API to respond (1-5 seconds per call).

**Problem:**
```python
# app/handlers/group.py line 27
classification = classify_task(task_text)  # ← BLOCKING CALL in async handler
```

All `ai.py` functions (`classify_task`, `generate_done_response`, `generate_why_response`, `chat`) use the synchronous `openai` SDK which blocks the thread.

**How to fix:**

Option A — Wrap with `asyncio.to_thread()` (quickest fix, no library changes):

```python
# In every handler that calls an ai.py function, add:
import asyncio

# app/handlers/group.py
classification = await asyncio.to_thread(classify_task, task_text)

# app/handlers/callbacks.py
reply = await asyncio.to_thread(generate_done_response, {"text": task.text, "category": task.category})
reply = await asyncio.to_thread(generate_why_response, task_dict, reason)

# app/handlers/private.py
reply = await asyncio.to_thread(chat, user_id, user_text)

# app/scheduler.py
reminder_text = await asyncio.to_thread(generate_reminder, task_dict)
```

Option B — Make `ai.py` async natively (cleaner, more work):

```python
# Replace openai sync client with async client in ai.py
from openai import AsyncOpenAI

_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

async def _call(prompt: str) -> str:
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            response = await _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception:
            if model == FALLBACK_MODEL:
                raise
    return ""

# Then make ALL functions that call _call() async too:
async def classify_task(task_text: str) -> dict:
    ...
    raw = await _call(prompt)
    ...

# And update ALL callers to await them (no asyncio.to_thread needed)
```

**Recommendation:** Use Option A first (5-minute fix), then migrate to Option B when refactoring.

---

### BUG-2: `TOPIC_GENERAL` is missing from `.env`

**Severity:** 🔴 Critical
**Files:** `.env`, `.env.example`, `app/config.py:26`, `app/handlers/group.py:20`
**Impact:** No group message will EVER be processed. `TOPIC_GENERAL` defaults to `0`, and no Telegram thread has ID `0`, so the filter on line 20 of `group.py` will reject every message.

**Problem:**
```python
# config.py line 26
TOPIC_GENERAL = int(os.getenv("TOPIC_GENERAL") or 0)

# group.py line 20 — this check will NEVER pass if TOPIC_GENERAL is 0
if message.message_thread_id != TOPIC_GENERAL:
    return
```

**How to fix:**

1. Add `TOPIC_GENERAL=` to `.env`:
```env
TOPIC_GENERAL=
TOPIC_WORK=
TOPIC_PERSONAL=
TOPIC_HEALTH=
TOPIC_OTHER=
```

2. Add `TOPIC_GENERAL=` to `.env.example`:
```env
TOPIC_GENERAL=
TOPIC_WORK=
TOPIC_PERSONAL=
TOPIC_HEALTH=
TOPIC_OTHER=
```

3. After the bot is running, send `/topics` inside the #general topic in your Telegram group, copy the returned thread ID, and paste it into `.env`.

4. Restart the bot: `docker-compose restart bot`

---

### BUG-3: `reason_message_handler` won't work for group button presses

**Severity:** 🔴 Critical
**Files:** `app/main.py:43-46`, `app/handlers/callbacks.py:32-37`
**Impact:** When user presses ❌ in a **group topic**, the bot asks for a reason. But the `reason_message_handler` is registered only under `filters.ChatType.PRIVATE`. The user's reason reply in the group will be caught by `group_message_handler` instead and treated as a **new task**.

**Problem:**
```python
# main.py lines 43-46 — reason handler only listens to PRIVATE chat
app.add_handler(MessageHandler(
    filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
    reason_message_handler,
), group=1)
```

But the ❌ button is shown inside a group topic, so the user's reply will be in the group — not private chat.

**How to fix:**

Option A — Also register the reason handler for group messages with higher priority:

```python
# main.py — add a group-aware reason handler BEFORE the group_message_handler
app.add_handler(MessageHandler(
    (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & filters.TEXT & ~filters.COMMAND,
    reason_message_handler,
), group=0)  # Higher priority than group_message_handler
```

Then update `reason_message_handler` to properly check if a reason is pending:
```python
async def reason_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_id = context.user_data.get("pending_notyet_task_id")
    if not task_id:
        return  # Not awaiting a reason → let other handlers process
    # ... rest of handler
```

Option B — Use `ConversationHandler` from python-telegram-bot for a cleaner state machine:
```python
from telegram.ext import ConversationHandler

AWAITING_REASON = 1

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_callback_handler, pattern="^(done|notyet):")],
    states={
        AWAITING_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reason_message_handler)],
    },
    fallbacks=[],
    per_chat=True,
    per_user=True,
)
app.add_handler(conv_handler)
```

**Recommendation:** Option A is quicker. Option B is the "right" way to handle multi-step flows in python-telegram-bot.

---

## 🟡 SIGNIFICANT — Will cause incorrect behavior or confusion

---

### BUG-4: Spec/Code drift — Gemini → OpenRouter

**Severity:** 🟡 Significant
**Files:** `CLAUDE.md`, `TASKMANAGERBOSS_SPEC.md`, `app/ai.py`, `app/config.py`, `.env`, `requirements.txt`
**Impact:** All documentation references Gemini 2.5 Flash and `google-generativeai`, but the actual code uses OpenRouter with the `openai` SDK. Anyone reading the docs (including Claude Code) will give incorrect advice.

**What changed:**
| Aspect | Docs say | Code uses |
|--------|----------|-----------|
| AI Provider | Gemini 2.5 Flash | OpenRouter (Llama 3.3 70B + Gemini Flash fallback) |
| SDK | `google-generativeai` | `openai` (OpenAI-compatible) |
| Config var | `GEMINI_API_KEY` | `OPENROUTER_API_KEY` |
| Rate limits | 10 RPM / 250 RPD | OpenRouter limits (varies by model) |

**How to fix:**

Update the following files to reflect the current OpenRouter setup:

1. **`CLAUDE.md`** — Replace all mentions of "Gemini" with "OpenRouter (Llama 3.3 70B primary, Gemini Flash fallback)". Replace `GEMINI_API_KEY` with `OPENROUTER_API_KEY`.

2. **`TASKMANAGERBOSS_SPEC.md`** — Same replacements throughout the spec. Update the `requirements.txt` section to show `openai>=1.54.0` instead of `google-generativeai==0.7.2`.

3. **`.claude/agents/ai-agent.md`** — Update the stack description from Gemini to OpenRouter.

4. **`.claude/skills/` relevant files** — Update any AI-related skill references.

---

### BUG-5: No migration files exist

**Severity:** 🟡 Significant
**Files:** `alembic/versions/` (empty), `CLAUDE.md:95`
**Impact:** The bot will crash on first DB query because the `tasks` table doesn't exist. `CLAUDE.md` says Step 2 is ✅ done but the migration was never generated.

**How to fix:**

```bash
# 1. Start containers
docker-compose up --build -d

# 2. Shell into bot container
docker-compose exec bot bash

# 3. Generate migration
alembic revision --autogenerate -m "create tasks table"

# 4. Apply migration
alembic upgrade head

# 5. Verify
exit
docker-compose exec db psql -U taskbot -d taskbot_db -c "\dt"
# Should show: tasks table
```

After running this, the `alembic/versions/` directory will contain the migration file. **Commit it to git** so it's available on deployment.

---

### BUG-6: `datetime.utcnow()` is deprecated

**Severity:** 🟡 Significant
**Files:** `app/scheduler.py:16`
**Impact:** Deprecated since Python 3.12. Returns a naive datetime without timezone info, which can cause subtle bugs when comparing with timezone-aware datetimes from the database.

**Problem:**
```python
now = datetime.utcnow()  # ← deprecated, returns naive datetime
```

**How to fix:**
```python
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
```

Also update the `Task` model's `created_at` to use timezone-aware timestamps if you want consistency:
```python
# models.py
from sqlalchemy import func
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
)
```

---

### BUG-7: Double `overdue_count` increment

**Severity:** 🟡 Significant
**Files:** `app/handlers/callbacks.py:54`, `app/scheduler.py:70`
**Impact:** `overdue_count` is incremented in **two separate places**, causing the boss tone to escalate **twice as fast** as intended.

**Where it's incremented:**
1. `callbacks.py:54` — When user presses ❌ and gives a reason
2. `scheduler.py:70` — Every time a reminder is sent

If a user gets a reminder (count +1) and then presses ❌ (count +1 again), the count jumps by 2 instead of 1 per cycle.

**How to fix:**

Remove the increment from `callbacks.py` — let only the scheduler control the escalation:

```python
# callbacks.py — REMOVE this line:
task.overdue_count += 1  # ← DELETE THIS

# Keep only the scheduler.py increment:
t.overdue_count += 1  # ← This is the single source of truth
```

The `snooze_reason` in callbacks is still valuable — keep that.

---

## 🟠 DESIGN — Logic issues that should be addressed

---

### DESIGN-1: Scheduler opens N separate DB sessions

**Severity:** 🟠 Design
**Files:** `app/scheduler.py:18-22, 65-71`
**Impact:** Opens one session to fetch all tasks, then opens a **new session per task** to update `reminded_at` and `overdue_count`. For 50 pending tasks, that's 51 DB sessions.

**How to fix:**

Reuse one session for both read and update:
```python
async def send_reminders(bot: Bot):
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        result = await session.execute(
            select(Task).where(Task.status == "pending")
        )
        tasks = result.scalars().all()

        for task in tasks:
            should_remind = False
            # ... same reminder logic ...

            if not should_remind:
                continue

            task_dict = {
                "text": task.text,
                "category": task.category,
                "overdue_count": task.overdue_count,
            }

            reminder_text = await asyncio.to_thread(generate_reminder, task_dict)

            keyboard = InlineKeyboardMarkup([...])

            try:
                await bot.send_message(
                    chat_id=task.group_id,
                    message_thread_id=task.topic_id,
                    text=reminder_text,
                    reply_markup=keyboard,
                )
                # Update in the SAME session
                task.reminded_at = now
                task.overdue_count += 1

            except Exception as e:
                logger.error(f"Failed to send reminder for task {task.id}: {e}")

        # Single commit for all updates
        await session.commit()
```

---

### DESIGN-2: `_histories` dict has no size limit

**Severity:** 🟠 Design
**Files:** `app/ai.py:17`
**Impact:** The conversation history dict grows unboundedly per user. While only last 10 turns are used for context, the full list is never trimmed. Over weeks of use, this could consume significant memory.

**How to fix:**

Trim the history list after each append:
```python
def chat(user_id: int, message: str) -> str:
    history = _histories.setdefault(user_id, [])
    # ... existing logic ...
    history.append({"user": message, "bot": reply})

    # Keep only last 20 turns in memory (only 10 used for context)
    if len(history) > 20:
        _histories[user_id] = history[-20:]

    return reply
```

---

### DESIGN-3: No error handling in handlers

**Severity:** 🟠 Design
**Files:** All handler files
**Impact:** If any Telegram API call or AI call fails, the exception will propagate unhandled. python-telegram-bot catches it at the top level and logs it, but the user gets no feedback.

**How to fix:**

Add try/except blocks in handlers:
```python
async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # ... existing handler logic ...
    except Exception as e:
        logger.error(f"Error processing group message: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
```

Or use python-telegram-bot's built-in error handler:
```python
# main.py
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

app.add_error_handler(error_handler)
```

---

## 🔵 MINOR — Polish and cleanup

---

### MINOR-1: Unused import in `group.py`

**File:** `app/handlers/group.py:4`
**Issue:** `from sqlalchemy import select` is imported but never used.
**Fix:** Remove line 4.

---

### MINOR-2: Typo in `topics.py`

**File:** `app/handlers/topics.py:21`
**Issue:** `"eki"` should be `"yoki"` (Uzbek for "or").
**Fix:**
```python
# Change:
f"Bu asosiy guruh eki #general mavzusi.\n"
# To:
f"Bu asosiy guruh yoki #general mavzusi.\n"
```

---

### MINOR-3: No logging in handlers

**Files:** All handler files
**Issue:** None of the handlers log anything. When debugging in production, there's no visibility into what the bot is doing.
**Fix:** Add `logger = logging.getLogger(__name__)` and `logger.info()` calls:
```python
import logging
logger = logging.getLogger(__name__)

async def group_message_handler(update, context):
    logger.info(f"Received task from user {update.message.from_user.id}")
    # ...
    logger.info(f"Task #{task_id} classified as {category}, routed to topic {destination_topic}")
```

---

### MINOR-4: `python-conventions` skill directory is empty

**File:** `.claude/skills/python-conventions/`
**Issue:** The directory exists but contains no `SKILL.md` file (0 children).
**Fix:** Create `.claude/skills/python-conventions/SKILL.md` with the content from `CLAUDE_CODE_SETUP.md` Part 3 Skill 1.

---

### MINOR-5: `.env.example` missing `TOPIC_GENERAL`

**File:** `.env.example`
**Issue:** Lists `TOPIC_WORK`, `TOPIC_PERSONAL`, `TOPIC_HEALTH`, `TOPIC_OTHER` but not `TOPIC_GENERAL`.
**Fix:** Add `TOPIC_GENERAL=` to `.env.example`.

---

### MINOR-6: Build status in `CLAUDE.md` is outdated

**File:** `CLAUDE.md:94-102`
**Issue:** Shows Steps 1-8 as ✅ done, but Step 2 (migration) hasn't actually been run yet, and the code has diverged from the spec (OpenRouter vs Gemini).
**Fix:** Update the checklist to accurately reflect current state.

---

## 🎯 Recommended Fix Priority

| Priority | Bug ID  | Description                                  | Effort   |
|----------|---------|----------------------------------------------|----------|
| 1        | BUG-2   | Add `TOPIC_GENERAL` to `.env`                | 1 min    |
| 2        | BUG-5   | Run Alembic migration                        | 5 min    |
| 3        | BUG-1   | Wrap AI calls with `asyncio.to_thread()`     | 10 min   |
| 4        | BUG-7   | Remove double `overdue_count` increment      | 2 min    |
| 5        | BUG-3   | Fix reason handler for group context         | 15 min   |
| 6        | BUG-4   | Update all docs Gemini → OpenRouter          | 20 min   |
| 7        | BUG-6   | Replace `datetime.utcnow()`                  | 2 min    |
| 8        | DESIGN-1| Reuse single DB session in scheduler         | 10 min   |
| 9        | DESIGN-3| Add error handling to all handlers            | 15 min   |
| 10       | DESIGN-2| Trim `_histories` dict                        | 2 min    |
| 11       | MINOR-* | All minor fixes                               | 10 min   |

**Total estimated effort: ~1.5 hours**

---

## ✅ Checklist — Mark off as you fix

- [ ] BUG-1 — Async AI calls
- [ ] BUG-2 — `TOPIC_GENERAL` in `.env`
- [ ] BUG-3 — Reason handler group/private mismatch
- [ ] BUG-4 — Update docs to OpenRouter
- [ ] BUG-5 — Run Alembic migration
- [ ] BUG-6 — Replace `datetime.utcnow()`
- [ ] BUG-7 — Fix double `overdue_count`
- [ ] DESIGN-1 — Single DB session in scheduler
- [ ] DESIGN-2 — Trim `_histories`
- [ ] DESIGN-3 — Error handling in handlers
- [ ] MINOR-1 — Remove unused import
- [ ] MINOR-2 — Fix typo "eki" → "yoki"
- [ ] MINOR-3 — Add logging to handlers
- [ ] MINOR-4 — Create python-conventions SKILL.md
- [ ] MINOR-5 — Add `TOPIC_GENERAL` to `.env.example`
- [ ] MINOR-6 — Update build status in CLAUDE.md
