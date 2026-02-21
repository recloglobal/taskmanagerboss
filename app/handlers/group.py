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
