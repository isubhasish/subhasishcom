import os
import sys
import json
import asyncio
import logging
import shutil
from pyrogram import idle
from bot.__init__ import bot_app, user_app, config_data
from bot.helper_funcs.ffmpeg import worker
from bot.helper_funcs.utils import AppState

import bot.commands
import bot.plugins.incoming_message_fn
import bot.plugins.call_back_button_handler
import bot.plugins.status_message_fn

logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def start_hybrid():
    logger.info("Booting Bot Client...")
    
    if not shutil.which("ffmpeg"):
        logger.error("❌ FFMPEG library isn't installed! Compression will fail.")
    else:
        logger.info("✅ FFMPEG is installed and ready.")
        
    await bot_app.start()
    
    me = await bot_app.get_me()
    AppState.bot_username = me.username
    logger.info(f"Bot Username detected: @{AppState.bot_username}")
    
    if os.path.exists("restart.json"):
        try:
            with open("restart.json", "r") as f:
                r_data = json.load(f)
            await bot_app.edit_message_text(
                chat_id=r_data["chat_id"],
                message_id=r_data["message_id"],
                text="✅ **Restarted successfully!**"
            )
        except Exception as e:
            logger.error(f"Failed to edit restart message: {e}")
        finally:
            os.remove("restart.json")
    
    logger.info("Booting Upload Client...")
    
    # --- BUG FIX: THE HYBRID START PREVENTER ---
    if user_app != bot_app:
        await user_app.start()
        logger.info("✅ User Session Client started successfully.")
    else:
        logger.info("✅ Running in Bot-Only Mode (Upload Client skipped).")
    
    # --- DYNAMIC LIMIT CHECKER ---
    # Correctly validates if the account can handle 4GB or 2GB uploads via MTProto
    if config_data.get("USER_SESSION_STRING"):
        me_user = await user_app.get_me()
        AppState.is_premium = me_user.is_premium
        status_text = "Premium (4GB Uploads)" if AppState.is_premium else "Free Session (2GB Uploads)"
        logger.info(f"✅ Session Verified | Limit Status: {status_text}")
    else:
        AppState.is_premium = False
        logger.info("✅ Bot Token Verified | Limit Status: Standard MTProto (2GB Uploads)")
    
    asyncio.create_task(worker())
    
    logger.info("Subhasish Encoder is fully online!")
    await idle()
    
    # --- BUG FIX: THE HYBRID STOP PREVENTER ---
    await bot_app.stop()
    if user_app != bot_app:
        await user_app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_hybrid())