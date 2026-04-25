from pyrogram import filters
from bot.__init__ import bot_app, config_data
from bot.helper_funcs.utils import AppState, queue

@bot_app.on_message(filters.command("status") & filters.user(config_data["AUTH_USERS"]))
async def status_cmd(client, message):
    text = f"📊 **Compression Status**\n\n⚙️ **Currently Processing:** `{AppState.active_file_name}`\n📥 **Files in Queue:** `{queue.qsize()}`"
    await message.reply(text)