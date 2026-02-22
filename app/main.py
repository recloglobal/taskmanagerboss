import logging
import traceback
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN
from handlers.start import start_handler
from handlers.topics import topics_handler
from handlers.group import group_message_handler
from handlers.callbacks import button_callback_handler, reason_message_handler
from handlers.private import private_message_handler
from scheduler import start_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context) -> None:
    """Global error handler — logs all unhandled exceptions."""
    logger.error("Unhandled exception while processing update:")
    logger.error(f"  Update: {update}")
    logger.error(f"  Error: {context.error}")
    logger.error(traceback.format_exc())

    # Try to notify the user if possible
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring."
            )
        except Exception:
            pass


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("topics", topics_handler))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(done|notyet):"))

    # Group messages (reads #general topic)
    app.add_handler(MessageHandler(
        (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & filters.TEXT & ~filters.COMMAND,
        group_message_handler
    ))

    # Private chat: reason replies after ❌
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        reason_message_handler,
    ), group=1)

    # Private chat: general AI conversation
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        private_message_handler,
    ), group=2)

    # Global error handler
    app.add_error_handler(error_handler)

    # Start scheduler
    start_scheduler(app.bot)

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
