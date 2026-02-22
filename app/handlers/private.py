import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from config import OWNER_ID
from ai import chat, clear_history
from database import SessionLocal
from models import Task

logger = logging.getLogger(__name__)


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

    logger.info(f"Private chat from {user_id}: {user_text[:50]}...")

    # DB Context Injection: Fetch active tasks
    pending_tasks = []
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Task)
                .where(Task.owner_id == user_id)
                .where(Task.status == "pending")
                .order_by(Task.created_at.desc())
                .limit(5)
            )
            tasks = result.scalars().all()
            pending_tasks = [{"text": t.text, "category": t.category} for t in tasks]
    except Exception as e:
        logger.error(f"Failed to fetch tasks for DB context: {e}")

    try:
        reply = await asyncio.to_thread(chat, user_id, user_text, pending_tasks)
    except Exception as e:
        logger.error(f"AI chat failed: {e}")
        reply = "⚠️ AI bilan bog'lanishda xatolik. Qaytadan urinib ko'ring."

    await message.reply_text(reply)
