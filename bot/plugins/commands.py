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
import subprocess
import re 
import psutil
import html
from collections import OrderedDict
from pyrogram.enums import ButtonStyle
from pyrogram import filters
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, ReplyParameters
from bot import bot_app, user_app, config_data, logger
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import AppState, TaskState, queue, START_TIME, get_readable_time, send_log, get_file_info, kill_running_process, delete_message_later, get_network_io, download_media_chunk, format_mediainfo_output
from bot.helper_funcs.download import get_graph_link
from bot.helper_funcs.display_progress import humanbytes, make_bar, time_formatter, render_active_status, get_sys_stats, progress_bar
from bot.plugins.call_back_button_handler import get_bsetting_menu
from bot.helper_funcs.ffmpeg import abort_current_task, take_screen_shot, start_tg_http_proxy, _find_free_port

UNAUTH_MSG = "<b>You are not allowed to do that 🤭</b>"
SPEEDTEST_LOCK = asyncio.Lock()
BACKGROUND_TASKS = set()
MESSAGE_LOCKS = {}
LAST_SENT_TEXT = OrderedDict()
ACTIVE_CMDS = {}

async def singleton_clear(chat_id, cmd):
    if chat_id in ACTIVE_CMDS and cmd in ACTIVE_CMDS[chat_id]:
        try: await bot_app.delete_messages(chat_id, [ACTIVE_CMDS[chat_id][cmd]["u"], ACTIVE_CMDS[chat_id][cmd]["b"]])
        except Exception: pass
def singleton_set(chat_id, cmd, u_id, b_id):
    if chat_id not in ACTIVE_CMDS: ACTIVE_CMDS[chat_id] = {}
    ACTIVE_CMDS[chat_id][cmd] = {"u": u_id, "b": b_id}

def get_msg_lock(msg_id):
    if len(MESSAGE_LOCKS) > 500:
        idle_locks = [k for k, v in list(MESSAGE_LOCKS.items()) if not v.locked()]
        for k in idle_locks[:50]:
            MESSAGE_LOCKS.pop(k, None)

    return MESSAGE_LOCKS.setdefault(msg_id, asyncio.Lock())

def _cleanup_task(task):
    BACKGROUND_TASKS.discard(task)
    try:
        exc = task.exception()
        if exc:
            logger.error(f"Background task failed: {exc}", exc_info=exc)
    except asyncio.CancelledError:
        pass

def spawn_temporary_task(coro, max_timeout=3600):
    async def watchdog():
        try:
            await asyncio.wait_for(coro, timeout=max_timeout)
        except asyncio.TimeoutError:
            logger.warning("A background task was safely terminated after reaching the 1-hour limit.")
        except asyncio.CancelledError:
            pass
            
    task = asyncio.create_task(watchdog())
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(_cleanup_task)
    return task

def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    auth_users = config_data.get("AUTH_USERS", [])
    owner_id = config_data.get("OWNER_ID", 0)
    
    if isinstance(auth_users, str):
        try: auth_users = json.loads(auth_users)
        except Exception: auth_users = []
        
    if not isinstance(auth_users, list):
        auth_users = [auth_users] if auth_users else []
        
    return user_id in auth_users or user_id == owner_id

def is_owner(message):
    user_id = message.from_user.id if message.from_user else 0
    return user_id == config_data.get("OWNER_ID", 0)

def get_uptime():
    uptime_ms = int((time.time() - START_TIME) * 1000)
    return get_readable_time(uptime_ms)

async def safe_delete(msg, log_context="Message"):
    """Enterprise helper to silently delete message objects without log spam."""
    if not msg: 
        return
    try: await msg.delete()
    except Exception as e: logger.debug(f"{log_context} deletion failed: {e}")

async def safe_delete_by_id(client, chat_id, msg_id, log_context="Message ID"):
    """Enterprise helper to cleanly delete messages by ID without wasting API GET calls."""
    if not msg_id: 
        return
    try: await client.delete_messages(chat_id=chat_id, message_ids=msg_id)
    except Exception as e: logger.debug(f"{log_context} deletion failed: {e}")

async def auto_clean(msg, message):
    await asyncio.sleep(30)
    if AppState.task_state == TaskState.IDLE and queue.qsize() == 0:
        await safe_delete(msg, "auto_clean msg")
        await safe_delete(message, "auto_clean user message")

@bot_app.on_message(filters.command("start"))
async def start_cmd(client, message): 
    await singleton_clear(message.chat.id, "start")
    btn = InlineKeyboardMarkup([[
        InlineKeyboardButton("Donate Me Some Bucks.. 🥺💰", url="https://t.me/Subhasish_bot", style=ButtonStyle.SUCCESS)
    ]])
    msg = await bot_app.send_message(
        message.chat.id, 
        Localisation.START_TEXT, 
        reply_markup=btn,
        reply_parameters=ReplyParameters(message_id=message.id)
    )
    singleton_set(message.chat.id, "start", message.id, msg.id)

