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
