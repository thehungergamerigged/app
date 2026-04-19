import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

YOUTUBE_CHANNEL_IDS: list[str] = [
    cid.strip()
    for cid in os.getenv("YOUTUBE_CHANNEL_IDS", "").split(",")
    if cid.strip()
]

POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "10"))
SEEN_IDS_FILE = os.getenv("SEEN_IDS_FILE", "seen_ids.json")
PORT = int(os.getenv("PORT", "8000"))

# Weighted vote weights (must sum to 1.0)
GEMINI_WEIGHT = 0.35
CLAUDE_WEIGHT = 0.35
GPT_WEIGHT = 0.30
