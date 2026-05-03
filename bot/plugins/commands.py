import os
import sys
import io
import time
import json
import random
import uuid
import signal
import asyncio
import traceback
import gc
import speedtest
import re 
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot_app, user_app, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import AppState, TaskState, queue, START_TIME, get_readable_time, send_log, get_file_info, kill_running_process, delete_message_later
from bot.helper_funcs.download import get_graph_link
from bot.helper_funcs.display_progress import humanbytes, make_bar, time_formatter, render_active_status, get_sys_stats, progress_bar
from bot.plugins.call_back_button_handler import get_bsetting_menu

UNAUTH_MSG = "<b>You are not allowed to do that 🤭</b>"

def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    auth_users = config_data.get("AUTH_USERS", [])
    owner_id = config_data.get("OWNER_ID", 0)
    
    if isinstance(auth_users, str):
        try: auth_users = json.loads(auth_users)
        except Exception: auth_users = []
        
    return user_id in auth_users or user_id == owner_id or chat_id in auth_users

def is_owner(message):
    user_id = message.from_user.id if message.from_user else 0
    return user_id == config_data.get("OWNER_ID", 0)

def get_uptime():
    uptime_ms = int((time.time() - START_TIME) * 1000)
    return get_readable_time(uptime_ms)

async def auto_clean(msg, message):
    await asyncio.sleep(30)
    if AppState.task_state == TaskState.IDLE and queue.qsize() == 0:
        try:
            await msg.delete()
            await message.delete()
        except: pass

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
        msg = await message.reply(f"Current {display_name}: `{config_data.get(key)}`")
        return asyncio.create_task(auto_clean(msg, message))
    val = message.command[1]
    if str(config_data.get(key)) == str(val): 
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
    if AppState.task_state == TaskState.IDLE: 
        msg = await message.reply(Localisation.NO_ACTIVE_TASK)
        return asyncio.create_task(auto_clean(msg, message))
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes ✅", callback_data="confirm_cancel_yes"), InlineKeyboardButton("No ❌", callback_data="confirm_cancel_no")]])
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
        active_client = user_app if user_app else bot_app
        real_path = await active_client.download_media(message.reply_to_message)
        if not real_path or not os.path.exists(real_path): return await msg.edit("❌ Failed to download file for probing.")
            
        process = await asyncio.create_subprocess_exec(
            "mediainfo", real_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True 
        )
        try: stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        except asyncio.TimeoutError:
            try: os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except: pass
            raise Exception("MediaInfo Process Timed Out")
            
        raw_info = stdout.decode('utf-8').strip()
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
    file_path = None
    sample_out = None
    actual_thumb = None
    user_id = target_message.from_user.id if target_message.from_user else 0
    custom_thumb = os.path.join(Config.THUMB_DIR, f"{user_id}.jpg")
    
    if os.path.exists(custom_thumb):
        actual_thumb = custom_thumb
        
    AppState.task_state = TaskState.SAMPLEGEN
    AppState.task_kind = "sample"
    AppState.active_origin_msg = target_message
    AppState.active_status_msg = status_msg
    AppState.active_file_name = getattr(target_message.video or target_message.document, 'file_name', 'sample_source')
    AppState.status_snapshot = Localisation.DOWNLOAD_START
    
    sample_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running")]
    ])
    
    try:
        active_client = user_app if user_app else bot_app
        
        # ---------- DOWNLOAD ----------
        dl_start = time.time()
        last_dl_update = [time.time() - 6]
        
        async def dl_progress(current, total):
            now = time.time()
            if (now - last_dl_update[0]) < 5 and current < total:
                return
            last_dl_update[0] = now
            
            if AppState.cancel_task:
                raise asyncio.CancelledError("Task Cancelled")
                
            percent = (current / total * 100) if total > 0 else 0
            elapsed = now - dl_start
            speed = current / elapsed if elapsed > 0 else 0
            eta_s = (total - current) / speed if speed > 0 else 0
            
            done_str = humanbytes(current)
            total_str = humanbytes(total)
            speed_str = humanbytes(speed)
            eta_str = time_formatter(eta_s * 1000)
            el_str = time_formatter(elapsed * 1000)
            
            cpu, mem, _ = get_sys_stats()
            
            AppState.status_snapshot = render_active_status(
                percent, done_str, total_str, eta_str, speed_str, el_str, display_status="Downloading"
            )
            
            text = (
                f"{Localisation.SAMPLE_DOWNLOADING}\n\n"
                f"[{make_bar(percent)}]\n"
                f"☞☢️ **ᴘʀᴏɢʀᴇss:** {percent:.1f}%\n"
                f"📦 **sɪᴢᴇ:** {done_str} of {total_str}\n"
                f"⚡️ **ꜱᴘᴇᴇᴅ:** {speed_str}/s\n"
                f"⏱️ **ᴇᴛᴀ:** {eta_str}\n"
                f"🖥 CPU: {cpu}% | 💽 RAM: {mem}%"
            )
            try:
                await status_msg.edit(text, reply_markup=sample_btn)
            except Exception: pass
                
        file_path = await active_client.download_media(target_message, progress=dl_progress)
        
        if not file_path or not os.path.exists(file_path):
            return await status_msg.edit(Localisation.FILE_NOT_FOUND)
            
        if AppState.cancel_task:
            raise asyncio.CancelledError()

        # ---------- PROBING ----------
        await status_msg.edit(Localisation.SAMPLE_PROBING, reply_markup=sample_btn)
        
        process = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True
        )
        
        async with AppState.process_lock:
            AppState.current_process = process
            
        try: stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        except asyncio.TimeoutError:
            try: os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except: pass
            raise Exception("FFProbe Process Timed Out")
        finally:
            async with AppState.process_lock:
                if AppState.current_process == process:
                    AppState.current_process = None
                    
        if AppState.cancel_task:
            raise asyncio.CancelledError()
            
        duration_output = stdout.decode('utf-8').strip()
        try: total_duration = float(duration_output)
        except: total_duration = 0
            
        if total_duration < 35:
            os.remove(file_path)
            return await status_msg.edit("⚠️ Video Is Too Short To Generate A 30-Second Sample..")
            
        start_time_cut = random.uniform(10, total_duration - 35)
        sample_out = f"Sample_{uuid.uuid4().hex}.mkv"

        # ---------- CUTTING ----------
        if AppState.status_snapshot:
            snapshot = AppState.status_snapshot.replace("Status:** Downloading", "Status:** Generating Sample")
            AppState.status_snapshot = snapshot
            
        await status_msg.edit(Localisation.SAMPLE_CUTTING, reply_markup=sample_btn)
        
        cut_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "quiet", "-nostats",
            "-ss", str(start_time_cut), "-i", file_path, "-t", "30", "-c", "copy", "-y", sample_out
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cut_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True
        )
        
        async with AppState.process_lock:
            AppState.current_process = process
            
        try:
            await asyncio.wait_for(process.communicate(), timeout=120)
        except asyncio.TimeoutError:
            try: os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except: pass
            return await status_msg.edit("⚠️ Sample cut timed out.")
        finally:
            async with AppState.process_lock:
                if AppState.current_process == process:
                    AppState.current_process = None
                    
        if AppState.cancel_task:
            raise asyncio.CancelledError()
            
        if not os.path.exists(sample_out):
            return await status_msg.edit("⚠️ Failed to generate sample.")

        # ---------- UPLOAD ----------
        await status_msg.edit(Localisation.SAMPLE_UPLOADING, reply_markup=sample_btn)
        
        caption = f"🎞 **Random 30s Sample**\n⏱ Cut from: `{time.strftime('%H:%M:%S', time.gmtime(start_time_cut))}`\n\n<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
        
        await active_client.send_video(
            chat_id=status_msg.chat.id,
            video=sample_out,
            caption=caption,
            thumb=actual_thumb,
            supports_streaming=True,
            reply_to_message_id=target_message.id
        )
        try: await status_msg.delete()
        except: pass

    except asyncio.CancelledError:
        from bot.helper_funcs.ffmpeg import abort_current_task
        await abort_current_task(status_msg, file_path, sample_out, chat_id=target_message.chat.id)
    except Exception as e:
        try: await status_msg.edit(f"❌ Sample Generation Error: {e}")
        except: pass
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        if sample_out and os.path.exists(sample_out):
            try: os.remove(sample_out)
            except: pass
            
        AppState.task_state = TaskState.IDLE
        AppState.task_kind = "compress"
        AppState.active_file_name = "None"
        AppState.active_origin_msg = None
        AppState.active_status_msg = None
        AppState.status_snapshot = ""
        AppState.cancel_task = False
        
        async with AppState.process_lock:
            AppState.current_process = None