@bot_app.on_message(filters.command("help"))
async def help_cmd(client, message): 
    await singleton_clear(message.chat.id, "help")
    msg = await bot_app.send_message(
        message.chat.id, 
        Localisation.HELP_TEXT,
        reply_parameters=ReplyParameters(message_id=message.id)
    )
    singleton_set(message.chat.id, "help", message.id, msg.id)
    spawn_temporary_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    await singleton_clear(message.chat.id, "ping")
    start_t = time.time()
    msg = await bot_app.send_message(
        message.chat.id, 
        "...",
        reply_parameters=ReplyParameters(message_id=message.id)
    )
    singleton_set(message.chat.id, "ping", message.id, msg.id)
    end_t = time.time()
    ping_ms = round((end_t - start_t) * 1000)
    uptime_str = get_uptime()
    
    git_info = ""
    if os.path.exists(".git"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "-c", "safe.directory=*", "log", "-1", "--format=%cd", "--date=format:%d/%m/%Y|%I:%M %p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            try:
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
                if proc.returncode is None: proc.kill(); await proc.wait()
        except Exception:
            pass
            
    text = f"📶 <b>Pɪɴɢ =</b> {ping_ms}ms\n⏰ <b>ᴜᴘᴛɪᴍᴇ:</b> {uptime_str}"
    if git_info:
        text += f"\n\n{git_info}"
        
    await msg.edit_text(text)
    spawn_temporary_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("settings"))
async def settings_cmd(client, message):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
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
    await bot_app.send_message(message.chat.id, text, reply_parameters=ReplyParameters(message_id=message.id))

async def update_setting(message, key, display_name):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if len(message.command) < 2: 
        msg = await bot_app.send_message(message.chat.id, f"Current {display_name}: `{config_data.get(key)}`", reply_parameters=ReplyParameters(message_id=message.id))
        return spawn_temporary_task(auto_clean(msg, message))
    val = message.command[1]
    if str(config_data.get(key)) == str(val): 
        msg = await bot_app.send_message(message.chat.id, f"⚠️ {display_name} is already set to `{val}`", reply_parameters=ReplyParameters(message_id=message.id))
        return spawn_temporary_task(auto_clean(msg, message))
    config_data[key] = val
    Config.save_config(config_data)
    msg = await bot_app.send_message(message.chat.id, f"✅ {display_name} successfully updated to `{val}`.", reply_parameters=ReplyParameters(message_id=message.id))
    spawn_temporary_task(auto_clean(msg, message))

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
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        else:
            queue.task_done()
            
    msg = await bot_app.send_message(message.chat.id, Localisation.QUEUE_CLEARED, reply_parameters=ReplyParameters(message_id=message.id))
    spawn_temporary_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("cancel"))
async def cancel_cmd(client, message):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if AppState.task_state == TaskState.IDLE: 
        msg = await bot_app.send_message(message.chat.id, Localisation.NO_ACTIVE_TASK, reply_parameters=ReplyParameters(message_id=message.id))
        return spawn_temporary_task(auto_clean(msg, message))
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes ✅", callback_data="confirm_cancel_yes", style=ButtonStyle.SUCCESS), InlineKeyboardButton("No ❌", callback_data="confirm_cancel_no", style=ButtonStyle.DANGER)]])
    
    msg = await bot_app.send_message(
        message.chat.id, 
        Localisation.CANCEL_PROMPT, 
        reply_markup=btn, 
        reply_parameters=ReplyParameters(message_id=message.id)
    )
    spawn_temporary_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("log"))
async def log_cmd(client, message):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    msg = await bot_app.send_message(message.chat.id, "⏳ Fetching bot logs...", reply_parameters=ReplyParameters(message_id=message.id))
    try:
        log_path = os.path.join(Config.ENV_DIR, "bot.log")
        if not os.path.exists(log_path): return await msg.edit_text("⚠️ Log file is empty or not yet created.")
        
        with open(log_path, "r") as f: log_data = f.read()[-30000:] 
        if not log_data: return await msg.edit_text("⚠️ Log file is empty.")
        
        content_json = []
        content_json.append({"tag": "pre", "children": [log_data]})
        
        link = await get_graph_link(content_json, "Subhasish Encoder Logs", "Subhasish Encoder")
        await msg.edit_text(f"📝 **Bot Logs:**\n{link}")
    except Exception as e: await msg.edit_text(f"❌ Failed to fetch logs: {e}")

@bot_app.on_message(filters.command("mediainfo"))
async def mediainfo_cmd(client, message):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if not message.reply_to_message or not getattr(message.reply_to_message, 'video', None) and not getattr(message.reply_to_message, 'document', None):
        return await bot_app.send_message(message.chat.id, "⚠️ Reply to a video or document to get its MediaInfo.", reply_parameters=ReplyParameters(message_id=message.id))
        
    msg = await bot_app.send_message(message.chat.id, "📝 Probing MediaInfo...", reply_parameters=ReplyParameters(message_id=message.id))
    chunk_path = f"/tmp/probe_{uuid.uuid4().hex}.mkv"
    try:
        active_client = user_app if user_app else bot_app
        await download_media_chunk(active_client, message.reply_to_message, chunk_path, limit_bytes=25 * 1024 * 1024)
            
        process = await asyncio.create_subprocess_exec(
            "mediainfo", chunk_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True 
        )
        try: stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        except asyncio.TimeoutError:
            raise Exception("MediaInfo Process Timed Out")
        finally:
            if process.returncode is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError: pass
                except Exception as e: logger.debug(f"MediaInfo kill failed: {e}")
                try: await asyncio.wait_for(process.wait(), timeout=5.0)
                except Exception as e: logger.debug(f"MediaInfo wait timeout/failed: {e}")

        raw_info = stdout.decode('utf-8', errors='replace').strip()
        size_str, _ = get_file_info(message.reply_to_message)
        real_name = getattr(message.reply_to_message.video or message.reply_to_message.document, 'file_name', 'video.mp4')
        content_json = format_mediainfo_output(raw_info, real_name, size_str)
            
        link = await get_graph_link(content_json, title="Subhasish Encoder Mediainfo", author="Subhasish Encoder")
        await msg.edit_text(f"📊 **MediaInfo Link:**\n{link}")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")
    finally:
        if os.path.exists(chunk_path):
            try: os.remove(chunk_path)
            except Exception as e: logger.debug(f"Failed to remove probe chunk: {e}")

async def safe_edit(msg, text, **kwargs):
    if not msg or not getattr(msg, "id", None): 
        return

    msg_id = msg.id

    markup_str = str(kwargs.get('reply_markup', ''))
    cache_key = f"{text}_{markup_str}"

    if LAST_SENT_TEXT.get(msg_id) == cache_key:
        LAST_SENT_TEXT.move_to_end(msg_id)
        return

    if len(LAST_SENT_TEXT) > 500:
        LAST_SENT_TEXT.popitem(last=False)

    lock = get_msg_lock(msg_id)

    try:
        async with lock:
            await asyncio.wait_for(msg.edit_text(text, **kwargs), timeout=10.0)
            LAST_SENT_TEXT[msg_id] = cache_key
    except MessageNotModified:
        LAST_SENT_TEXT[msg_id] = cache_key
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        pass
    except FloodWait as e:
        wait_time = int(getattr(e, "value", getattr(e, "x", 5)))
        for _ in range(wait_time):
            if AppState.cancel_task:
                raise asyncio.CancelledError()
            await asyncio.sleep(1)
        try:
            async with lock:
                await asyncio.wait_for(msg.edit_text(text, **kwargs), timeout=10.0)
                LAST_SENT_TEXT[msg_id] = cache_key
        except MessageNotModified:
            LAST_SENT_TEXT[msg_id] = cache_key
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            pass
        except Exception as e: 
            error_str = str(e).upper()
            if "MESSAGE_ID_INVALID" in error_str or "DELETED" in error_str:
                LAST_SENT_TEXT.pop(msg_id, None)
                MESSAGE_LOCKS.pop(msg_id, None)
            else:
                logger.exception(f"safe_edit recovery failed: {e}")
    except Exception as e:
        error_str = str(e).upper()
        if "MESSAGE_ID_INVALID" in error_str or "DELETED" in error_str:
            LAST_SENT_TEXT.pop(msg_id, None)
            MESSAGE_LOCKS.pop(msg_id, None)
        else:
            logger.exception(f"safe_edit initial edit failed: {e}")

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
    
    sample_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running", style=ButtonStyle.DANGER)]])
    
    try:
        active_client = user_app if user_app else bot_app
        if not media:
            await safe_edit(status_msg, "⚠️ No media found on this message.")
            return
        file_size: int = media.file_size or 0

        # ---------- RESOLVE DURATION ----------
        total_duration = float(getattr(media, "duration", 0) or 0)
        
        if total_duration < 1.0:
            await safe_edit(status_msg, Localisation.SAMPLE_PROBING, reply_markup=sample_btn)
            probe_path = f"/tmp/probe_{uuid.uuid4().hex[:10]}.mkv"
            await download_media_chunk(active_client, target_message, probe_path, limit_bytes=8 * 1024 * 1024)
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
            await safe_edit(
                status_msg, 
                "⚡️ **Fast Sample Mode Active**\n📡 Duration from metadata — probe step skipped!\n",
                reply_markup=sample_btn
            )

        SAMPLE_DURATION = 30
        MIN_LEN = SAMPLE_DURATION + 15
        
        if total_duration < MIN_LEN:
            await safe_edit(
                status_msg, 
                f"❎**ᴠɪᴅᴇᴏ ɪs ᴛᴏᴏ sʜᴏʀᴛ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀ** `{SAMPLE_DURATION}s` **sᴀᴍᴘʟᴇ, ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ** `{MIN_LEN}s` **ᴛɪᴍᴇ ғᴏʀ ᴛʜɪs** `{int(total_duration)}s` **ᴅᴜʀᴀᴛɪᴏɴ ᴠɪᴅᴇᴏ, ᴜsᴇ ᴀɴᴏᴛʜᴇʀ ᴠɪᴅᴇᴏ.**❎"
            )
            return
            
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
            "-map", "0",
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
        secondary_text = ""
        
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
                
                await safe_edit(status_msg, primary_text, reply_markup=sample_btn)
                AppState.status_snapshot = secondary_text
                
            if time.time() - wait_start > MAX_WAIT_SEC:
                try: os.killpg(os.getpgid(cut_proc.pid), signal.SIGKILL)
                except Exception: pass
                
                await safe_edit(status_msg, "⚠️ Sample cut timed out.\nThe HTTP seek may have stalled — please try again.")
                return
                
            await asyncio.sleep(0.5)

        async with AppState.process_lock:
            if AppState.current_process == cut_proc:
                AppState.current_process = None
                
        if proxy_server is not None:
            try:
                proxy_server.close()
                await proxy_server.wait_closed()
            except Exception as e:
                logger.debug(f"Proxy server close failed: {e}")
            proxy_server = None
            
        if AppState.cancel_task: raise asyncio.CancelledError()

        gen_elapsed = int(time.time() - gen_start)
            
        if not os.path.exists(sample_out) or os.path.getsize(sample_out) < 4096:
            await safe_edit(status_msg, "⚠️ Sample output is empty or corrupt. Please try again.")
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
            except Exception as e:
                logger.debug(f"Dimension extraction failed: {e}")
                
        vid_width = vid_width or 1280
        vid_height = vid_height or 720

        # ---------- UPLOAD ----------
        current_phase = "Uploading"
        if secondary_text:
            AppState.status_snapshot = secondary_text.replace("Sample Generating", current_phase)
            
        await safe_edit(status_msg, Localisation.SAMPLE_UPLOADING, reply_markup=sample_btn)
        
        caption = (
            f"✅ <b>Successfully Extracted</b> `{SAMPLE_DURATION}s` <b>From {cut_str} Of</b> `{AppState.active_file_name}` <b>In {gen_elapsed} Seconds.</b>\n\n"
            f"<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
        )
        
        upload_start  = time.time()
        last_up_time  = [time.time()]
        
        upload_task = asyncio.create_task(
            active_client.send_video(
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
                reply_parameters=ReplyParameters(message_id=target_message.id),
            )
        )
        
        while not upload_task.done():
            if AppState.cancel_task:
                upload_task.cancel()
                try: 
                    await asyncio.wait_for(upload_task, timeout=10)
                except Exception as e: 
                    logger.debug(f"Upload task teardown exception caught: {e}")
                raise asyncio.CancelledError("Upload phase cancelled by user")
            await asyncio.sleep(0.5)
            
        await upload_task
        try: await status_msg.delete()
        except Exception as e: logger.debug(f"Status msg deletion failed: {e}")

    except asyncio.CancelledError:
        await abort_current_task(status_msg, probe_path, sample_out, chat_id=target_message.chat.id)
    except Exception as e:
        logger.error("[SAMPLEGEN ERROR] %s\n%s", e, traceback.format_exc())
        await safe_edit(status_msg, f"❌ **Sample Generation Error:**\n`{e}`")
    finally:
        if proxy_server is not None:
            try:
                proxy_server.close()
                await proxy_server.wait_closed()
            except Exception as e:
                logger.debug(f"Final proxy cleanup failed: {e}")
            proxy_server = None
            
        for path in filter(None, [probe_path, sample_out]):
            try:
                if os.path.exists(path): os.remove(path)
            except Exception as e: 
                logger.debug(f"File cleanup failed for {path}: {e}")
                
        if gen_thumb and os.path.exists(gen_thumb) and gen_thumb != custom_thumb:
            try:
                os.remove(gen_thumb)
            except Exception as e: 
                logger.debug(f"Thumb cleanup failed: {e}")
                
        AppState.task_state       = TaskState.IDLE
        AppState.task_kind        = "compress"
        AppState.active_file_name = "None"
        AppState.active_origin_msg  = None
        AppState.active_status_msg  = None
        AppState.status_snapshot  = ""
        AppState.cancel_task      = False
        async with AppState.process_lock:
            AppState.current_process = None
            
        if status_msg and getattr(status_msg, "id", None):
            LAST_SENT_TEXT.pop(status_msg.id, None)
            MESSAGE_LOCKS.pop(status_msg.id, None)

@bot_app.on_message(filters.command("samplegen"))
async def samplegen_cmd(client, message):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if AppState.task_state != TaskState.IDLE or not queue.empty(): 
        return await bot_app.send_message(message.chat.id, Localisation.SAMPLE_BUSY, reply_parameters=ReplyParameters(message_id=message.id))
    if not message.reply_to_message: 
        return await bot_app.send_message(message.chat.id, "⚠️ Please reply to a video to generate a sample.", reply_parameters=ReplyParameters(message_id=message.id))
    
    if getattr(message.reply_to_message, "audio", None) or getattr(message.reply_to_message, "voice", None):
        await send_log(f"⚠️ **Abuse Warning:** User @{message.from_user.username} tried to use /samplegen on an Audio file.")
        return await bot_app.send_message(message.chat.id, "⚠️ `/samplegen` only works on Videos, not Audio files!", reply_parameters=ReplyParameters(message_id=message.id))
        
    if not getattr(message.reply_to_message, "video", None) and not getattr(message.reply_to_message, "document", None):
        return await bot_app.send_message(message.chat.id, "⚠️ Please reply to a video or document to generate a sample.", reply_parameters=ReplyParameters(message_id=message.id))
        
    if getattr(message.reply_to_message, "document", None):
        mime = message.reply_to_message.document.mime_type
        if mime and not mime.startswith("video/"):
            return await bot_app.send_message(message.chat.id, "⚠️ The replied document is not a valid video format! (e.g. zip/pdf)", reply_parameters=ReplyParameters(message_id=message.id))
    msg = await bot_app.send_message(message.chat.id, "⏳ **Initializing Fast Sample Generator...** 📡\n", reply_parameters=ReplyParameters(message_id=message.id))
    spawn_temporary_task(generate_sample_background(client, message.reply_to_message, msg))

@bot_app.on_message(filters.command("clearlocals"))
async def clearlocals_cmd(client, message):
    if not is_sudo(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    try:
        freed = gc.collect()
        await bot_app.send_message(message.chat.id, f"✅ **Garbage Collection Triggered!**\nFreed `{freed}` unused Python objects from memory.", reply_parameters=ReplyParameters(message_id=message.id))
    except Exception as e:
        await bot_app.send_message(message.chat.id, f"❌ **Failed to run GC:** {e}", reply_parameters=ReplyParameters(message_id=message.id))

@bot_app.on_message(filters.command("restart"))
async def restart_cmd(client, message):
    if not is_sudo(message): return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    msg = await bot_app.send_message(message.chat.id, "🔄 **Restarting...**", reply_parameters=ReplyParameters(message_id=message.id))
    if os.path.exists(".git"):
        try:
            proc = await asyncio.create_subprocess_exec("git", "-c", "safe.directory=*", "pull", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            git_out = stdout.decode().strip()
            logger.info(f"Git pull output:\n{git_out}")

            if proc.returncode != 0:
                await msg.edit_text(f"⚠️ **Git Pull Failed:**\n`{git_out[-1000:]}`\n\n☑️ Restarting Anyway...")
                await asyncio.sleep(2)
        except asyncio.TimeoutError:
            try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception as e: logger.debug(f"Git pull kill failed: {e}")
            try: await proc.wait()
            except: pass
            logger.error("Git pull timed out and was killed.")
            await msg.edit_text("⚠️ **Git Pull Timed Out!**\n☑️ Restarting Anyway...")
            await asyncio.sleep(2)
        except Exception as e:
            try:
                if 'proc' in locals() and proc.returncode is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    await proc.wait()
            except: pass
            logger.error(f"❎ **Oops...!! Failed to load the latest data...** ❎ | Reason: {e}")
            await msg.edit_text(f"⚠️ **Git Pull Error:**\n`{e}`\n\nRestarting Anyway...")
            await asyncio.sleep(2)
            
    restart_path = os.path.join(Config.ENV_DIR, "restart.json")
    with open(restart_path, "w") as f: 
        json.dump({"chat_id": msg.chat.id, "message_id": msg.id}, f)
        f.flush()
        os.fsync(f.fileno())
# 🛑 ZOMBIE PREVENTION: Kill all heavy child processes before os.execl
    AppState.cancel_task = True
    await kill_running_process()
    for proc_name in ["ffmpeg", "ffprobe", "mkvmerge"]:
        try: p = await asyncio.create_subprocess_exec("pkill", "-9", "-f", proc_name, stderr=asyncio.subprocess.DEVNULL); await p.wait()
        except Exception: pass

    os.execl(sys.executable, sys.executable, "-m", "bot")

@bot_app.on_message(filters.command("cancelall"))
async def cancel_all_cmd(client, message):
    if not is_owner(message): return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    
    is_idle = (AppState.task_state == TaskState.IDLE and queue.empty())
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        else:
            queue.task_done()
    
    AppState.cancel_task = True 
    await kill_running_process()
    AppState.merge_sessions.clear()

    if AppState.active_status_msg:
        try: await AppState.active_status_msg.delete()
        except Exception as e: logger.debug(f"cancelall status deletion failed: {e}")

    MESSAGE_LOCKS.clear()
    LAST_SENT_TEXT.clear()
        
    msg = await bot_app.send_message(message.chat.id, "⚠️ **ALL TASKS CANCELLED AND QUEUE CLEARED.**", reply_parameters=ReplyParameters(message_id=message.id))
    if is_idle: spawn_temporary_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("setthumbnail"))
async def set_thumb(client, message):
    if not is_owner(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if not message.reply_to_message or not message.reply_to_message.photo: 
        return await bot_app.send_message(message.chat.id, Localisation.INVALID_THUMB, reply_parameters=ReplyParameters(message_id=message.id))
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    await message.reply_to_message.download(file_name=path)

    await bot_app.send_message(message.chat.id, Localisation.THUMB_ADDED, reply_parameters=ReplyParameters(message_id=message.id))

@bot_app.on_message(filters.command("delthumbnail"))
async def del_thumb_cmd(client, message):
    if not is_owner(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    await singleton_clear(message.chat.id, "delthumbnail")
    path = os.path.join(Config.THUMB_DIR, f"{message.from_user.id}.jpg")
    if not os.path.exists(path): 
        msg = await bot_app.send_message(message.chat.id, "⚠️ You don't have a custom thumbnail set.", reply_parameters=ReplyParameters(message_id=message.id))
        singleton_set(message.chat.id, "delthumbnail", message.id, msg.id)
        return spawn_temporary_task(auto_clean(msg, message))

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes ✅", callback_data="delthumb_yes", style=ButtonStyle.SUCCESS), InlineKeyboardButton("No ❌", callback_data="delthumb_no", style=ButtonStyle.DANGER)]])
    msg = await bot_app.send_message(message.chat.id, Localisation.THUMB_WARNING, reply_markup=btn, reply_parameters=ReplyParameters(message_id=message.id))
    singleton_set(message.chat.id, "delthumbnail", message.id, msg.id)
    return spawn_temporary_task(auto_clean(msg, message))

@bot_app.on_message(filters.command("speedtest"))
async def speedtest_cmd(client, message):
    if not is_sudo(message): return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if SPEEDTEST_LOCK.locked(): return await bot_app.send_message(message.chat.id, "⚠️ A Speedtest Is Already Running. 𝘗𝘭𝘦𝘢𝘴𝘦 𝘞𝘢𝘪𝘵...!!", reply_parameters=ReplyParameters(message_id=message.id))
    msg = await bot_app.send_message(message.chat.id, "⏳ **Running Server Speedtest...**\n✨ 𝘛𝘩𝘪𝘴 𝘛𝘢𝘬𝘦𝘴 𝘈𝘣𝘰𝘶𝘵 30 𝘚𝘦𝘤𝘰𝘯𝘥𝘴...!! ✨", reply_parameters=ReplyParameters(message_id=message.id))
    try:
        async with SPEEDTEST_LOCK:
            res = await asyncio.to_thread(run_speedtest)
        d_speed = humanbytes(res.get('download', {}).get('bandwidth', 0))
        u_speed = humanbytes(res.get('upload', {}).get('bandwidth', 0))
        idle_latency = round(res.get('ping', {}).get('latency', 0))
        dl_latency = round(res.get('download', {}).get('latency', {}).get('iqm', 0))
        ul_latency = round(res.get('upload', {}).get('latency', {}).get('iqm', 0))
        ping = res.get('ping', {}).get('latency', 0)
        ping_str = f"{float(ping):.3f}"
        packet_loss = res.get('packetLoss', 0.0)
        packet_loss_str = f"{float(packet_loss if packet_loss is not None else 0.0):.1f}"
        server_location = res.get('server', {}).get('location', 'Unknown')
        server_country = res.get('server', {}).get('country', 'Unknown')
        app_name = res.get('app_name', 'Ookla Speedtest CLI')
        app_version = res.get('app_version', 'Unknown')

        text = (
            f"🚀 <u>**ＳＰＥＥＤＴＥＳＴ ＩＮＦＯ**</u>\n\n"
            f"<b><i>🌐 Connection Metrics</i></b>\n"
            f"🔻 **ᴅᴏᴡɴʟᴏᴀᴅ:** `{d_speed}/s`\n"
            f"🔺 **ᴜᴘʟᴏᴀᴅ:** `{u_speed}/s`\n\n"
            f"<b><i>⏱️ Latency & Performance</i></b>\n"
            f"💤 **ɪᴅʟᴇ:** `{idle_latency} ms`\n"
            f"⏬ **ᴅᴏᴡɴʟᴏᴀᴅ:** `{dl_latency} ms`\n"
            f"⏫ **ᴜᴘʟᴏᴀᴅ:** `{ul_latency} ms`\n"
            f"🛜 **ᴘɪɴɢ:** `{ping_str} ms`\n"
            f"📉 **ᴘᴀᴄᴋᴇᴛ ʟᴏss:** `{packet_loss_str}%`\n\n"
            f"<b><i>🗺️ Host Location</i></b>\n"
            f"🌍 **sᴇʀᴠᴇʀ:** `{server_location}, {server_country}`\n\n"
            f"<b><i>⚙️ Runner Details</i></b>\n"
            f"💻 **ᴀᴘᴘʟɪᴄᴀᴛɪᴏɴ:** `{app_name}`\n"
            f"🏷️ **ᴠᴇʀsɪᴏɴ:** `v{app_version}`"
        )
        await msg.edit_text(text)
    except Exception as e:
        await msg.edit_text(f"❌ **Speedtest Failed:** {e}")

def run_speedtest():
    app_name = "Ookla Speedtest CLI"
    app_version = "Unknown"
    try:
        v_cmd = ["speedtest", "--version"]
        v_proc = subprocess.Popen(v_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        v_stdout, _ = v_proc.communicate(timeout=10)
        v_text = v_stdout.decode('utf-8').strip().split('\n')[0]
        match = re.search(r"^(.*?)\s+([\d\.]+)", v_text)
        if match: app_name, app_version = match.group(1).strip(), match.group(2).strip()
    except Exception: pass
    cmd = ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise Exception("Speedtest CLI timed out after 60 seconds.")

    if process.returncode != 0: raise Exception(stderr.decode('utf-8').strip() or "Speedtest CLI failed.")
    res = json.loads(stdout.decode('utf-8'))
    res.pop('result', None); res.pop('interface', None); res.pop('isp', None)
    res['app_name'] = app_name; res['app_version'] = app_version
    return res

async def aexec(code, client, message):
    exec_vars = {}
    code_lines = "\n".join([f"    {line}" for line in code.split("\n")])
    exec_code = f"async def __aexec(client, message):\n{code_lines}"
    exec(exec_code, globals().copy(), exec_vars)
    return await exec_vars["__aexec"](client, message)

@bot_app.on_message(filters.command("exec"))
async def sh_handler(client, message):
    if not is_owner(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if len(message.text.split()) < 2: return
    
    cmd = message.text.split(maxsplit=1)[1]
    msg = await bot_app.send_message(message.chat.id, "📟 <b>Terminal:</b> <code>Processing...</code>", reply_parameters=ReplyParameters(message_id=message.id))
    
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        result = (stdout.decode() + stderr.decode()).strip() or "Success (No Output)"
    except asyncio.TimeoutError:
        try: os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception as e: logger.debug(f"exec timeout kill failed: {e}")
        try: await process.wait()
        except: pass
        result = "⚠️ EXEC TIMEOUT: Command ran for over 120 seconds and was killed to protect the event loop."
    except Exception as e:
        try:
            if 'process' in locals() and process.returncode is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                await process.wait()
        except: pass
        result = str(e)

    result = html.escape(result)
    final_output = f"<b>EXEC</b>: <code>{html.escape(cmd)}</code>\n\n<b>OUTPUT</b>:\n<code>{result}</code>"
    
    if len(final_output) > 4000:
        sh_path = os.path.join(Config.ENV_DIR, "exec.txt")
        with open(sh_path, "w+", encoding="utf8") as out_file: out_file.write(str(result))
        await bot_app.send_document(
            chat_id=message.chat.id,
            document=sh_path,
            caption=f"sh: {cmd[:100]}",
            disable_notification=True,
            reply_parameters=ReplyParameters(message_id=message.id)
        )
        os.remove(sh_path); await msg.delete()
    else:
        await msg.edit_text(final_output)

@bot_app.on_message(filters.command("eval"))
async def eval_handler(client, message):
    if not is_owner(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if not message.text or len(message.text.split()) < 2: return
    cmd = message.text.split(maxsplit=1)[1]
    msg = await bot_app.send_message(message.chat.id, "Processing...", reply_parameters=ReplyParameters(message_id=message.id))
    
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    redirected_error = sys.stderr = io.StringIO()
    stdout, stderr, exc = None, None, None
    
    try: 
        await asyncio.wait_for(aexec(cmd, client, message), timeout=120)
    except asyncio.TimeoutError:
        exc = "⚠️ EVAL TIMEOUT: Code execution exceeded 120 seconds and was forcefully terminated."
    except Exception: 
        exc = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    
    redirected_output.close()
    redirected_error.close()
    
    evaluation = html.escape(str(exc or stderr or stdout or "Success"))
    final_output = f"<b>EVAL</b>: <code>{html.escape(cmd)}</code>\n\n<b>OUTPUT</b>:\n<code>{evaluation.strip()}</code>\n"

    if len(final_output) > 4000:
        eval_path = os.path.join(Config.ENV_DIR, "eval.txt")
        with open(eval_path, "w+", encoding="utf8") as out_file: out_file.write(str(final_output))
        await bot_app.send_document(
            chat_id=message.chat.id,
            document=eval_path,
            caption=cmd[:100],
            disable_notification=True,
            reply_parameters=ReplyParameters(message_id=message.id)
        )
        os.remove(eval_path); await msg.delete()
    else: await msg.edit_text(final_output)

@bot_app.on_message(filters.command("broadcast"))
async def broadcast_cmd(client, message):
    if not is_owner(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    if len(message.command) < 2: 
        return await bot_app.send_message(message.chat.id, "⚠️ Usage: `/broadcast Your message here`", reply_parameters=ReplyParameters(message_id=message.id))
    
    b_msg = message.text.split(maxsplit=1)[1]
    success = 0
    failed = 0
    
    auth_list = config_data.get('AUTH_USERS', [])
    if isinstance(auth_list, str):
        try: auth_list = json.loads(auth_list)
        except Exception: auth_list = []
        
    await bot_app.send_message(message.chat.id, f"📣 **Broadcasting to {len(auth_list)} users...**", reply_parameters=ReplyParameters(message_id=message.id))
    
    for user_id in auth_list:
        try:
            await asyncio.wait_for(bot_app.send_message(user_id, f"📣 **Announcement from Admin:**\n\n{b_msg}"), timeout=10)
            success += 1
            await asyncio.sleep(0.5) 
        except FloodWait as fw:
            wait_time = getattr(fw, "value", getattr(fw, "x", 5))
            await asyncio.sleep(wait_time)
            try:
                await asyncio.wait_for(bot_app.send_message(user_id, f"📣 **Announcement from Admin:**\n\n{b_msg}"), timeout=10)
                success += 1
            except Exception as e: 
                logger.debug(f"Broadcast retry failed for {user_id}: {e}")
                failed += 1
        except Exception as e: 
            logger.debug(f"Broadcast failed for {user_id}: {e}")
            failed += 1
            
    msg = await bot_app.send_message(message.chat.id, f"✅ **Broadcast Complete!**\n\n🟢 **Success:** `{success}`\n🔴 **Failed:** `{failed}`", reply_parameters=ReplyParameters(message_id=message.id))
    spawn_temporary_task(delete_message_later(msg, 30))

@bot_app.on_message(filters.command("bsetting"))
async def bsetting_cmd(client, message):
    if not is_owner(message): 
        return await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
    await singleton_clear(message.chat.id, "bsetting")
    help_text = (
        "**⚙️ Bot Settings Menu**\n"
        "Click a variable below to change its value interactively.\n"
        "✨ 𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵 ✨"
    )
    msg = await bot_app.send_message(message.chat.id, help_text, reply_markup=get_bsetting_menu(), reply_parameters=ReplyParameters(message_id=message.id))
    singleton_set(message.chat.id, "bsetting", message.id, msg.id)

@bot_app.on_message(filters.text, group=1)
async def bsetting_input_catcher(client, message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    if user_id == 0:
        return
    
    try:
        async with AppState.state_lock:
            state_data = AppState.bsetting_state.get(user_id)

        if state_data and state_data.get("step") == "awaiting_value":
            if (message.text or "").startswith("/"):
                async with AppState.state_lock:
                    AppState.bsetting_state.pop(user_id, None)
                return

            key = state_data["key"]
            val = message.text.strip()

            async with AppState.state_lock:
                if user_id in AppState.bsetting_state:
                    AppState.bsetting_state[user_id]["msg_to_delete"] = message.id

            if str(config_data.get(key)) == str(val):
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"), InlineKeyboardButton("❌ Close", callback_data="bsetting_close", style=ButtonStyle.DANGER)]])
                msg = await bot_app.send_message(message.chat.id, f"⚠️ **{key}** is already set to `{val}`.", reply_markup=btn, reply_parameters=ReplyParameters(message_id=message.id))
                async with AppState.state_lock:
                    if user_id in AppState.bsetting_state:
                        AppState.bsetting_state[user_id]["bot_msg_to_delete"] = msg.id
                return

            async with AppState.state_lock:
                if user_id in AppState.bsetting_state:
                    AppState.bsetting_state[user_id]["pending_value"] = val
                    AppState.bsetting_state[user_id]["step"] = "confirming"

            sensitive_keys = ["API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID"]
            
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes ✅", callback_data="bsetting_confirm_yes", style=ButtonStyle.SUCCESS),
                 InlineKeyboardButton("No ❌", callback_data="bsetting_confirm_no", style=ButtonStyle.DANGER)],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"),
                 InlineKeyboardButton("❌ Close", callback_data="bsetting_close", style=ButtonStyle.DANGER)]
            ])

            if key in sensitive_keys: text = f"❓ **Confirm {key}**\n\nSensitive credential detected.\nDo you want to securely save this?"
            elif key == "USER_SESSION_STRING": text = f"❓ **Confirm Update**\n\nNew session string received.\nDo you want to securely save this?"
            elif key == "AS_DOCUMENT": text = f"❓ **Confirm Update**\n\nYou entered **{val}**.\n✨ 𝘖𝘯𝘭𝘺 𝘵𝘺𝘱𝘦 𝘛𝘳𝘶𝘦 𝘰𝘳 𝘍𝘢𝘭𝘴𝘦 ✨\n\nDo you want to save this?"
            else: text = f"❓ **Confirm Update**\n\nYou entered a new value for **{key}**:\n`{val}`\n\nDo you want to save this?"
                
            msg = await bot_app.send_message(message.chat.id, text, reply_markup=btn, reply_parameters=ReplyParameters(message_id=message.id))

            async with AppState.state_lock:
                if user_id in AppState.bsetting_state:
                    AppState.bsetting_state[user_id]["bot_msg_to_delete"] = msg.id
    except Exception as e:
        logger.error(f"[BSETTING CATCHER ERROR] {e}")