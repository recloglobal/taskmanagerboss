import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from database import SessionLocal
from models import Task
from ai import generate_reminder

logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot):
    """Check all pending tasks and send reminders if needed."""
    now = datetime.utcnow()

    async with SessionLocal() as session:
        result = await session.execute(
            select(Task).where(Task.status == "pending")
        )
        tasks = result.scalars().all()

    for task in tasks:
        should_remind = False

        if task.due_at:
            # Remind 1 day before due
            one_day_before = task.due_at - timedelta(days=1)
            if now >= one_day_before:
                should_remind = True
        else:
            # No due date: remind every 48 hours
            last = task.reminded_at or task.created_at
            if now >= last + timedelta(hours=48):
                should_remind = True

        if not should_remind:
            continue

        task_dict = {
            "text": task.text,
            "category": task.category,
            "overdue_count": task.overdue_count,
        }

        reminder_text = generate_reminder(task_dict)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Bajarildi", callback_data=f"done:{task.id}"),
                InlineKeyboardButton("❌ Bajarilmadi", callback_data=f"notyet:{task.id}"),
            ]
        ])

        try:
            await bot.send_message(
                chat_id=task.group_id,
                message_thread_id=task.topic_id,
                text=reminder_text,
                reply_markup=keyboard,
            )

            # Update reminder tracking
            async with SessionLocal() as session:
                result = await session.execute(select(Task).where(Task.id == task.id))
                t = result.scalar_one_or_none()
                if t:
                    t.reminded_at = now
                    t.overdue_count += 1
                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to send reminder for task {task.id}: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=60,
        args=[bot],
        id="reminder_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler
