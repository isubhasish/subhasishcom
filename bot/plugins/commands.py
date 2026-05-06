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
import psutil
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot_app, user_app, config_data, logger
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import AppState, TaskState, queue, START_TIME, get_readable_time, send_log, get_file_info, kill_running_process, delete_message_later, get_network_io
from bot.helper_funcs.download import get_graph_link
from bot.helper_funcs.display_progress import humanbytes, make_bar, time_formatter, render_active_status, get_sys_stats, progress_bar
from bot.plugins.call_back_button_handler import get_bsetting_menu
from bot.helper_funcs.ffmpeg import abort_current_task, take_screen_shot, start_tg_http_proxy, _find_free_port

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
    uptime_str = get_uptime()
    
    git_info = ""
    if os.path.exists(".git"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "log", "-1", "--format=%cd", "--date=format:%d/%m/%Y|%I:%M %p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            git_out = stdout.decode().strip()
            if "|" in git_out:
                g_date, g_time = git_out.split("|")
                git_info = (
                    f"⭐️ <b><u>Last Updated:</u></b> 🌟\n"
                    f"✶ <i><b>Date ➝</b></i> {g_date}\n"
                    f"✶ <i><b>Time ➝</b></i> {g_time}"
                )
        except Exception:
            pass
            
    text = f"📶 <b>Pɪɴɢ =</b> {ping_ms}ms\n⏰ <b>ᴜᴘᴛɪᴍᴇ:</b> {uptime_str}"
    if git_info:
        text += f"\n\n{git_info}"
        
    await msg.edit(text)
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
        log_path = os.path.join(Config.ENV_DIR, "bot.log")
        if not os.path.exists(log_path): return await msg.edit("⚠️ Log file is empty or not yet created.")
        
        with open(log_path, "r") as f: log_data = f.read()[-30000:] 
        if not log_data: return await msg.edit("⚠️ Log file is empty.")
        
        content_json = []
        content_json.append({"tag": "pre", "children": [log_data]})
        
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
    probe_path: str | None = None
    sample_out: str | None = None
    gen_thumb: str | None = None          
    proxy_server: asyncio.AbstractServer | None = None
    
    user_id = target_message.from_user.id if target_message.from_user else 0
    custom_thumb = os.path.join(Config.THUMB_DIR, f"{user_id}.jpg")
    actual_thumb: str | None = custom_thumb if os.path.exists(custom_thumb) else None
        
    AppState.task_state = TaskState.SAMPLEGEN
    AppState.task_kind = "sample"
    AppState.active_origin_msg = target_message
    AppState.active_status_msg = status_msg
    
    media = target_message.video or target_message.document
    AppState.active_file_name = getattr(media, "file_name", "sample_source")
    AppState.status_snapshot = Localisation.SAMPLE_CUTTING
    
    sample_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running")]])
    
    try:
        active_client = user_app if user_app else bot_app
        if not media:
            return await status_msg.edit("⚠️ No media found on this message.")
        file_size: int = media.file_size or 0

        # ---------- RESOLVE DURATION ----------
        total_duration = float(getattr(media, "duration", 0) or 0)
        
        if total_duration < 1.0:
            await status_msg.edit(Localisation.SAMPLE_PROBING, reply_markup=sample_btn)
            probe_path = f"/tmp/probe_{uuid.uuid4().hex[:10]}.mkv"
            with open(probe_path, "wb") as pf:
                async for chunk in active_client.stream_media(target_message, limit=8):
                    if AppState.cancel_task: raise asyncio.CancelledError()
                    pf.write(chunk)
            if AppState.cancel_task: raise asyncio.CancelledError()

            probe_proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", probe_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
            )
            async with AppState.process_lock:
                AppState.current_process = probe_proc
            try: probe_stdout, _ = await asyncio.wait_for(probe_proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                try: os.killpg(os.getpgid(probe_proc.pid), signal.SIGKILL)
                except Exception: pass
                raise Exception("FFProbe timed out during header probe.")
            finally:
                async with AppState.process_lock:
                    if AppState.current_process == probe_proc: AppState.current_process = None
            if probe_path and os.path.exists(probe_path):
                os.remove(probe_path)
            probe_path = None
            
            try: total_duration = float(probe_stdout.decode("utf-8").strip())
            except (ValueError, TypeError): total_duration = 0.0
        else:
            await status_msg.edit(
                "⚡️ **Fast Sample Mode Active**\n"
                "📡 Duration from metadata — probe step skipped!\n",
                reply_markup=sample_btn,
            )

        SAMPLE_DURATION = 30
        MIN_LEN = SAMPLE_DURATION + 15
        
        if total_duration < MIN_LEN:
            return await status_msg.edit(
                f"❎**ᴠɪᴅᴇᴏ ɪs ᴛᴏᴏ sʜᴏʀᴛ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀ** `{SAMPLE_DURATION}s` **sᴀᴍᴘʟᴇ, ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ** `{MIN_LEN}s` **ᴛɪᴍᴇ ғᴏʀ ᴛʜɪs** `{int(total_duration)}s` **ᴅᴜʀᴀᴛɪᴏɴ ᴠɪᴅᴇᴏ, ᴜsᴇ ᴀɴᴏᴛʜᴇʀ ᴠɪᴅᴇᴏ.**❎"
            )
            
        if AppState.cancel_task: raise asyncio.CancelledError()

        # ---------- RANDOM CUT POINT & PROXY SETUP ----------
        start_time_cut = random.uniform(10.0, total_duration - (SAMPLE_DURATION + 5))
        cut_str        = time.strftime("%H:%M:%S", time.gmtime(start_time_cut))
        sample_out     = f"/tmp/Sample_{uuid.uuid4().hex[:12]}.mkv"
        
        proxy_port = _find_free_port()
        progress_dict = {"downloaded": 0}
        proxy_server = await start_tg_http_proxy(active_client, target_message, proxy_port, file_size, progress_dict)
        file_url = f"http://127.0.0.1:{proxy_port}/"

        # ---------- FFMPEG INPUT SEEKING ----------
        cut_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "quiet", "-nostats",
            "-ss", f"{start_time_cut:.3f}",   
            "-i", file_url,
            "-t",  str(SAMPLE_DURATION),
            "-c",  "copy",                     
            "-avoid_negative_ts", "make_zero",
            "-y", sample_out,
        ]
        
        cut_proc = await asyncio.create_subprocess_exec(
            *cut_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
        )
        async with AppState.process_lock: 
            AppState.current_process = cut_proc
            
        MAX_WAIT_SEC = 300.0
        POLL_SEC     = 2.5
        wait_start   = time.time()
        last_ui_update = time.time() - 6
        gen_start = time.time()
        
        current_phase = "Sample Generating"
        
        while True:
            if AppState.cancel_task:
                await kill_running_process()
                raise asyncio.CancelledError("Task Cancelled by User")
            
            if cut_proc.returncode is not None:
                break
                
            now = time.time()
            if now - last_ui_update >= POLL_SEC:
                last_ui_update = now
                elapsed = max(now - gen_start, 0.001)
                total_fed = progress_dict["downloaded"]
                speed = total_fed / elapsed if elapsed > 0 else 0
                
                pct = min((total_fed / file_size) * 100, 99.9) if file_size > 0 else 0
                cpu, mem, disk = get_sys_stats()
                speed_str = humanbytes(speed)
                
                if speed > 0:
                    expected_bytes = 16 * 1024 * 1024
                    rem_bytes = max(0, expected_bytes - total_fed)
                    est_rem = rem_bytes / speed
                else:
                    est_rem = max(1, 15 - elapsed)
                est_rem = max(1, est_rem)
                eta_str = time_formatter(est_rem * 1000)
                
                primary_text = (
                    f"{Localisation.SAMPLE_CUTTING}\n\n"
                    f"[{make_bar(pct)}]\n"
                    f"☞☢️ **ᴘʀᴏɢʀᴇss:** {pct:.1f}%\n"
                    f"📦 **sɪᴢᴇ:** {humanbytes(total_fed)} of {humanbytes(file_size)}\n"
                    f"💎 **ᴛᴀʀɢᴇᴛ:** `{cut_str}` 💠 **sᴀᴍᴘʟᴇ:** `{SAMPLE_DURATION}s`\n"
                    f"⚡️ **ꜱᴘᴇᴇᴅ:** {speed_str}/s\n"
                    f"⏱️ **ᴇᴛᴀ:** {eta_str}\n"
                    f"🖥 **CPU:** {cpu}% | 💽 **RAM:** {mem}%"
                )
                
                sent, recv = get_network_io()
                free_disk_gb = round(psutil.disk_usage('/').free / (1024**3), 2)
                uptime_str = get_readable_time((time.time() - START_TIME)*1000)
                elapsed_str = time.strftime('%Ss', time.gmtime(elapsed))
                
                secondary_text = (
                    f"🌐 <b><u>Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs</u></b> 🌐\n"
                    f"{AppState.active_file_name}\n"
                    f"[{make_bar(pct)}] {pct:.2f}%\n"
                    f"**Processed:** {humanbytes(total_fed)} of {humanbytes(file_size)}\n"
                    f"**Target:** {cut_str} | **Sample:** {SAMPLE_DURATION}s\n"
                    f"**Status:** {current_phase} | **ETA:** {eta_str}\n"
                    f"**Speed:** {speed_str}/s | **Elapsed:** {elapsed_str}\n\n"
                    f"🔰 <b><u>Hardware Info:</u></b> 🔰\n"
                    f"**CPU:** {cpu}% | **Free:** {free_disk_gb}GB ({100-disk}%)\n"
                    f"**In:** {humanbytes(recv)} | **Out:** {humanbytes(sent)}\n"
                    f"**Ram:** {mem}% | **Uptime:** {uptime_str}\n\n"
                    f"**🏷 Maintained By: @Subhasish_bot**"
                )
                
                try: await status_msg.edit(primary_text, reply_markup=sample_btn)
                except Exception: pass
                AppState.status_snapshot = secondary_text
                
            if time.time() - wait_start > MAX_WAIT_SEC:
                try:
                    os.killpg(os.getpgid(cut_proc.pid), signal.SIGKILL)
                except Exception:
                    pass
                try:
                    return await status_msg.edit(
                        "⚠️ Sample cut timed out.\n"
                        "The HTTP seek may have stalled — please try again."
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    try: return await status_msg.edit("⚠️ Sample cut timed out.\nThe HTTP seek may have stalled — please try again.")
                    except: pass
                except Exception:
                    pass
                return
                
            await asyncio.sleep(0.5)

        async with AppState.process_lock:
            if AppState.current_process == cut_proc:
                AppState.current_process = None
                
        if proxy_server is not None:
            try:
                proxy_server.close()
                await proxy_server.wait_closed()
            except Exception:
                pass
            proxy_server = None
            
        if AppState.cancel_task: raise asyncio.CancelledError()

        gen_elapsed = int(time.time() - gen_start)
            
        if not os.path.exists(sample_out) or os.path.getsize(sample_out) < 4096:
            try:
                return await status_msg.edit("⚠️ Sample output is empty or corrupt. Please try again.")
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try: return await status_msg.edit("⚠️ Sample output is empty or corrupt. Please try again.")
                except: pass
            except Exception:
                pass
            return

        # ---------- THUMBNAIL GENERATION ----------
        if actual_thumb is None:
            for seek_t in (5, 3, 1, 0):
                if seek_t >= SAMPLE_DURATION: continue
                candidate = await take_screen_shot(sample_out, Config.THUMB_DIR, seek_t)
                if candidate and os.path.exists(candidate) and os.path.getsize(candidate) > 1024:
                    gen_thumb = candidate
                    actual_thumb = gen_thumb
                    break

        # ---------- EXTRACT DIMENSIONS ----------
        vid_width = getattr(media, 'width', 0)
        vid_height = getattr(media, 'height', 0)
        
        if not vid_width or not vid_height:
            try:
                probe = await asyncio.create_subprocess_exec(
                    "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", sample_out,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
                )
                stdout, _ = await asyncio.wait_for(probe.communicate(), timeout=5)
                dim_out = stdout.decode().strip().split('\n')[0].split('x')
                if len(dim_out) == 2:
                    vid_width, vid_height = int(dim_out[0]), int(dim_out[1])
            except Exception:
                pass
                
        vid_width = vid_width or 1280
        vid_height = vid_height or 720

        # ---------- UPLOAD ----------
        current_phase = "Uploading"
        if 'secondary_text' in locals():
            AppState.status_snapshot = secondary_text.replace("Sample Generating", current_phase)
            
        try:
            await status_msg.edit(Localisation.SAMPLE_UPLOADING, reply_markup=sample_btn)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try: await status_msg.edit(Localisation.SAMPLE_UPLOADING, reply_markup=sample_btn)
            except: pass
        except Exception:
            pass
        
        caption = (
            f"✅ <b>Successfully Extracted</b> `{SAMPLE_DURATION}s` <b>From {cut_str} Of</b> `{AppState.active_file_name}` <b>In {gen_elapsed} Seconds.</b>\n\n"
            f"<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
        )
        
        upload_start  = time.time()
        last_up_time  = [time.time()]
        
        await active_client.send_video(
            chat_id=status_msg.chat.id,
            video=sample_out,
            caption=caption,
            thumb=actual_thumb,
            width=vid_width,
            height=vid_height,
            duration=SAMPLE_DURATION,
            supports_streaming=True,
            progress=progress_bar,
            progress_args=("Uploading", status_msg, upload_start, last_up_time),
            reply_to_message_id=target_message.id,
        )
        try: await status_msg.delete()
        except Exception: pass

    except asyncio.CancelledError:
        await abort_current_task(status_msg, probe_path, sample_out, chat_id=target_message.chat.id)
    except Exception as e:
        logger.error("[SAMPLEGEN ERROR] %s\n%s", e, traceback.format_exc())
        try: await status_msg.edit(f"❌ **Sample Generation Error:**\n`{e}`")
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try: await status_msg.edit(f"❌ **Sample Generation Error:**\n`{e}`")
            except: pass
        except Exception: pass
    finally:
        if proxy_server is not None:
            try:
                proxy_server.close()
                await proxy_server.wait_closed()
            except Exception:
                pass
            proxy_server = None
            
        for path in filter(None, [probe_path, sample_out]):
            try:
                if os.path.exists(path): os.remove(path)
            except Exception: pass
                
        if gen_thumb and os.path.exists(gen_thumb) and gen_thumb != custom_thumb:
            try:
                os.remove(gen_thumb)
            except Exception: pass
                
        AppState.task_state       = TaskState.IDLE
        AppState.task_kind        = "compress"
        AppState.active_file_name = "None"
        AppState.active_origin_msg  = None
        AppState.active_status_msg  = None
        AppState.status_snapshot  = ""
        AppState.cancel_task      = False
        async with AppState.process_lock:
            AppState.current_process = None

@bot_app.on_message(filters.command("samplegen"))
async def samplegen_cmd(client, message):
    if not is_sudo(message): return await message.reply(UNAUTH_MSG)
    if AppState.task_state != TaskState.IDLE or not queue.empty(): return await message.reply(Localisation.SAMPLE_BUSY)
    if not message.reply_to_message: return await message.reply("⚠️ Please reply to a video to generate a sample.")
    
    if getattr(message.reply_to_message, "audio", None) or getattr(message.reply_to_message, "voice", None):
        await send_log(f"⚠️ **Abuse Warning:** User @{message.from_user.username} tried to use /samplegen on an Audio file.")
        return await message.reply("⚠️ `/samplegen` only works on Videos, not Audio files!")
        
    if not getattr(message.reply_to_message, "video", None) and not getattr(message.reply_to_message, "document", None):
        return await message.reply("⚠️ Please reply to a video or document to generate a sample.")
        
    msg = await message.reply("⏳ **Initializing Fast Sample Generator...** 📡\n")
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
    msg = await message.reply("🔄 **Restarting...**")
    
    if os.path.exists(".git"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "pull",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)
        except Exception as e:
            logger.error(f"❎ **Oops...!! Failed to load the latest data...** ❎ | Reason: {e}")
            
    restart_path = os.path.join(Config.ENV_DIR, "restart.json")
    with open(restart_path, "w") as f: json.dump({"chat_id": msg.chat.id, "message_id": msg.id}, f)
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
    asyncio.create_task(delete_message_later(msg, 30))

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
        return asyncio.create_task(delete_message_later(msg, 30))
        
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes ✅", callback_data="delthumb_yes"), InlineKeyboardButton("No ❌", callback_data="delthumb_no")]])
    msg = await message.reply(Localisation.THUMB_WARNING, reply_markup=btn)
    asyncio.create_task(delete_message_later(msg, 30))

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
        eval_path = os.path.join(Config.ENV_DIR, "eval.txt")
        with open(eval_path, "w+", encoding="utf8") as out_file: out_file.write(str(final_output))
        await message.reply_document(document=eval_path, caption=cmd[:100], disable_notification=True)
        os.remove(eval_path); await msg.delete()
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
    asyncio.create_task(delete_message_later(msg, 30))

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