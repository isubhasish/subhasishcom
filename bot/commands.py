import os
import sys
import io
import time
import json
import random
import asyncio
import traceback
import gc
import speedtest
import re 
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.__init__ import bot_app, user_app, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import AppState, queue, START_TIME, get_readable_time, send_log, get_file_info
from bot.helper_funcs.download import get_graph_link
from bot.helper_funcs.display_progress import humanbytes

SUDO_USERS = config_data["AUTH_USERS"] + [config_data["OWNER_ID"]]
UNAUTH_MSG = "<b>Opps You Need To Donate Some Amount To Use Meh...🐸👀</b>"

def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    return user_id in config_data["AUTH_USERS"] or user_id == config_data["OWNER_ID"] or chat_id in config_data["AUTH_USERS"]

def is_owner(message):
    user_id = message.from_user.id if message.from_user else 0
    return user_id == config_data["OWNER_ID"]

def get_uptime():
    uptime_ms = int((time.time() - START_TIME) * 1000)
    return get_readable_time(uptime_ms)

async def auto_clean(msg, message):
    await asyncio.sleep(30)
    if AppState.active_file_name == "None" and queue.qsize() == 0:
        try:
            await msg.delete()
            await message.delete()
        except: pass

# ==========================================
# 🟢 PUBLIC COMMANDS
# ==========================================
@bot_app.on_message(filters.command("start"))
async def start_cmd(client, message): 
    await message.reply(Localisation.START_TEXT)

@bot_app.on_message(filters.command("help"))
async def help_cmd(client, message): 
    msg = await message.reply(Localisation.HELP_TEXT)
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    start_t = time.time()
    msg = await message.reply("...")
    end_t = time.time()
    ping_ms = round((end_t - start_t) * 1000)
    await msg.edit(f"📶Pɪɴɢ = {ping_ms}ms\n⏰ **Uptime:** `{get_uptime()}`")
    asyncio.create_task(auto_clean(msg, message))

# ==========================================
# 🔴 SUDO COMMANDS
# ==========================================
@bot_app.on_message(filters.command("settings"))
async def settings_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    text = (
        "⚠️ **Current Ffmpeg Code Settings**\n"
        "The current settings will be added to your video file :\n\n"
        f"**Codec :** `{config_data.get('CODEC', 'libx265')}`\n"
        f"**Crf :** `{config_data.get('CRF', '28')}`\n"
        f"**Resolution :** `{config_data.get('RESOLUTION', '820x480')}`\n"
        f"**Preset :** `{config_data.get('PRESET', 'fast')}`\n"
        f"**Audio Bitrates :** `{config_data.get('AUDIO_BITRATE', '96k')}`\n"
        f"**Watermark :** `{config_data.get('WATERMARK_TEXT', 'None')}`\n"
        f"**Upload As Document :** `{config_data.get('AS_DOCUMENT', True)}`"
    )
    await message.reply(text)

async def update_setting(message, key, display_name):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    if len(message.command) < 2: 
        msg = await message.reply(f"Current {display_name}: `{config_data[key]}`")
        return asyncio.create_task(auto_clean(msg, message))
    val = message.command[1]
    if str(config_data[key]) == str(val): 
        msg = await message.reply(f"⚠️ {display_name} is already set to `{val}`")
        return asyncio.create_task(auto_clean(msg, message))
    config_data[key] = val
    Config.save_config(config_data)
    msg = await message.reply(f"✅ {display_name} successfully updated to `{val}`.")
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("preset"))
async def preset_cmd(client, message): await update_setting(message, "PRESET", "preset")

@bot_app.on_message(filters.command("crf"))
async def crf_cmd(client, message): await update_setting(message, "CRF", "crf")

@bot_app.on_message(filters.command("audio"))
async def audio_cmd(client, message): await update_setting(message, "AUDIO_BITRATE", "audio_bitrate")

@bot_app.on_message(filters.command("resolution"))
async def res_cmd(client, message): await update_setting(message, "RESOLUTION", "resolution")

@bot_app.on_message(filters.command("codec"))
async def codec_cmd(client, message): await update_setting(message, "CODEC", "codec")

@bot_app.on_message(filters.command("clear"))
async def clear_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    while not queue.empty(): queue.get_nowait(); queue.task_done()
    msg = await message.reply(Localisation.QUEUE_CLEARED)
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("cancel"))
async def cancel_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    if AppState.active_file_name == "None": 
        msg = await message.reply(Localisation.NO_ACTIVE_TASK)
        return asyncio.create_task(auto_clean(msg, message))
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes✅", callback_data="confirm_cancel_yes"), InlineKeyboardButton("No ❌", callback_data="confirm_cancel_no")]])
    msg = await message.reply(Localisation.CANCEL_PROMPT, reply_markup=btn, quote=True)
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("log"))
async def log_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    msg = await message.reply("⏳ Fetching bot logs...")
    try:
        with open("bot.log", "r") as f: log_data = f.read()[-30000:] 
        if not log_data: return await msg.edit("⚠️ Log file is empty.")
        content_json = [{"tag": "pre", "children": [log_data]}]
        link = await get_graph_link(content_json, "Subhasish Encoder Logs", "Subhasish Encoder")
        await msg.edit(f"📝 **Bot Logs:**\n{link}")
    except Exception as e: await msg.edit(f"❌ Failed to fetch logs: {e}")

@bot_app.on_message(filters.command("mediainfo"))
async def mediainfo_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    if not message.reply_to_message or not getattr(message.reply_to_message, 'video', None) and not getattr(message.reply_to_message, 'document', None):
        return await message.reply("⚠️ Reply to a video or document to get its MediaInfo.")
        
    msg = await message.reply("📝 Probing MediaInfo...")
    real_path = None
    
    try:
        real_path = await user_app.download_media(message.reply_to_message)
        if not real_path or not os.path.exists(real_path):
            return await msg.edit("❌ Failed to download file for probing.")
            
        # FIX: Closes the OS pipeline to prevent micro-zombies
        stream = os.popen(f"mediainfo '{real_path}'")
        raw_info = stream.read()
        stream.close()
        
        os.remove(real_path)
        
        size_str, _ = get_file_info(message.reply_to_message)
        real_name = getattr(message.reply_to_message.video or message.reply_to_message.document, 'file_name', 'video.mp4')
        
        raw_info = re.sub(r"Complete name\s+:\s+.*", f"Complete name                            : {real_name}", raw_info)
        raw_info = re.sub(r"File size\s+:\s+.*", f"File size                                : {size_str}", raw_info)
        
        content_json = []
        content_json.append({"tag": "h3", "children": [real_name]})

        current_pre = ""
        for line in raw_info.split('\n'):
            clean_line = line.strip()
            if clean_line in ["General", "Video", "Text", "Menu"] or clean_line.startswith("Audio"):
                if current_pre:
                    content_json.append({"tag": "pre", "children": [current_pre]})
                    current_pre = ""
                    
                icon = "📄" if clean_line == "General" else "🎬" if clean_line == "Video" else "💬" if clean_line == "Text" else "📑" if clean_line == "Menu" else "🔊"
                content_json.append({"tag": "h3", "children": [f"{icon} {clean_line}"]})
            else:
                if line.strip(): current_pre += line + "\n"
        
        if current_pre: content_json.append({"tag": "pre", "children": [current_pre]})
            
        link = await get_graph_link(content_json, "Subhasish Encoder Mediainfo", "Subhasish Encoder")
        await msg.edit(f"📊 **MediaInfo Link:**\n{link}")
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
        if real_path and os.path.exists(real_path): os.remove(real_path)

