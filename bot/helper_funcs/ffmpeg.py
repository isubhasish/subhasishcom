import os
import asyncio
import time
import re
import traceback
from datetime import datetime, timezone, timedelta
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot_app, user_app, logger, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import queue, AppState, TaskState, get_ist, send_log, get_sys_stats, get_file_info, kill_running_process, get_readable_time, START_TIME
from bot.helper_funcs.display_progress import progress_bar, humanbytes, time_formatter, make_bar, render_active_status

async def safe_readline(stream, timeout=10):
    try:
        return await asyncio.wait_for(stream.readline(), timeout=timeout)
    except asyncio.TimeoutError:
        return None  

async def abort_current_task(status_msg, file_path=None, out=None):
    await kill_running_process()
    for p in [file_path, out]:
        try:
            if p and os.path.exists(p): os.remove(p)
        except: pass
        
    try:
        await status_msg.edit("🛑 **Task Cancelled. Moving to next in queue...**")
    except: pass
    
    try:
        if AppState.active_origin_msg:
            await bot_app.send_message(
                status_msg.chat.id,
                "❌ **Task Cancelled.**",
                reply_to_message_id=AppState.active_origin_msg.id
            )
    except: pass

async def take_screen_shot(video_file, output_directory, ttl):
    out_put_file_name = os.path.join(output_directory, f"{time.time()}_thumb.jpg")
    file_genertor_command = [
        "ffmpeg", "-hide_banner", "-loglevel", "quiet",
        "-ss", str(ttl), "-i", video_file, "-vframes", "1", out_put_file_name
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *file_genertor_command, 
            stdout=asyncio.subprocess.DEVNULL, 
            stderr=asyncio.subprocess.DEVNULL, 
            start_new_session=True
        )
        await process.communicate()
        if os.path.lexists(out_put_file_name): return out_put_file_name
    except Exception as e: logger.error(f"Failed to generate auto-thumbnail: {e}")
    return None

