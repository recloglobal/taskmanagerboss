import asyncio
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from sqlalchemy import select

from database import SessionLocal
from models import Task
from ai import generate_done_response, generate_why_response

logger = logging.getLogger(__name__)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # "done:123" or "notyet:123"
    action, task_id_str = data.split(":")
    task_id = int(task_id_str)

    logger.info(f"Button callback: action={action}, task_id={task_id}")

    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            await query.edit_message_text("❌ Vazifa topilmadi.")
            return

        if action == "done":
            task.status = "done"
            await session.commit()

            try:
                reply = await asyncio.to_thread(
                    generate_done_response,
                    {"text": task.text, "category": task.category}
                )
            except Exception as e:
                logger.error(f"AI done response failed: {e}")
                reply = "Yaxshi, bajarildi! ✅"

            await query.edit_message_text(f"✅ *Bajarildi!*\n\n{reply}", parse_mode="Markdown")
            logger.info(f"Task #{task_id} marked as done")

        elif action == "notyet":
            # Ask for reason
            context.user_data[f"awaiting_reason_{task_id}"] = True
            await query.edit_message_text(
                "❌ Nima uchun bajarilmadi? Sababini yozing:",
            )
            context.user_data["pending_notyet_task_id"] = task_id
            logger.info(f"Task #{task_id}: awaiting reason from user")

        elif action == "doing_now":
            from sqlalchemy import func
            # Give them a temporary grace period on reminders by resetting reminded_at
            task.reminded_at = func.now()
            await session.commit()
            await query.edit_message_text("⏳ Yaxshi, kutaman. Diqqat bilan ishla! 💪")
            logger.info(f"Task #{task_id} marked as doing_now")


async def reason_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles user's text reply after pressing ❌ Not yet."""
    task_id = context.user_data.get("pending_notyet_task_id")
    if not task_id:
        return

    reason = update.message.text
    logger.info(f"Received reason for task #{task_id}: {reason[:50]}...")

    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        task.snooze_reason = reason
        # NOTE: overdue_count is ONLY incremented by the scheduler, not here
        # This avoids the double-increment bug
        await session.commit()
        task_dict = {"text": task.text, "category": task.category, "overdue_count": task.overdue_count}

    try:
        reply = await asyncio.to_thread(generate_why_response, task_dict, reason)
    except Exception as e:
        logger.error(f"AI why response failed: {e}")
        reply = "Bahona qilma, ishni qil! 💪"

    await update.message.reply_text(reply)
    context.user_data.pop("pending_notyet_task_id", None)
    context.user_data.pop(f"awaiting_reason_{task_id}", None)
