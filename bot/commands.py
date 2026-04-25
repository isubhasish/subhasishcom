import os
import sys
import io
import time
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.__init__ import bot_app, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import AppState, queue, START_TIME
from bot.helper_funcs.download import get_graph_link

# Creates a combined list of Owner + Auth Users for Sudo access
SUDO_USERS = config_data["AUTH_USERS"] + [config_data["OWNER_ID"]]

def get_uptime():
    uptime_sec = int(time.time() - START_TIME)
    m, s = divmod(uptime_sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"

@bot_app.on_message(filters.command("start") & filters.user(SUDO_USERS))
async def start_cmd(client, message):
    await message.reply(Localisation.START_TEXT)

@bot_app.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply(Localisation.HELP_TEXT)

@bot_app.on_message(filters.command("ping") & filters.user(SUDO_USERS))
async def ping_cmd(client, message):
    await message.reply(f"🏓 **Pong!**\n\n⏰ **Uptime:** `{get_uptime()}`")

@bot_app.on_message(filters.command("clear") & filters.user(SUDO_USERS))
async def clear_cmd(client, message):
    count = 0
    while not queue.empty():
        queue.get_nowait()
        queue.task_done()
        count += 1
    await message.reply(f"🔫 **Queue Cleared!** Removed {count} pending tasks.")

@bot_app.on_message(filters.command("cancelall") & filters.user(SUDO_USERS))
async def cancel_all_cmd(client, message):
    while not queue.empty():
        queue.get_nowait()
        queue.task_done()
    if AppState.current_process:
        AppState.current_process.terminate()
        AppState.current_process = None
    await message.reply("⚠️ **ALL TASKS CANCELLED AND QUEUE CLEARED.**")

@bot_app.on_message(filters.command(["cancel", "stop"]) & filters.user(SUDO_USERS))
async def cancel_cmd(client, message):
    if not AppState.current_process:
        return await message.reply(Localisation.NO_ACTIVE_TASK)
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Cancel Task", callback_data="confirm_cancel_yes"),
         InlineKeyboardButton("❌ No, Continue", callback_data="confirm_cancel_no")]
    ])
    await message.reply(Localisation.CANCEL_PROMPT, reply_markup=btn)

@bot_app.on_message(filters.command("log") & filters.user(SUDO_USERS))
async def log_cmd(client, message):
    msg = await message.reply("⏳ Fetching bot logs...")
    try:
        with open("bot.log", "r") as f:
            log_data = f.read()[-30000:] # Get last 30,000 characters
        if not log_data:
            return await msg.edit("⚠️ Log file is empty.")
        link = await get_graph_link(log_data)
        await msg.edit(f"📝 **Bot Logs:**\n{link}", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit(f"❌ Failed to fetch logs: {e}")

# --- SUDO SETTINGS COMMANDS ---
@bot_app.on_message(filters.command("settings") & filters.user(SUDO_USERS))
async def settings_cmd(client, message):
    text = (
        "⚠️ **Current Ffmpeg Code Settings**\n"
        "The current settings will be added to your video file :\n\n"
        f"**Codec :** `{config_data['CODEC']}`\n"
        f"**Crf :** `{config_data['CRF']}`\n"
        f"**Resolution :** `{config_data['RESOLUTION']}`\n"
        f"**Preset :** `{config_data['PRESET']}`\n"
        f"**Audio Bitrates :** `{config_data['AUDIO_BITRATE']}`"
    )
    await message.reply(text)

async def update_setting(message, key):
    if len(message.command) < 2:
        return await message.reply(f"Usage: `/{message.command[0].lower()} <value>`")
    val = message.command[1]
    config_data[key] = val
    Config.save_config(config_data)
    await message.reply(f"✅ `{key}` successfully updated to `{val}`.")

@bot_app.on_message(filters.command("preset") & filters.user(SUDO_USERS))
async def preset_cmd(client, message): await update_setting(message, "PRESET")

@bot_app.on_message(filters.command("crf") & filters.user(SUDO_USERS))
async def crf_cmd(client, message): await update_setting(message, "CRF")

@bot_app.on_message(filters.command("audio") & filters.user(SUDO_USERS))
async def audio_cmd(client, message): await update_setting(message, "AUDIO_BITRATE")

@bot_app.on_message(filters.command("resolution") & filters.user(SUDO_USERS))
async def res_cmd(client, message): await update_setting(message, "RESOLUTION")

@bot_app.on_message(filters.command("codec") & filters.user(SUDO_USERS))
async def codec_cmd(client, message): await update_setting(message, "CODEC")

# --- OWNER ONLY COMMANDS ---
@bot_app.on_message(filters.command("setvar") & filters.user(config_data["OWNER_ID"]))
async def setvar_cmd(client, message):
    try:
        _, k, v = message.text.split(maxsplit=2)
        if k in ["AUTH_USERS"]: v = json.loads(v) # Allow passing arrays like [123, 456]
        elif v.isdigit() and k not in ["USER_SESSION_STRING"]: v = int(v)
        config_data[k] = v
        Config.save_config(config_data)
        await message.reply(f"✅ `{k}` updated to `{v}`. Use /restart to apply.\n*(Note: Help instructions for changing session strings: use `/setvar USER_SESSION_STRING your_string_here`)*")
    except Exception as e: 
        await message.reply("Usage: `/setvar LOG_CHANNEL -100123`")

@bot_app.on_message(filters.command(["eval", "exec"]) & filters.user(config_data["OWNER_ID"]))
async def eval_handler(client, message):
    if len(message.text.split()) < 2: return
    cmd = message.text.split(maxsplit=1)[1]
    msg = await message.reply("Running...")
    try:
        exec(f"async def __ex(client, message): " + "".join(f"\n {l}" for l in cmd.split("\n")))
        result = await locals()["__ex"](client, message)
        await msg.edit(f"**Result:**\n`{result or 'Success'}`")
    except Exception as e: 
        await msg.edit(f"**Error:**\n`{e}`")

@bot_app.on_message(filters.command("restart") & filters.user(config_data["OWNER_ID"]))
async def restart_cmd(client, message):
    await message.reply("🔄 Restarting Server...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# --- THUMBNAIL LOGIC ---
@bot_app.on_message(filters.command("setthumbnail") & filters.user(SUDO_USERS))
async def set_thumb(client, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("⚠️ Reply to a photo with `/setthumbnail` to save it.")
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    await message.reply_to_message.download(file_name=path)
    await message.reply(Localisation.THUMB_SAVED)

@bot_app.on_message(filters.command("delthumbnail") & filters.user(SUDO_USERS))
async def del_thumb_cmd(client, message):
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    if not os.path.exists(path):
        return await message.reply("⚠️ You don't have a custom thumbnail set.")
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data="delthumb_yes"),
         InlineKeyboardButton("❌ No, Cancel", callback_data="delthumb_no")]
    ])
    await message.reply(Localisation.THUMB_WARNING, reply_markup=btn)