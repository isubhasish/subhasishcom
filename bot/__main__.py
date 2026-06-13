import os
import sys
import time
import json
import asyncio
import httpx
from pyrogram import idle
from bot import bot_app, user_app, logger
from bot.config import Config
from bot.helper_funcs.utils import START_TIME, get_readable_time, AppState, cpu_monitor
from bot.helper_funcs.ffmpeg import worker

import bot.plugins.commands
import bot.plugins.call_back_button_handler
import bot.plugins.incoming_message_fn
import bot.plugins.status_message_fn
import bot.plugins.merge_handler

async def fetch_default_thumbnail() -> None:
    thumb_url = "https://telegra.ph/file/5c4635e173e7407694a63.jpg"
    thumb_path = os.path.join(Config.ENV_DIR, "thumb.jpg")
    
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20), follow_redirects=True) as client:
            resp = await client.get(thumb_url)
            resp.raise_for_status()
        with open(thumb_path, "wb") as f:
            f.write(resp.content)
        logger.info("Default universal thumbnail saved to %s", thumb_path)
    except Exception as e:
        logger.warning("Default thumbnail download skipped: %s", e)

async def main():
    try:
        p1 = await asyncio.create_subprocess_exec("pkill", "-9", "-f", "ffmpeg", stderr=asyncio.subprocess.DEVNULL)
        await p1.wait()
        p2 = await asyncio.create_subprocess_exec("pkill", "-9", "-f", "ffprobe", stderr=asyncio.subprocess.DEVNULL)
        await p2.wait()
    except Exception:
        pass
        
    try:
        logger.info("Fetching default universal thumbnail...")
        await fetch_default_thumbnail()

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
        
        # Start the worker and the CPU monitor as concurrent background tasks
        asyncio.create_task(worker())
        asyncio.create_task(cpu_monitor())   # ← keeps _cpu_cache fresh
        
        restart_path = os.path.join(Config.ENV_DIR, "restart.json")
        if os.path.exists(restart_path):
            try:
                with open(restart_path, "r") as f:
                    data = json.load(f)
                    chat_id = data.get("chat_id")
                    msg_id = data.get("message_id")
                    if chat_id and msg_id:
                        await bot_app.edit_message_text(
                            chat_id, 
                            msg_id, 
                            "**Restarted Successfully!** ✅"
                        )
            except Exception as e:
                logger.error(f"Failed to edit restart msg: {e}")
            finally:
                if os.path.exists(restart_path):
                    os.remove(restart_path)
            
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