@bot_app.on_message(filters.command("samplegen"))
async def samplegen_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    if AppState.task_state != TaskState.IDLE or not queue.empty(): return await message.reply(Localisation.SAMPLE_BUSY)
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

@bot_app.on_message(filters.command("cancelall"))
async def cancel_all_cmd(client, message):
    if not is_owner(message): return await message.reply(UNAUTH_MSG)
    while not queue.empty(): queue.get_nowait(); queue.task_done()
    
    AppState.cancel_task = True 
    await kill_running_process()
    
    if AppState.active_status_msg:
        try: await AppState.active_status_msg.delete()
        except: pass
        
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
        
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes ✅", callback_data="delthumb_yes"), InlineKeyboardButton("No ❌", callback_data="delthumb_no")]])
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
            f"🚀 <u>**sᴘᴇᴇᴅᴛᴇsᴛ ɪɴғᴏ**</u>\n\n"
            f"🔻 **ᴅᴏᴡɴʟᴏᴀᴅ:** `{d_speed}/s`\n"
            f"🔺 **ᴜᴘʟᴏᴀᴅ:** `{u_speed}/s`\n"
            f"📶 **ᴘɪɴɢ:** `{ping} ms`\n"
            f"🌍 **sᴇʀᴠᴇʀ:** `{res['server']['name']}, {res['server']['country']}`"
        )
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ **Speedtest Failed:** {e}")
        
