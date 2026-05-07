import logging
from logging.handlers import RotatingFileHandler
import os
from pyrogram import Client
from bot.config import Config

config_data = Config.load_config()
os.makedirs(Config.THUMB_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(Config.ENV_DIR, "bot.log"), 
            maxBytes=20000000, 
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# 🛡️ THE FIX: BULLETPROOF CREDENTIAL CLEANER
# ==========================================
try:
    # Forces API_ID to be a strict integer and removes accidentally pasted spaces
    CLEAN_API_ID = int(str(config_data.get("API_ID", "")).strip())
except ValueError:
    CLEAN_API_ID = 0

# Removes invisible spaces/newlines from Hash, Token, and Session
CLEAN_API_HASH = str(config_data.get("API_HASH", "")).strip()
CLEAN_BOT_TOKEN = str(config_data.get("TG_BOT_TOKEN", "")).strip()
CLEAN_SESSION = str(config_data.get("USER_SESSION_STRING", "")).strip()

bot_app = Client(
    os.path.join(Config.ENV_DIR, "encoder_bot"),
    api_id=CLEAN_API_ID,
    api_hash=CLEAN_API_HASH,
    bot_token=CLEAN_BOT_TOKEN
)

# Ensures that accidental spaces or the literal word "None" don't trigger the Userbot
if CLEAN_SESSION and CLEAN_SESSION.lower() not in ["none", "", "null"]:
    logger.info("✅ User Session detected. Evaluating Account Tier limits...")
    user_app = Client(
        os.path.join(Config.ENV_DIR, "encoder_user"),
        session_string=CLEAN_SESSION,
        api_id=CLEAN_API_ID,
        api_hash=CLEAN_API_HASH
    )
else:
    logger.info("ℹ️ No USER_SESSION_STRING. Running on Bot Token (2GB limit).")
    user_app = bot_app  # ← CRITICAL: fallback to bot_app, never None