async def worker():
    active_client = user_app if user_app else bot_app
    
    while True:
        try:
            task = await asyncio.wait_for(queue.get(), timeout=30)
        except asyncio.TimeoutError:
            continue
            
        msg, name, map_args, status_msg = task
        
        AppState.task_state = TaskState.DOWNLOADING
        AppState.active_file_name = name
        AppState.active_origin_msg = msg
        AppState.cancel_task = False 
        
        start_time = time.time()
        last_up = [time.time()]
        file_path = None
        out = None
        actual_thumb = None 
        
        custom_thumb = os.path.join(Config.THUMB_DIR, f"{msg.from_user.id}.jpg")
        default_thumb = "thumb.jpg"
        
        try:
            now_time = get_ist()
            await send_log(f"**Bot Become Busy Now !!** \n\nDownload Started at {now_time}")
            
            download_cancelled = False
            try:
                file_path = await active_client.download_media(msg, progress=progress_bar, progress_args=("Downloading", status_msg, start_time, last_up))
            except asyncio.CancelledError: download_cancelled = True
            except Exception as e:
                if "Cancelled" in str(e) or "400" in str(e): download_cancelled = True
                else: raise e
                
            if download_cancelled or AppState.cancel_task:
                await abort_current_task(status_msg, file_path)
                continue
                
            if not file_path or not os.path.exists(file_path):
                await status_msg.edit(Localisation.FILE_NOT_FOUND)
                await send_log(f"**Download Error, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nReason: Path not exist")
                continue

            AppState.task_state = TaskState.ENCODING
            AppState.status_snapshot = Localisation.COMPRESS_START
            dl_time = int(time.time() - start_time)
            await status_msg.edit(Localisation.DOWNLOADED_SUCCESS.format(time_formatter(dl_time * 1000)))
            await send_log(f"**Download Stopped, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")
            await asyncio.sleep(2.5) 
            
            if AppState.cancel_task:
                await abort_current_task(status_msg, file_path)
                continue
            
            base = name.replace(" ", ".").rsplit(".", 1)[0]
            out = f"{base}.Compressed.mkv"
            
            await status_msg.edit(Localisation.COMPRESS_START)
            await send_log(f"**Compressing Video ...** \n\nProcess Started at {get_ist()}")
            await asyncio.sleep(1) 

            res = str(config_data.get('RESOLUTION', '820x480')).lower().replace("x", ":")
            vf_filters = [f"scale={res}"]
            watermark = str(config_data.get("WATERMARK_TEXT", "None"))
            if watermark.lower() != "none" and watermark.strip() != "":
                clean_wm = watermark.replace("'", "").replace(":", "") 
                vf_filters.append(f"drawtext=text='{clean_wm}':fontcolor=white:fontsize=24:x=15:y=15:box=1:boxcolor=black@0.5")
                
            vf_string = ",".join(vf_filters)
            
            try:
                crf_val = str(float(config_data.get("CRF", "28")))
            except Exception:
                crf_val = "28"
            
            duration_sec = getattr(msg.video, 'duration', 0) if msg.video else 0
            if not duration_sec:
                try:
                    probe = await asyncio.create_subprocess_exec(
                        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", file_path,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=True
                    )
                    probe_stdout, _ = await asyncio.wait_for(probe.communicate(), timeout=30)
                    duration_sec = int(float(probe_stdout.decode().strip()))
                except Exception:
                    duration_sec = 0

            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-i", file_path
            ] + map_args + [
                "-c:v", str(config_data.get("CODEC", "libx265")), 
                "-crf", crf_val, 
                "-preset", str(config_data.get("PRESET", "fast")),
                "-vf", vf_string, 
                "-c:a", "libopus", 
                "-b:a", str(config_data.get("AUDIO_BITRATE", "96k")), 
                "-progress", "pipe:1",
                "-y", out
            ]
            
            encode_start_time = time.time()
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.DEVNULL, 
                    start_new_session=True
                )
                async with AppState.process_lock:
                    AppState.current_process = process
                last_update_time = time.time() - 10 
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running")]])

                while True:
                    if AppState.cancel_task:
                        await kill_running_process()
                        raise asyncio.CancelledError("Task Cancelled by User")

                    line_bytes = await safe_readline(process.stdout)
                    
                    if line_bytes is None:
                        if process.returncode is not None: break
                        continue 
                    if line_bytes == b"":
                        break    

                    line_str = line_bytes.decode('utf-8', errors='ignore').strip()
                    if not line_str: continue

                    if line_str.startswith("out_time_ms="):
                        try:
                            out_time_ms = int(line_str.split("=", 1)[1])
                        except ValueError:
                            continue

                        if time.time() - last_update_time > 4:
                            curr_sec = out_time_ms / 1_000_000
                            safe_duration = duration_sec if duration_sec > 0 else max(curr_sec + 1, 1)

                            percent = min((curr_sec / safe_duration) * 100, 100.0)
                            elapsed = max(time.time() - encode_start_time, 0.001)
                            speed = curr_sec / elapsed if elapsed > 0 else 0
                            eta = (safe_duration - curr_sec) / speed if speed > 0 else 0

                            cpu, mem, disk = get_sys_stats()
                            est_total_bytes = max(os.path.getsize(file_path) * 0.4, 1)
                            current_bytes = (percent / 100) * est_total_bytes

                            done_str = humanbytes(current_bytes)
                            total_str = humanbytes(est_total_bytes)
                            speed_str = humanbytes(speed)
                            eta_str = time_formatter(eta * 1000)
                            elapsed_str = time_formatter(elapsed * 1000)

                            AppState.status_snapshot = render_active_status(
                                percent, done_str, total_str, eta_str, speed_str, elapsed_str
                            )

                            text = (
                                f"ℹ️ **ɴᴏᴡ:** 💡 ENCODING...💡\n\n"
                                f"⏱️ **ᴇᴛᴀ:** {eta_str}\n\n"
                                f"[{make_bar(percent)}] {percent:.2f}%\n\n"
                                f"⚡️ **ꜱᴘᴇᴇᴅ:** {speed_str}/s\n"
                                f"⏰ **ᴇʟᴀᴘsᴇᴅ:** {elapsed_str}\n"
                                f"📦 **sɪᴢᴇ:** {done_str} of {total_str}\n\n"
                                f"🖥 CPU: {cpu}% | 💽 RAM: {mem}%"
                            )

                            try:
                                await status_msg.edit(text, reply_markup=btn)
                                last_update_time = time.time()
                            except: pass

                await process.wait()
                async with AppState.process_lock:
                    if AppState.current_process == process: AppState.current_process = None
                if process.returncode != 0 and not AppState.cancel_task: 
                    raise asyncio.CancelledError("FFmpeg failed or cancelled")
                    
            except Exception as e:
                if AppState.cancel_task or isinstance(e, asyncio.CancelledError):
                    await abort_current_task(status_msg, file_path, out)
                    continue
                else:
                    await status_msg.edit(Localisation.COMPRESS_FAILED)
                    await send_log(f"**Compression Failed, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
                    if file_path and os.path.exists(file_path): os.remove(file_path)
                    if out and os.path.exists(out): os.remove(out)
                    continue
            
            if AppState.cancel_task:
                await abort_current_task(status_msg, file_path, out)
                continue

            AppState.task_state = TaskState.UPLOADING
            final_size = os.path.getsize(out)
            MAX_SIZE = 3950000000 if AppState.is_premium else 1950000000 
            files_to_upload = [out]
            
            if final_size > MAX_SIZE:
                limit_text = "3.95GB" if AppState.is_premium else "1.95GB"
                await status_msg.edit(f"⚠️ **File Exceeds {limit_text} Limit!**\nAuto-Splitting perfectly into parts safely...")
                
                base_name, ext = os.path.splitext(out)
                split_time = "01:00:00" 
                
                if duration_sec > 0:
                    safe_split_sec = int((MAX_SIZE / final_size) * duration_sec)
                    st_h, st_rem = divmod(safe_split_sec, 3600)
                    st_m, st_s = divmod(st_rem, 60)
                    split_time = f"{st_h:02d}:{st_m:02d}:{st_s:02d}"

                split_cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats",
                    "-i", out, "-c", "copy", "-f", "segment", "-segment_time", split_time, 
                    "-reset_timestamps", "1", f"{base_name}_part%03d{ext}"
                ]
                s_proc = await asyncio.create_subprocess_exec(
                    *split_cmd, 
                    stdout=asyncio.subprocess.DEVNULL, 
                    stderr=asyncio.subprocess.DEVNULL, 
                    start_new_session=True
                )
                await s_proc.communicate()
                files_to_upload = sorted([f for f in os.listdir(".") if f.startswith(base_name + "_part") and f.endswith(ext)])
                os.remove(out) 

            await send_log(f"**Uploading Video ...** \n\nProcess Started at {get_ist()}")

            if os.path.exists(custom_thumb):
                actual_thumb = custom_thumb
            elif os.path.exists(default_thumb):
                actual_thumb = default_thumb
            else:
                actual_thumb = None

            if not actual_thumb and files_to_upload: 
                actual_thumb = await take_screen_shot(files_to_upload[0], Config.THUMB_DIR, 5)

            as_doc = config_data.get("AS_DOCUMENT", True)
            upload_aborted = False

            for idx, upload_file in enumerate(files_to_upload):
                if upload_aborted: break
                part_size_bytes = os.path.getsize(upload_file)
                part_size_str = humanbytes(part_size_bytes)
                    
                final_caption = f"✅ <b>{upload_file}</b>\n**Size:** {part_size_str}\n\n<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
                if len(files_to_upload) > 1: final_caption = f"**[Part {idx+1}/{len(files_to_upload)}]**\n" + final_caption

                try:
                    upload_start = time.time()
                    last_up_time = [time.time()]
                    
                    uploaded_msg = None
                    if as_doc:
                        uploaded_msg = await active_client.send_document(
                            chat_id=msg.chat.id, document=upload_file, thumb=actual_thumb, caption=final_caption, force_document=True,
                            progress=progress_bar, progress_args=("Uploading", status_msg, upload_start, last_up_time),
                            reply_to_message_id=msg.id
                        )
                    else:
                        uploaded_msg = await active_client.send_video(
                            chat_id=msg.chat.id, video=upload_file, thumb=actual_thumb, caption=final_caption,
                            progress=progress_bar, progress_args=("Uploading", status_msg, upload_start, last_up_time),
                            reply_to_message_id=msg.id
                        )
                        
                    if uploaded_msg:
                        _, new_dc_str = get_file_info(uploaded_msg)
                        updated_caption = f"✅ <b>{upload_file}</b>\n**Size:** {part_size_str}\n**Data Center:** {new_dc_str}\n\n<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
                        if len(files_to_upload) > 1: updated_caption = f"**[Part {idx+1}/{len(files_to_upload)}]**\n" + updated_caption
                        await uploaded_msg.edit_caption(updated_caption)

                except Exception as e:
                    if AppState.cancel_task or isinstance(e, asyncio.CancelledError) or "Cancelled" in str(e) or "400" in str(e):
                        upload_aborted = True
                        await abort_current_task(status_msg, upload_file)
                    else:
                        await status_msg.edit(Localisation.UPLOAD_FAILED)
                        await send_log(f"**Upload Stopped, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
                finally:
                    if os.path.exists(upload_file): os.remove(upload_file)

            if upload_aborted: continue
                
            await status_msg.edit("✅ Process Complete!")
            await asyncio.sleep(3) 
            try: await status_msg.delete() 
            except: pass
            
            await send_log(f"**Upload Done, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")
            
        except Exception as e: 
            logger.error(f"[WORKER CRASHED] {e}\n{traceback.format_exc()}")
        finally: 
            await kill_running_process()
            if file_path and os.path.exists(file_path): os.remove(file_path)
            if actual_thumb and actual_thumb != custom_thumb and actual_thumb != default_thumb and os.path.exists(actual_thumb): 
                os.remove(actual_thumb)
            
            AppState.cancel_task = False
            AppState.active_file_name = "None"
            AppState.active_origin_msg = None
            AppState.status_snapshot = ""
            if queue.empty(): AppState.task_state = TaskState.IDLE
            
            queue.task_done()