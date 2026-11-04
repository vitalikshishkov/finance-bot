import os
from dotenv import load_dotenv

load_dotenv()  # читает .env и загружает значения в окружение

BOT_TOKEN = os.getenv("BOT_TOKEN")
YADISK_TOKEN = os.getenv("YADISK_TOKEN")
INITIAL_ADMIN = int(os.getenv("INITIAL_ADMIN", "0"))
API_BASE = "https://platform-api2.max.ru"
DB_PATH = "finance_bot.db"
