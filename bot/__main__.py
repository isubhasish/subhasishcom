import os
import sys
# Ensure the root directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from pyrogram import idle
from bot.__init__ import bot_app, user_app
from bot.helper_funcs.ffmpeg import worker

# Explicitly import files so decorators are registered
import bot.command
import bot.plugins.incoming_message_fn
import bot.plugins.call_back_button_handler
import bot.plugins.status_message_fn

logger = logging.getLogger(__name__)

async def start_hybrid():
    logger.info("Booting Bot Client...")
    await bot_app.start()
    
    logger.info("Booting User Client (4GB Limit Bypass)...")
    await user_app.start()
    
    # Start the FFmpeg Queue Worker
    asyncio.create_task(worker())
    
    logger.info("Gemini Modular Compressor is fully online!")
    await idle()
    
    await bot_app.stop()
    await user_app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_hybrid())