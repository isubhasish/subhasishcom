import os
import time
import uuid
import asyncio
import traceback
import signal
import re
from pyrogram import filters
from pyrogram.enums import ButtonStyle, ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from bot import bot_app, user_app, logger, config_data
from bot.config import Config
from bot.helper_funcs.utils import AppState, TaskState, get_file_info, download_media_chunk, get_ist, send_log, queue
from bot.helper_funcs.merge_utils import get_video_signature, compare_signatures, run_mkvmerge
from bot.plugins.commands import safe_edit, safe_delete
from bot.plugins.call_back_button_handler import safe_callback, is_sudo
from bot.helper_funcs.display_progress import progress_bar
from bot.helper_funcs.ffmpeg import take_screen_shot

UNAUTH_MSG = "<b>You are not allowed to do that 🤭</b>"

# ==========================================
# 🧠 SMART FILENAME PARSERS
# ==========================================
def natural_sort_key(msg):
    filename = getattr(msg.video or msg.document, "file_name", "") or ""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', filename)] + [msg.id]

def get_episode_identifier(filename: str):
    match = re.search(r'(?i)(?:s|season)\s*(\d+)\s*(?:e|ep|episode)\s*(\d+)', filename)
    if match:
        return f"S{int(match.group(1)):02d} EP{int(match.group(2)):02d}", int(match.group(2)), match.group(0)

    match = re.search(r'(?i)part[\s\.]*(\d+)', filename)
    if match:
        return f"Part {int(match.group(1))}", int(match.group(1)), match.group(0)

    match = re.search(r'(?i)(?:e|ep|episode)\s*(\d+)', filename)
    if match:
        return f"EP{int(match.group(1)):02d}", int(match.group(1)), match.group(0)

    temp = re.sub(r'(19|20)\d{2}', '', filename)
    match = re.search(r'(?<!\d)(\d{1,3})(?!\d)', temp)
    if match:
        return f"{int(match.group(1))}", int(match.group(1)), match.group(0)

    return None, None, None

# ==========================================
# 🎬 MERGE UI & EXECUTION LOGIC
# ==========================================

@bot_app.on_callback_query(filters.regex(r"^panel_merge_(.+)$"))
@safe_callback
async def init_merge_session(client, cb):
    tid = cb.matches[0].group(1)
    chat_id = cb.message.chat.id

    if not is_sudo(cb): 
        return await cb.answer("You are not allowed to do that 🤭", show_alert=True)

    async with AppState.state_lock:
        if AppState.task_state != TaskState.IDLE or not queue.empty():
            return await cb.answer("⚠️ Bot is currently busy processing other tasks. Please wait until it finishes.", show_alert=True)
            
        if len(AppState.merge_sessions) > 0 and chat_id not in AppState.merge_sessions:
            return await cb.answer("⚠️ Another user is currently building a merge queue. Please wait.", show_alert=True)
        task = AppState.pending_tasks.get(tid)
        if not task:
            return await cb.answer("⚠️ Task Expired", show_alert=True)

        AppState.pending_tasks.pop(tid, None)
    await cb.answer()
    await safe_edit(cb.message, "🛠 **Merge Session Started**\nCommands are hidden. Use the Buttons Below.", reply_markup=None)

    base_msg = task['msg']
    reply_params = ReplyParameters(message_id=base_msg.id)
    chunk_path = f"/tmp/probe_{uuid.uuid4().hex}.mkv"

    try:
        active_client = user_app if user_app else bot_app
        await download_media_chunk(active_client, base_msg, chunk_path, limit_bytes=15 * 1024 * 1024)
        
        sig_result = await get_video_signature(chunk_path)
        
        if "error" in sig_result:
            return await safe_edit(cb.message, f"❌ **Smart Detector Error:**\n`{sig_result['error']}`\n\nCannot use this file as a base for merging.")

        base_signature = sig_result["signature"]
        size_bytes = base_msg.video.file_size if base_msg.video else base_msg.document.file_size
        base_filename = getattr(base_msg.video or base_msg.document, "file_name", "") or ""
        ep_id, ep_num, _ = get_episode_identifier(base_filename)
        received_eps = [ep_id] if ep_id else []
        ep_numbers = [ep_num] if ep_num is not None else []
        expiry_time = time.time() + 1200
        received_str = ", ".join(received_eps) if received_eps else "1"
        
        text = (
            "<b>Total Videos :</b> 1\n"
            f"<b>Total Size:</b> {round(size_bytes/(1024*1024), 2)} MB\n"
            f"<b>Video Received:</b> {received_str}\n"
            "<b>Session Expires In:</b> 20m 00s\n\n"
            "<i><b>👇🏻 Now Send Me The Next Video 👇🏻</b></i>"
        )

        reply_kbd = ReplyKeyboardMarkup([[KeyboardButton("❌ ᴄᴀɴᴄᴇʟ ❌")]], resize_keyboard=True)
        status_msg = await bot_app.send_message(chat_id, text, reply_markup=reply_kbd, reply_parameters=reply_params)

        AppState.merge_sessions[chat_id] = {
            "base_signature": base_signature,
            "videos": [base_msg],
            "total_size_bytes": size_bytes,
            "status_msg": status_msg,
            "expiry_time": expiry_time,
            "received_eps": received_eps,
            "ep_numbers": ep_numbers
        }

        async def auto_delete_init_msg():
            await asyncio.sleep(5)
            await safe_delete(cb.message)
        asyncio.create_task(auto_delete_init_msg())

        async def auto_expire_session():
            await asyncio.sleep(1200) 
            if chat_id in AppState.merge_sessions:
                session = AppState.merge_sessions.pop(chat_id, None)
                if session:
                    try:
                        await bot_app.send_message(chat_id, "⚠️ **Merge Session Expired due to 20 minutes time limit.**", reply_markup=ReplyKeyboardRemove())
                        await safe_delete(session["status_msg"])
                        for msg in session["videos"]:
                            await safe_delete(msg)
                    except: pass
        asyncio.create_task(auto_expire_session())

    except Exception as e:
        logger.error(f"Merge Init Error: {e}")
        await safe_edit(cb.message, f"❌ **Error initializing merge:** `{e}`")
    finally:
        if os.path.exists(chunk_path):
            try: os.remove(chunk_path)
            except: pass