async def generate_sample_background(client, target_message, status_msg):
    try:
        await status_msg.edit(Localisation.DOWNLOAD_START)
        file_path = await user_app.download_media(target_message)
        if not file_path or not os.path.exists(file_path): return await status_msg.edit(Localisation.FILE_NOT_FOUND)

        await status_msg.edit(Localisation.SAMPLE_GENERATING)
        duration_cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{file_path}'"
        
        # FIX: Closes the OS pipeline to prevent micro-zombies
        stream = os.popen(duration_cmd)
        duration_output = stream.read().strip()
        stream.close()
        
        try: total_duration = float(duration_output)
        except: total_duration = 0
            
        if total_duration < 35:
            os.remove(file_path)
            return await status_msg.edit("⚠️ Video is too short to generate a 30-second sample.")

        start_time = random.uniform(10, total_duration - 35)
        sample_out = f"Sample_{int(time.time())}.mkv"
        cut_cmd = ["ffmpeg", "-ss", str(start_time), "-i", file_path, "-t", "30", "-c", "copy", "-y", sample_out]
        
        process = await asyncio.create_subprocess_exec(*cut_cmd)
        await process.communicate()

        if not os.path.exists(sample_out):
            os.remove(file_path)
            return await status_msg.edit("⚠️ Failed to generate sample.")

        await status_msg.edit(Localisation.UPLOAD_START)
        caption = f"🎞 **Random 30s Sample**\n⏱ Cut from: `{time.strftime('%H:%M:%S', time.gmtime(start_time))}`\n\n<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
        
        await client.send_document(chat_id=status_msg.chat.id, document=sample_out, caption=caption, force_document=True, reply_to_message_id=target_message.id)
        
        await status_msg.delete()
        os.remove(file_path); os.remove(sample_out)
    except Exception as e:
        await status_msg.edit(f"❌ Sample Generation Error: {e}")
        if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)
        if 'sample_out' in locals() and os.path.exists(sample_out): os.remove(sample_out)

@bot_app.on_message(filters.command("samplegen"))
async def samplegen_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    if AppState.current_process or not queue.empty(): return await message.reply(Localisation.SAMPLE_BUSY)
    if not message.reply_to_message: return await message.reply("⚠️ Please reply to a video to generate a sample.")
    
    if getattr(message.reply_to_message, 'audio', None) or getattr(message.reply_to_message, 'voice', None):
        await send_log(f"⚠️ **Abuse Warning:** User @{message.from_user.username} tried to use /samplegen on an Audio file.")
        return await message.reply("⚠️ `/samplegen` only works on Videos, not Audio files!")
        
    if not getattr(message.reply_to_message, 'video', None) and not getattr(message.reply_to_message, 'document', None):
        return await message.reply("⚠️ Please reply to a video or document to generate a sample.")
        
    msg = await message.reply("⏳ **Initializing Random Sample Generator...**")
    asyncio.create_task(generate_sample_background(client, message.reply_to_message, msg))

@bot_app.on_message(filters.command("clearlocals"))
async def clearlocals_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    try:
        gc.collect()
        await message.reply("✅ **Local Execution Variables Cleared!**\nServer RAM has been optimized and flushed.")
    except Exception as e:
        await message.reply(f"❌ **Failed to clear locals:** {e}")

@bot_app.on_message(filters.command("restart"))
async def restart_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    msg = await message.reply("🔄 **Restarting the server now...**")
    with open("restart.json", "w") as f: json.dump({"chat_id": msg.chat.id, "message_id": msg.id}, f)
    os.execl(sys.executable, sys.executable, "-m", "bot")

