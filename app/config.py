import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

DATABASE_URL_SYNC = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

TOPIC_GENERAL = int(os.getenv("TOPIC_GENERAL") or 0)
TOPIC_WORK = int(os.getenv("TOPIC_WORK") or 0)
TOPIC_PERSONAL = int(os.getenv("TOPIC_PERSONAL") or 0)
TOPIC_HEALTH = int(os.getenv("TOPIC_HEALTH") or 0)
TOPIC_OTHER = int(os.getenv("TOPIC_OTHER") or 0)

CATEGORY_TOPIC_MAP = {
    "work": TOPIC_WORK,
    "personal": TOPIC_PERSONAL,
    "health": TOPIC_HEALTH,
    "other": TOPIC_OTHER,
}

REMINDER_INTERVAL_MINUTES = 60
