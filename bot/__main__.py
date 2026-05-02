import os
import sys
import time
import json
import asyncio
from pyrogram import idle
from bot import bot_app, user_app, logger
from bot.helper_funcs.utils import START_TIME, get_readable_time, AppState
from bot.helper_funcs.ffmpeg import worker

import bot.plugins.commands
import bot.plugins.call_back_button_handler
import bot.plugins.incoming_message_fn
import bot.plugins.status_message_fn

async def main():
    try:
        # FIX: Non-blocking process cleanup
        p1 = await asyncio.create_subprocess_exec("pkill", "-9", "-f", "ffmpeg", stderr=asyncio.subprocess.DEVNULL)
        await p1.wait()
        p2 = await asyncio.create_subprocess_exec("pkill", "-9", "-f", "ffprobe", stderr=asyncio.subprocess.DEVNULL)
        await p2.wait()
    except Exception:
        pass
        
    try:
        # FIX: Fetch the default thumbnail gracefully on boot
        logger.info("Fetching default universal thumbnail...")
        os.system("wget -q https://telegra.ph/file/5c4635e173e7407694a63.jpg -O thumb.jpg")

        await bot_app.start()
        logger.info("Bot Username detected: @%s", bot_app.me.username)
        
        AppState.bot_username = bot_app.me.username
        
        if user_app != bot_app:
            logger.info("Booting Upload Client...")
            if not user_app.is_connected:
                await user_app.start()
            AppState.is_premium = True
            logger.info("✅ Upload Client (Userbot) Verified | Limit Status: Premium (4GB Uploads)")
        else:
            logger.info("✅ Running in Bot-Only Mode (2GB Limit)")
            
        logger.info("Subhasish Encoder is fully online!")
        
        asyncio.create_task(worker())
        
        if os.path.exists("restart.json"):
            try:
                with open("restart.json", "r") as f:
                    data = json.load(f)
                    chat_id = data.get("chat_id")
                    msg_id = data.get("message_id")
                    if chat_id and msg_id:
                        # FIX: Clean, custom restart message without Boot Time
                        await bot_app.edit_message_text(
                            chat_id, 
                            msg_id, 
                            "Restarted successfully!"
                        )
            except Exception as e:
                logger.error(f"Failed to edit restart msg: {e}")
            finally:
                if os.path.exists("restart.json"):
                    os.remove("restart.json")
            
        await idle()
        
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
    finally:
        try:
            await bot_app.stop()
        except Exception:
            pass
        if user_app != bot_app:
            try:
                await user_app.stop()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")