import os
import subprocess
import time
import json
import asyncio
from pyrogram import idle
from bot.__init__ import bot_app, user_app, logger
from bot.helper_funcs.utils import START_TIME, get_readable_time
from bot.helper_funcs.ffmpeg import worker

async def main():
    try:
        # The OS sweeper. Forcefully kills any leftover PuTTY ffmpeg processes before the bot boots!
        subprocess.run(["pkill", "-9", "-f", "ffmpeg"], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-9", "-f", "ffprobe"], stderr=subprocess.DEVNULL)
        
        # Start the Main Bot Client
        await bot_app.start()
        logger.info("Bot Username detected: @%s", bot_app.me.username)
        
        # Start the Upload Client (Userbot) if configured
        if user_app:
            logger.info("Booting Upload Client...")
            await user_app.start()
            logger.info("✅ Upload Client (Userbot) Verified | Limit Status: Premium (4GB Uploads)")
        else:
            logger.info("Booting Upload Client...")
            logger.info("✅ Running in Bot-Only Mode (Upload Client skipped).")
            logger.info("✅ Bot Token Verified | Limit Status: Standard MTProto (2GB Uploads)")
            
        logger.info("Subhasish Encoder is fully online!")
        
        # Start the background compression worker
        asyncio.create_task(worker())
        
        # Handle post-restart UI updates
        if os.path.exists("restart.json"):
            try:
                with open("restart.json", "r") as f:
                    data = json.load(f)
                    chat_id = data.get("chat_id")
                    msg_id = data.get("message_id")
                    if chat_id and msg_id:
                        uptime = get_readable_time((time.time() - START_TIME) * 1000)
                        await bot_app.edit_message_text(
                            chat_id, 
                            msg_id, 
                            f"✅ **Restart Successful!**\n⏰ **Boot Time:** `{uptime}`"
                        )
            except Exception as e:
                logger.error(f"Failed to edit restart msg: {e}")
            finally:
                if os.path.exists("restart.json"):
                    os.remove("restart.json")
            
        # Keep the process alive and listening for Telegram updates
        await idle()
        
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
    finally:
        # Gracefully shut down both clients on exit
        try:
            await bot_app.stop()
        except Exception:
            pass
        if user_app:
            try:
                await user_app.stop()
            except Exception:
                pass

if __name__ == "__main__":
    # FIX: Use asyncio.run() instead of bot_app.run() to prevent connection conflicts
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")