def run_speedtest():
    st = speedtest.Speedtest(secure=True)
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
    auth_list = config_data.get('AUTH_USERS', [])
    await message.reply(f"📣 **Broadcasting to {len(auth_list)} users...**")
    
    for user_id in auth_list:
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
    help_text = (
        "**⚙️ Bot Settings Menu**\n"
        "Click a variable below to change its value interactively.\n"
        "✨ 𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵 ✨"
    )
    await message.reply(help_text, reply_markup=get_bsetting_menu())

@bot_app.on_message(filters.text & filters.private, group=1)
async def bsetting_input_catcher(client, message):
    user_id = message.from_user.id
    
    if user_id in AppState.bsetting_state and AppState.bsetting_state[user_id].get("step") == "awaiting_value":
        if message.text.startswith("/"):
            del AppState.bsetting_state[user_id]
            return
            
        key = AppState.bsetting_state[user_id]["key"]
        val = message.text.strip()
        
        AppState.bsetting_state[user_id]["msg_to_delete"] = message.id
        
        if str(config_data.get(key)) == str(val):
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"), InlineKeyboardButton("❌ Close", callback_data="bsetting_close")]])
            msg = await message.reply(f"⚠️ **{key}** is already set to `{val}`.", reply_markup=btn)
            AppState.bsetting_state[user_id]["bot_msg_to_delete"] = msg.id
            return

        AppState.bsetting_state[user_id]["pending_value"] = val
        AppState.bsetting_state[user_id]["step"] = "confirming"
        
        sensitive_keys = ["API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID"]
        
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes ✅", callback_data="bsetting_confirm_yes"),
             InlineKeyboardButton("No ❌", callback_data="bsetting_confirm_no")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"),
             InlineKeyboardButton("❌ Close", callback_data="bsetting_close")]
        ])
        
        if key in sensitive_keys: text = f"❓ **Confirm {key}**\n\nSensitive credential detected.\nDo you want to securely save this?"
        elif key == "USER_SESSION_STRING": text = f"❓ **Confirm Update**\n\nNew session string received.\nDo you want to securely save this?"
        elif key == "AS_DOCUMENT": text = f"❓ **Confirm Update**\n\nYou entered **{val}**.\n✨ 𝘖𝘯𝘭𝘺 𝘵𝘺𝘱𝘦 𝘛𝘳𝘶𝘦 𝘰𝘳 𝘍𝘢𝘭𝘴𝘦 ✨\n\nDo you want to save this?"
        else: text = f"❓ **Confirm Update**\n\nYou entered a new value for **{key}**:\n`{val}`\n\nDo you want to save this?"
            
        msg = await message.reply(text, reply_markup=btn)
        AppState.bsetting_state[user_id]["bot_msg_to_delete"] = msg.id