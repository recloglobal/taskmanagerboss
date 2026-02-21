from telegram import Update
from telegram.ext import ContextTypes


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men TaskManagerBoss — sening shaxsiy vazifa menejeringman.\n\n"
        "📌 Guruhda #general mavzusiga vazifa yoz — men uni tasniflab, to'g'ri mavzuga qo'yaman.\n"
        "⏰ Muddatingni o'tkazib yuborsang, men senga xabar beraman.\n"
        "💬 Bu yerda esa men bilan erkin suhbatlashishingiz mumkin!"
    )
