from telegram import Update
from telegram.ext import ContextTypes
from config import OWNER_ID
from ai import chat, clear_history


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

    reply = chat(user_id, user_text)
    await message.reply_text(reply)
