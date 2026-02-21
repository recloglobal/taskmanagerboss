from telegram import Update
from telegram.ext import ContextTypes


async def topics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Run this inside each topic to get its thread ID.
    """
    thread_id = update.message.message_thread_id
    chat_id = update.message.chat_id

    if thread_id:
        await update.message.reply_text(
            f"📋 Bu mavzuning ID si:\n\n"
            f"`{thread_id}`\n\n"
            f"Buni `.env` faylingizga to'g'ri o'zgaruvchiga qo'ying.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"Bu asosiy guruh eki #general mavzusi.\n"
            f"Chat ID: `{chat_id}`",
            parse_mode="Markdown"
        )