async def handle_merge_input(client, message):
    chat_id = message.chat.id
    session = AppState.merge_sessions.get(chat_id)
    if not session:
        return

    base_msg = session['videos'][0]
    reply_params = ReplyParameters(message_id=base_msg.id)

    temp_msg = await bot_app.send_message(
        chat_id, 
        "⏳ **Smart Detector Active:** Probing new video signature...",
        reply_parameters=ReplyParameters(message_id=message.id)
    )

    chunk_path = f"/tmp/probe_{uuid.uuid4().hex}.mkv"

    try:
        new_filename = getattr(message.video or message.document, "file_name", "") or ""
        ep_id, ep_num, _ = get_episode_identifier(new_filename)
        # ==========================================
        # ⚠️ DUPLICATE DETECTOR
        # ==========================================
        if ep_id and ep_id in session["received_eps"]:
            await safe_edit(temp_msg, f"⚠️ **Duplicate Detected!**\n\nYou already sent `{ep_id}`. This file has been ignored.")
            async def auto_delete_dup():
                await asyncio.sleep(5)
                await safe_delete(temp_msg)
                await safe_delete(message)
            asyncio.create_task(auto_delete_dup())
            return

        active_client = user_app if user_app else bot_app
        await download_media_chunk(active_client, message, chunk_path, limit_bytes=15 * 1024 * 1024)
        new_sig_result = await get_video_signature(chunk_path)

        if "error" in new_sig_result:
            await safe_edit(temp_msg, f"❌ **Smart Detector Error:**\n`{new_sig_result['error']}`\n\nThis video was rejected.")
            async def auto_delete_err():
                await asyncio.sleep(5)
                await safe_delete(temp_msg)
                await safe_delete(message)
            asyncio.create_task(auto_delete_err())
            return

        new_signature = new_sig_result["signature"]
        is_compatible, reason = compare_signatures(session["base_signature"], new_signature)
        
        if not is_compatible:
            await safe_edit(temp_msg, f"❌ **Incompatible Video Detected!**\n\n**Reason:** `{reason}`\n\nThis video was rejected.")
            async def auto_delete_incompatible():
                await asyncio.sleep(5)
                await safe_delete(temp_msg)
                await safe_delete(message)
            asyncio.create_task(auto_delete_incompatible())
            return

        if ep_id: session["received_eps"].append(ep_id)
        if ep_num is not None: session["ep_numbers"].append(ep_num)

        size_bytes = message.video.file_size if message.video else message.document.file_size
        session["videos"].append(message)
        session["total_size_bytes"] += size_bytes
        total_videos = len(session["videos"])
        total_size_mb = round(session["total_size_bytes"] / (1024 * 1024), 2)

        await safe_delete(temp_msg)
        await safe_delete(session["status_msg"])
        
        rem_sec = int(session["expiry_time"] - time.time())
        if rem_sec < 0: rem_sec = 0
        mins, secs = divmod(rem_sec, 60)
        
        received_str = ", ".join(session["received_eps"]) if session["received_eps"] else ", ".join([str(i+1) for i in range(total_videos)])
        
        text = (
            f"<b>Total Videos :</b> {total_videos}\n"
            f"<b>Total Size:</b> {total_size_mb} MB\n"
            f"<b>Video Received:</b> {received_str}\n"
            f"<b>Session Expires In:</b> {mins}m {secs:02d}s\n\n"
            "<i><b>👇🏻 Now Send Me The Next Video 👇🏻</b></i>"
        )

        reply_kbd = ReplyKeyboardMarkup([["🎬 ᴍᴇʀɢᴇ ᴠɪᴅᴇᴏs 🎬"], ["❌ ᴄᴀɴᴄᴇʟ ❌"]], resize_keyboard=True)
        new_status_msg = await bot_app.send_message(chat_id, text, reply_markup=reply_kbd, reply_parameters=reply_params)
        session["status_msg"] = new_status_msg

    except Exception as e:
        logger.error(f"Merge Input Error: {e}")
        await safe_edit(temp_msg, f"❌ **Error processing video:** `{e}`")
    finally:
        if os.path.exists(chunk_path):
            try: os.remove(chunk_path)
            except: pass

# ==========================================
# 🛑 REPLY KEYBOARD HANDLER
# ==========================================
@bot_app.on_message(filters.text & filters.regex(r"^❌ ᴄᴀɴᴄᴇʟ ❌$"))
async def reply_kbd_cancel(client, message):
    chat_id = message.chat.id

    if not is_sudo(message): 
        unauth_msg = await bot_app.send_message(chat_id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
        async def auto_delete_unauth():
            await asyncio.sleep(10)
            await safe_delete(unauth_msg)
            await safe_delete(message)
        asyncio.create_task(auto_delete_unauth())
        return

    session = AppState.merge_sessions.pop(chat_id, None)

    cancel_msg = await message.reply("Merge Cancelled ✅", reply_markup=ReplyKeyboardRemove())

    if session:
        await safe_delete(session.get("status_msg"))
        for msg in session["videos"]:
            await safe_delete(msg)

    async def auto_delete_cancel():
        await asyncio.sleep(5)
        await safe_delete(cancel_msg)
        await safe_delete(message)
    asyncio.create_task(auto_delete_cancel())

@bot_app.on_message(filters.text & filters.regex(r"^🎬 ᴍᴇʀɢᴇ ᴠɪᴅᴇᴏs 🎬$"))
async def execute_merge_text(client, message):
    chat_id = message.chat.id

    if not is_sudo(message): 
        unauth_msg = await bot_app.send_message(chat_id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
        async def auto_delete_unauth():
            await asyncio.sleep(10)
            await safe_delete(unauth_msg)
            await safe_delete(message)
        asyncio.create_task(auto_delete_unauth())
        return

    async with AppState.state_lock:
        if AppState.task_state != TaskState.IDLE:
            warning = await message.reply("⚠️ Bot is currently executing another task! Please wait until it finishes.")
            asyncio.create_task(delete_message_later(warning, 5))
            return

        session = AppState.merge_sessions.pop(chat_id, None)
        if not session:
            warning = await message.reply("⚠️ Merge session expired or invalid.", reply_markup=ReplyKeyboardRemove())
            asyncio.create_task(delete_message_later(warning, 5))
            return

        AppState.task_state = TaskState.MERGING
        AppState.task_kind = "merge"
        AppState.cancel_task = False

    status_msg = None
    downloaded_files = []
    files_to_upload = []
    active_client = user_app if user_app else bot_app
    videos = sorted(session["videos"], key=natural_sort_key)
    reply_to_message_id = videos[0].id
    reply_params = ReplyParameters(message_id=reply_to_message_id)

    try:
        await safe_delete(session["status_msg"])

        rm_msg = await bot_app.send_message(chat_id, "🔄 Preparing... Please Wait.. 🔄", reply_markup=ReplyKeyboardRemove())
        asyncio.create_task(safe_delete(rm_msg))

        status_msg = await bot_app.send_message(chat_id, "⏳ **Initializing Merge Engine...** ⏳", reply_parameters=reply_params)
        await safe_delete(message)

        AppState.active_origin_msg = videos[0]
        AppState.active_status_msg = status_msg

        await send_log(f"**Bot Become Busy Now !!** \n\nDownload Started at {get_ist()}")

        # ==========================================
        # 📥 DOWNLOAD PHASE
        # ==========================================
        for idx, msg in enumerate(videos):
            if AppState.cancel_task: raise asyncio.CancelledError()
            AppState.active_file_name = getattr(msg.video or msg.document, "file_name", f"Video_{idx+1}.mkv")
            start_time = time.time()
            last_up = [time.time()]
            # Claude FIX: re-anchor status_msg to each video being downloaded ---
            if idx > 0:
                await safe_delete(status_msg)
                status_msg = await bot_app.send_message(
                    chat_id,
                    f"📥 **Downloading Video {idx+1} of {len(videos)}...**\n`{AppState.active_file_name}`",
                    reply_parameters=ReplyParameters(message_id=msg.id)
                )
                AppState.active_status_msg = status_msg
            else:
                await safe_edit(status_msg, f"📥 **Downloading Video {idx+1} of {len(videos)}...**\n`{AppState.active_file_name}`")

            file_path = await active_client.download_media(
                msg,
                progress=progress_bar,
                progress_args=(f"Downloading (Video {idx+1}/{len(videos)})", status_msg, start_time, last_up)
            )

            if not file_path or not os.path.exists(file_path):
                raise Exception(f"Failed to download video {idx+1}")
                
            downloaded_files.append(file_path)
            
        await send_log(f"**Download Stopped, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")

        # ==========================================
        # 💡 MERGE PHASE
        # ==========================================
        if AppState.cancel_task: raise asyncio.CancelledError()
        
        await send_log(f"**Merging Video ...** \n\nProcess Started at {get_ist()}")
        # COMPLETENESS CHECK & FILENAME CONSTRUCTION
        ep_numbers = session["ep_numbers"]
        is_complete = False
        if ep_numbers and len(ep_numbers) > 1:
            if len(set(ep_numbers)) == (max(ep_numbers) - min(ep_numbers) + 1):
                is_complete = True
        elif len(videos) == 1:
            is_complete = True

        tag = "MERGED" if is_complete else "INCOMPLETE"

        first_name = getattr(videos[0].video or videos[0].document, "file_name", "Video.mkv")
        last_name = getattr(videos[-1].video or videos[-1].document, "file_name", "Video.mkv")

        first_id, _, _ = get_episode_identifier(first_name)
        last_id, _, last_raw = get_episode_identifier(last_name)

        if first_id and last_id and first_id != last_id and last_raw:
            clean_name = last_name.replace(last_raw, f"{first_id} - {last_id}", 1)
        else:
            clean_name = last_name

        clean_name = re.sub(r'\[.*?\]', '', clean_name.rsplit('.', 1)[0]).replace("_", " ")
        space_name = re.sub(r'\s+', ' ', clean_name).strip()
        full_mkv_title = f"{space_name} {tag}"
        clean_name = clean_name.replace("-", "")
        clean_name = re.sub(r'\s+', '.', clean_name)
        clean_name = re.sub(r'\.+', '.', clean_name).strip('.')
        max_allowed_length = 60 - len(tag) - 5

        if len(clean_name) > max_allowed_length:
            clean_name = clean_name[:max_allowed_length].rstrip('.')
        final_filename = f"{clean_name}.{tag}.mkv"
        output_path = os.path.join("/tmp", final_filename)
        cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running", style=ButtonStyle.DANGER)]])
        merge_success = await run_mkvmerge(downloaded_files, output_path, status_msg, cancel_markup, title=full_mkv_title)
        
        if not merge_success or not os.path.exists(output_path):
            raise Exception("mkvmerge failed to produce the output file.")

        # ==========================================
        # ✂️ AUTO-SPLIT PHASE
        # ==========================================
        if AppState.cancel_task: raise asyncio.CancelledError()
        
        duration_sec = 0
        try:
            probe = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", output_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
            )
            probe_stdout, _ = await asyncio.wait_for(probe.communicate(), timeout=30)
            duration_sec = int(float(probe_stdout.decode().strip()))
        except: pass

        duration_str = time.strftime('%H:%M:%S', time.gmtime(duration_sec))
        final_size_bytes = os.path.getsize(output_path)
        
        MAX_SIZE = 3950000000 if AppState.is_premium else 1950000000 
        files_to_upload = [output_path]

        if final_size_bytes > MAX_SIZE:
            limit_text = "3.95GB" if AppState.is_premium else "1.95GB"
            await safe_edit(status_msg, f"⚠️ **File Exceeds {limit_text} Limit!**\nAuto-Splitting perfectly into parts safely...")
            
            base_name_no_ext, ext = os.path.splitext(output_path)
            split_time = "01:00:00" 

            if duration_sec > 0:
                safe_split_sec = max(30, int((MAX_SIZE / final_size_bytes) * duration_sec))
                st_h, st_rem = divmod(safe_split_sec, 3600)
                st_m, st_s = divmod(st_rem, 60)
                split_time = f"{st_h:02d}:{st_m:02d}:{st_s:02d}"

            split_cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-nostdin",
                "-i", output_path, "-c", "copy", "-f", "segment", "-segment_time", split_time, 
                "-reset_timestamps", "1", f"{base_name_no_ext}_part%03d{ext}"
            ]

            s_proc = await asyncio.create_subprocess_exec(
                *split_cmd, 
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL, 
                stderr=asyncio.subprocess.DEVNULL, 
                start_new_session=True
            )
            try:
                await s_proc.communicate()
            except Exception:
                if s_proc.returncode is None:
                    try: os.killpg(os.getpgid(s_proc.pid), signal.SIGKILL); await s_proc.wait()
                    except: pass
                raise
                
            files_to_upload = sorted([os.path.join("/tmp", f) for f in os.listdir("/tmp") if f.startswith(os.path.basename(base_name_no_ext) + "_part") and f.endswith(ext)])
            os.remove(output_path)

        # ==========================================
        # 📤 UPLOAD PHASE
        # ==========================================
        await send_log(f"**Uploading Video ...** \n\nProcess Started at {get_ist()}")
        
        user_id = message.from_user.id
        custom_thumb = os.path.join(Config.THUMB_DIR, f"{user_id}.jpg")
        default_thumb = os.path.join(Config.ENV_DIR, "thumb.jpg")
        actual_thumb = custom_thumb if os.path.exists(custom_thumb) else (default_thumb if os.path.exists(default_thumb) else None)
        
        if not actual_thumb and files_to_upload:
            actual_thumb = await take_screen_shot(files_to_upload[0], Config.THUMB_DIR, 5)

        as_doc = config_data.get("AS_DOCUMENT", True)
        upload_aborted = False

        for idx, upload_file in enumerate(files_to_upload):
            if upload_aborted: break
            
            part_size_bytes = os.path.getsize(upload_file)
            part_size_mb = round(part_size_bytes / (1024 * 1024), 2)
            base_upload_name = os.path.basename(upload_file)
            # --- 1. CAPTION DISPLAY FORMATTING (Uncut & Spaced) ---
            part_match = re.search(r'_part(\d+)', base_upload_name, flags=re.IGNORECASE)
            # Dynamically format the part number for the caption if split
            part_str = f" - Part {int(part_match.group(1))}" if part_match else ""
            display_name = f"{full_mkv_title}{part_str}.mkv"
            # --- 2. TELEGRAM API FORMATTING (Strict 60-Char Limit) ---
            # Convert any underscores from the auto-splitter into dots
            file_name_safe = base_upload_name.replace("_", ".")
            file_name_safe = re.sub(r'\.+', '.', file_name_safe)
            # Bulletproof limit: If the auto-splitter added length that exceeds 60 chars
            if len(file_name_safe) > 60:
                # We dynamically shrink the base title but keep the ".part001.mkv" intact
                ext_str = f".part{part_match.group(1)}.mkv" if part_match else ".mkv"
                allowed_base_len = 60 - len(ext_str)
                safe_base = file_name_safe.split('.part')[0] if part_match else file_name_safe.rsplit('.mkv')[0]
                file_name_safe = f"{safe_base[:allowed_base_len].rstrip('.')}{ext_str}"

            caption = (
                f"<b>✅ {display_name}</b>\n"
                f"<b>Size:</b> {part_size_mb} MB\n"
                f"<b>Duration:</b> {duration_str}\n"
                f"<b>Data Center:</b> Pending...\n\n"
                f"<i><b>➕ {len(videos)} Videos Merged ✅</b></i>\n\n"
                f"<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
            )

            if len(files_to_upload) > 1:
                caption = f"<b>[Part {idx+1}/{len(files_to_upload)}]</b>\n" + caption

            try:
                upload_start = time.time()
                last_up_time = [time.time()]
                
                if as_doc:
                    uploaded_msg = await active_client.send_document(
                        chat_id=chat_id, document=upload_file, thumb=actual_thumb, caption=caption, force_document=True,
                        file_name=file_name_safe, 
                        progress=progress_bar, progress_args=("Uploading", status_msg, upload_start, last_up_time),
                        parse_mode=ParseMode.HTML,
                        reply_parameters=reply_params
                    )
                else:
                    uploaded_msg = await active_client.send_video(
                        chat_id=chat_id, video=upload_file, thumb=actual_thumb, caption=caption,
                        file_name=file_name_safe, 
                        progress=progress_bar, progress_args=("Uploading", status_msg, upload_start, last_up_time),
                        parse_mode=ParseMode.HTML,
                        reply_parameters=reply_params
                    )

                if uploaded_msg:
                    _, new_dc_str = get_file_info(uploaded_msg)
                    updated_caption = caption.replace("Pending...", new_dc_str)
                    await uploaded_msg.edit_caption(updated_caption, parse_mode=ParseMode.HTML)

            except asyncio.CancelledError:
                upload_aborted = True
                raise
            except Exception as e:
                if AppState.cancel_task or "Cancelled" in str(e) or "400" in str(e):
                    upload_aborted = True
                    raise asyncio.CancelledError()
                else:
                    logger.error(f"Upload Error on part {idx+1}: {e}")
                    if status_msg:
                        await safe_edit(status_msg, f"⚠️ **Upload Failed on Part {idx+1}:**\n`{e}`")
            finally:
                if os.path.exists(upload_file): os.remove(upload_file)

        if not upload_aborted:
            await send_log(f"**Upload Done, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")
            if status_msg:
                await safe_edit(status_msg, "✅ **Merge Process Complete!**")

            await asyncio.sleep(3)
            if status_msg:
                await safe_delete(status_msg)
            for msg in videos:
                await safe_delete(msg)

    except asyncio.CancelledError:
        if status_msg:
            await safe_edit(status_msg, "🛑 **Merge Task Cancelled.**")
        await send_log(f"**Merge Cancelled, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")
        await asyncio.sleep(3)
        if status_msg:
            await safe_delete(status_msg)
        for msg in videos:
            await safe_delete(msg)
    except Exception as e:
        logger.error(f"Merge Execution Error: {e}\n{traceback.format_exc()}")
        if status_msg:
            await safe_edit(status_msg, f"⚠️ **Merge Failed:**\n`{e}`")
        await send_log(f"**Merge Failed, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
    finally:
        for f in downloaded_files:
            if os.path.exists(f): os.remove(f)
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
        for f in files_to_upload:
            if os.path.exists(f): os.remove(f)
        if 'actual_thumb' in locals() and actual_thumb and actual_thumb not in [custom_thumb, default_thumb] and os.path.exists(actual_thumb):
            os.remove(actual_thumb)

        async with AppState.state_lock:
            AppState.task_state = TaskState.IDLE
            AppState.cancel_task = False
            AppState.active_file_name = "None"
            AppState.active_origin_msg = None
            AppState.active_status_msg = None
            AppState.status_snapshot = ""
            AppState.task_kind = "compress"