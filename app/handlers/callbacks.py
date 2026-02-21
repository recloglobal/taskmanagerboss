from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
