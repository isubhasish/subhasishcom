import os
import sys
import io
import traceback
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.__init__ import bot_app, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import AppState

@bot_app.on_message(filters.command("start") & filters.user(config_data["AUTH_USERS"]))
async def start_cmd(client, message):
    await message.reply(Localisation.START_TEXT)

@bot_app.on_message(filters.command("setvar") & filters.user(config_data["OWNER_ID"]))
async def setvar_cmd(client, message):
    try:
        _, k, v = message.text.split(maxsplit=2)
        config_data[k] = int(v) if v.isdigit() else v
        Config.save_config(config_data)
        await message.reply(f"✅ `{k}` updated to `{v}`. Use /restart to apply.")
    except Exception as e: 
        await message.reply("Usage: `/setvar CRF 26`")

@bot_app.on_message(filters.command("eval") & filters.user(config_data["OWNER_ID"]))
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

@bot_app.on_message(filters.command("setthumbnail") & filters.user(config_data["AUTH_USERS"]))
async def set_thumb(client, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("⚠️ Reply to a photo with `/setthumbnail` to save it.")
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    await message.reply_to_message.download(file_name=path)
    await message.reply(Localisation.THUMB_SAVED)

@bot_app.on_message(filters.command("delthumbnail") & filters.user(config_data["AUTH_USERS"]))
async def del_thumb_cmd(client, message):
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    if not os.path.exists(path):
        return await message.reply("⚠️ You don't have a custom thumbnail set.")
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data="delthumb_yes"),
         InlineKeyboardButton("❌ No, Cancel", callback_data="delthumb_no")]
    ])
    await message.reply(Localisation.THUMB_WARNING, reply_markup=btn)

@bot_app.on_message(filters.command("cancel") & filters.user(config_data["AUTH_USERS"]))
async def cancel_cmd(client, message):
    if not AppState.current_process:
        return await message.reply(Localisation.NO_ACTIVE_TASK)
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Cancel Task", callback_data="confirm_cancel_yes"),
         InlineKeyboardButton("❌ No, Continue", callback_data="confirm_cancel_no")]
    ])
    await message.reply(Localisation.CANCEL_PROMPT, reply_markup=btn)