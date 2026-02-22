import asyncio
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
        update_flag = None

        if task.due_at:
            # 1. Check 1 hour before deadline
            one_hour_before = task.due_at - timedelta(hours=1)
            if now >= one_hour_before and now < task.due_at and not task.reminded_before_due:
                should_remind = True
                update_flag = "reminded_before_due"

            # 2. Check exactly at deadline
            elif now >= task.due_at and not task.deadline_asked_at:
                should_remind = True
                update_flag = "deadline_asked_at"

            # 3. Check 30 minutes overdue penalty
            elif task.deadline_asked_at and now >= task.deadline_asked_at + timedelta(minutes=30):
                should_remind = True
                update_flag = "overdue_penalty"
        else:
            # No due date: remind every 48 hours
            last = task.reminded_at or task.created_at
            if now >= last + timedelta(hours=48):
                should_remind = True
                update_flag = "standard_48h"

        if not should_remind:
            continue

        task_dict = {
            "text": task.text,
            "category": task.category,
            "overdue_count": task.overdue_count,
        }

        # Async AI call to prevent blocking the event loop
        try:
            reminder_text = await asyncio.to_thread(generate_reminder, task_dict)
            if update_flag == "deadline_asked_at":
                reminder_text = f"⏰ Muddat keldi!\n\n{reminder_text}"
            elif update_flag == "reminded_before_due":
                reminder_text = f"1 soat qoldi! {reminder_text}"
        except Exception as e:
            logger.error(f"AI reminder generation failed for task {task.id}: {e}")
            reminder_text = f"⏰ Hali bajarilmagan vazifa bor: {task.text}"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Bajarildi", callback_data=f"done:{task.id}"),
                InlineKeyboardButton("❌", callback_data=f"notyet:{task.id}"),
                InlineKeyboardButton("⏳ Hozir qilyapman", callback_data=f"doing_now:{task.id}"),
            ]
        ])

        try:
            send_kwargs = {
                "chat_id": task.group_id,
                "text": reminder_text,
                "reply_markup": keyboard,
            }
            # Only pass message_thread_id if topics are configured
            if task.topic_id:
                send_kwargs["message_thread_id"] = task.topic_id

            await bot.send_message(**send_kwargs)

            # Update DB trackers based on what triggered the alert
            async with SessionLocal() as session:
                result = await session.execute(select(Task).where(Task.id == task.id))
                t = result.scalar_one_or_none()
                if t:
                    t.reminded_at = now
                    
                    if update_flag == "reminded_before_due":
                        t.reminded_before_due = True
                    elif update_flag == "deadline_asked_at":
                        t.deadline_asked_at = now
                    elif update_flag == "overdue_penalty":
                        t.overdue_count += 1
                        t.deadline_asked_at = None  # Reset so it falls into standard 48h loop
                    elif update_flag == "standard_48h":
                        t.overdue_count += 1
                        
                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to send reminder for task {task.id}: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="reminder_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler
