import logging
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


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("topics", topics_handler))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(done|notyet):"))

    # Group messages (reads #general topic)
    app.add_handler(MessageHandler(
        filters.Chat(chat_type=["group", "supergroup"]) & filters.TEXT & ~filters.COMMAND,
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

    # Start scheduler
    start_scheduler(app.bot)

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