# ==========================================
# 👑 OWNER ONLY COMMANDS
# ==========================================
@bot_app.on_message(filters.command("cancelall"))
async def cancel_all_cmd(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    while not queue.empty(): queue.get_nowait(); queue.task_done()
    AppState.cancel_task = True 
    if AppState.current_process: 
        try: 
            AppState.current_process.terminate()
            await AppState.current_process.wait()
        except: pass
        AppState.current_process = None
    msg = await message.reply("⚠️ **ALL TASKS CANCELLED AND QUEUE CLEARED.**")
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("setthumbnail"))
async def set_thumb(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    if not message.reply_to_message or not message.reply_to_message.photo: return await message.reply(Localisation.INVALID_THUMB)
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    await message.reply_to_message.download(file_name=path)
    await message.reply(Localisation.THUMB_ADDED)

@bot_app.on_message(filters.command("delthumbnail"))
async def del_thumb_cmd(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    if not os.path.exists(path): 
        msg = await message.reply("⚠️ You don't have a custom thumbnail set.")
        return asyncio.create_task(auto_clean(msg, message))
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes✅", callback_data="delthumb_yes"), InlineKeyboardButton("No ❌", callback_data="delthumb_no")]])
    msg = await message.reply(Localisation.THUMB_WARNING, reply_markup=btn)
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("speedtest"))
async def speedtest_cmd(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    msg = await message.reply("⏳ **Running Server Speedtest...**\n✨ 𝘛𝘩𝘪𝘴 𝘵𝘢𝘬𝘦𝘴 𝘢𝘣𝘰𝘶𝘵 20 𝘴𝘦𝘤𝘰𝘯𝘥𝘴 ✨")
    try:
        res = await asyncio.to_thread(run_speedtest)
        d_speed = humanbytes(res['download'] / 8)
        u_speed = humanbytes(res['upload'] / 8)
        ping = res['ping']
        
        text = (
            f"🚀 **Oracle Server Speedtest**\n\n"
            f"🔻 **Download:** `{d_speed}/s`\n"
            f"🔺 **Upload:** `{u_speed}/s`\n"
            f"📶 **Ping:** `{ping} ms`\n"
            f"🌍 **Server:** `{res['server']['name']}, {res['server']['country']}`"
        )
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ **Speedtest Failed:** {e}")
        
def run_speedtest():
    st = speedtest.Speedtest()
    st.get_best_server()
    st.download()
    st.upload()
    return st.results.dict()

async def aexec(code, client, message):
    exec(f"async def __aexec(client, message): " + "".join(f"\n {l}" for l in code.split("\n")))
    return await locals()["__aexec"](client, message)

@bot_app.on_message(filters.command(["eval", "exec"]))
async def eval_handler(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    if len(message.text.split()) < 2: return
    cmd = message.text.split(maxsplit=1)[1]
    msg = await message.reply("Processing...")
    old_stderr = sys.stderr; old_stdout = sys.stdout; redirected_output = sys.stdout = io.StringIO(); redirected_error = sys.stderr = io.StringIO()
    stdout, stderr, exc = None, None, None
    try: await aexec(cmd, client, message)
    except Exception: exc = traceback.format_exc()
    stdout = redirected_output.getvalue(); stderr = redirected_error.getvalue(); sys.stdout = old_stdout; sys.stderr = old_stderr
    evaluation = exc or stderr or stdout or "Success"
    final_output = f"<b>EVAL</b>: <code>{cmd}</code>\n\n<b>OUTPUT</b>:\n<code>{evaluation.strip()}</code>\n"

    if len(final_output) > 4000:
        with open("eval.txt", "w+", encoding="utf8") as out_file: out_file.write(str(final_output))
        await message.reply_document(document="eval.txt", caption=cmd[:100], disable_notification=True)
        os.remove("eval.txt"); await msg.delete()
    else: await msg.edit(final_output)

@bot_app.on_message(filters.command("broadcast"))
async def broadcast_cmd(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    if len(message.command) < 2: return await message.reply("⚠️ Usage: `/broadcast Your message here`")
    
    b_msg = message.text.split(maxsplit=1)[1]
    success = 0
    failed = 0
    
    await message.reply(f"📣 **Broadcasting to {len(config_data['AUTH_USERS'])} users...**")
    
    for user_id in config_data['AUTH_USERS']:
        try:
            await bot_app.send_message(user_id, f"📣 **Announcement from Admin:**\n\n{b_msg}")
            success += 1
            await asyncio.sleep(0.5) 
        except: failed += 1
            
    msg = await message.reply(f"✅ **Broadcast Complete!**\n\n🟢 **Success:** `{success}`\n🔴 **Failed:** `{failed}`")
    asyncio.create_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("bsetting"))
async def bsetting_cmd(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("API_ID", callback_data="bsetting_select_API_ID"),
         InlineKeyboardButton("API_HASH", callback_data="bsetting_select_API_HASH")],
        [InlineKeyboardButton("TG_BOT_TOKEN", callback_data="bsetting_select_TG_BOT_TOKEN"),
         InlineKeyboardButton("OWNER_ID", callback_data="bsetting_select_OWNER_ID")],
        [InlineKeyboardButton("LOG_CHANNEL", callback_data="bsetting_select_LOG_CHANNEL"),
         InlineKeyboardButton("AUTH_USERS", callback_data="bsetting_select_AUTH_USERS")],
        [InlineKeyboardButton("USER_SESSION_STRING", callback_data="bsetting_select_USER_SESSION_STRING")],
        [InlineKeyboardButton("CRF", callback_data="bsetting_select_CRF"),
         InlineKeyboardButton("PRESET", callback_data="bsetting_select_PRESET")],
        [InlineKeyboardButton("RESOLUTION", callback_data="bsetting_select_RESOLUTION"),
         InlineKeyboardButton("AUDIO_BITRATE", callback_data="bsetting_select_AUDIO_BITRATE")],
        [InlineKeyboardButton("CODEC", callback_data="bsetting_select_CODEC"),
         InlineKeyboardButton("WATERMARK", callback_data="bsetting_select_WATERMARK_TEXT")],
        [InlineKeyboardButton("AS_DOCUMENT", callback_data="bsetting_toggle_AS_DOCUMENT")], 
        [InlineKeyboardButton("❌ Close", callback_data="bsetting_close")]
    ])
    
    help_text = (
        "**⚙️ Bot Settings Menu**\n"
        "Click a variable below to change its value interactively.\n"
        "✨ 𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵 ✨"
    )
    await message.reply(help_text, reply_markup=btn)

@bot_app.on_message(filters.text, group=1)
async def bsetting_input_catcher(client, message):
    user_id = message.from_user.id
    
    if user_id in AppState.bsetting_state and AppState.bsetting_state[user_id].get("step") == "awaiting_value":
        if message.text.startswith("/"):
            del AppState.bsetting_state[user_id]
            return
            
        key = AppState.bsetting_state[user_id]["key"]
        val = message.text.strip()
        
        AppState.bsetting_state[user_id]["pending_value"] = val
        AppState.bsetting_state[user_id]["step"] = "confirming"
        
        sensitive_keys = ["USER_SESSION_STRING", "API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID"]
        
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes ✅", callback_data="bsetting_confirm_yes"),
             InlineKeyboardButton("No ❌", callback_data="bsetting_confirm_no")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"),
             InlineKeyboardButton("❌ Close", callback_data="bsetting_close")]
        ])
        
        if key in sensitive_keys:
            text = f"❓ **Confirm {key}**\n\nSensitive credential detected.\nDo you want to securely save this?"
        elif key == "AS_DOCUMENT":
            text = f"❓ **Confirm Update**\n\nYou entered **{val}**.\n✨ 𝘖𝘯𝘭𝘺 𝘵𝘺𝘱𝘦 𝘛𝘳𝘶𝘦 𝘰𝘳 𝘍𝘢𝘭𝘴𝘦 ✨\n\nDo you want to save this?"
        else:
            text = f"❓ **Confirm Update**\n\nYou entered a new value for **{key}**:\n`{val}`\n\nDo you want to save this?"
            
        await message.reply(text, reply_markup=btn)