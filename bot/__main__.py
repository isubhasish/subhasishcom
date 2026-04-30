import os
import subprocess
from bot.__init__ import bot_app, user_app, logger
from bot.helper_funcs.utils import queue, get_readable_time, START_TIME
from bot.helper_funcs.ffmpeg import worker
import asyncio

async def main():
    try:
        # FIX: The OS sweeper. Forcefully kills any leftover PuTTY ffmpeg processes before the bot boots!
        subprocess.run(["pkill", "-9", "-f", "ffmpeg"], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-9", "-f", "ffprobe"], stderr=subprocess.DEVNULL)
        
        await bot_app.start()
        logger.info("Bot Username detected: @%s", bot_app.me.username)
        
        if user_app:
            logger.info("Booting Upload Client...")
            await user_app.start()
            logger.info("✅ Upload Client (Userbot) Verified | Limit Status: Premium (4GB Uploads)")
        else:
            logger.info("Booting Upload Client...")
            logger.info("✅ Running in Bot-Only Mode (Upload Client skipped).")
            logger.info("✅ Bot Token Verified | Limit Status: Standard MTProto (2GB Uploads)")
            
        logger.info("Subhasish Encoder is fully online!")
        
        asyncio.create_task(worker())
        
        if os.path.exists("restart.json"):
            with open("restart.json", "r") as f:
                import json
                data = json.load(f)
                chat_id = data.get("chat_id")
                msg_id = data.get("message_id")
                if chat_id and msg_id:
                    try:
                        uptime = get_readable_time((time.time() - START_TIME)*1000)
                        await bot_app.edit_message_text(chat_id, msg_id, f"✅ **Restart Successful!**\n⏰ **Boot Time:** `{uptime}`")
                    except Exception as e:
                        logger.error(f"Failed to edit restart msg: {e}")
            os.remove("restart.json")
            
        from pyrogram import idle
        await idle()
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
    finally:
        await bot_app.stop()
        if user_app: await user_app.stop()

if __name__ == "__main__":
    bot_app.run(main())