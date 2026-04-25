import logging
import os
from pyrogram import Client
from bot.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

config_data = Config.load_config()
os.makedirs(Config.THUMB_DIR, exist_ok=True)

# Define Clients
bot_app = Client(
    "bot_session", 
    api_id=config_data["API_ID"], 
    api_hash=config_data["API_HASH"], 
    bot_token=config_data["TG_BOT_TOKEN"]
)

user_app = Client(
    "user_session", 
    api_id=config_data["API_ID"], 
    api_hash=config_data["API_HASH"]
)