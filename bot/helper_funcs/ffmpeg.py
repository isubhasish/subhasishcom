import os
import asyncio
import time
import re
from datetime import datetime, timezone, timedelta
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.__init__ import bot_app, user_app, logger, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import queue, AppState, get_ist, send_log, get_sys_stats, get_file_info, get_network_io, get_readable_time
from bot.helper_funcs.display_progress import progress_bar, humanbytes, time_formatter, make_bar

async def take_screen_shot(video_file, output_directory, ttl):
    out_put_file_name = os.path.join(output_directory, f"{time.time()}_thumb.jpg")
    file_genertor_command = ["ffmpeg", "-ss", str(ttl), "-i", video_file, "-vframes", "1", out_put_file_name]
    try:
        process = await asyncio.create_subprocess_exec(*file_genertor_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        if os.path.lexists(out_put_file_name): return out_put_file_name
    except Exception as e: logger.error(f"Failed to generate auto-thumbnail: {e}")
    return None

async def worker():
    while True:
        msg, name, map_args, status_msg = await queue.get()
        AppState.active_file_name = name
        start_time = time.time()
        last_up = [time.time()]
        file_path = None
        out = None
        actual_thumb = None 
        custom_thumb = os.path.join(Config.THUMB_DIR, f"{msg.from_user.id}.jpg")
        
        try:
            now_time = get_ist()
            await send_log(f"**Bot Become Busy Now !!** \n\nDownload Started at {now_time}")
            
            try:
                file_path = await user_app.download_media(msg, progress=progress_bar, progress_args=("Downloading", status_msg, start_time, last_up))
                if not file_path or not os.path.exists(file_path):
                    await status_msg.edit(Localisation.FILE_NOT_FOUND)
                    await send_log(f"**Download Error, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nReason: Path not exist")
                    continue
            except Exception as e:
                await status_msg.edit(Localisation.DOWNLOAD_FAILED)
                await send_log(f"**Download Failed, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
                continue
            
            dl_time = int(time.time() - start_time)
            await status_msg.edit(Localisation.DOWNLOADED_SUCCESS.format(time_formatter(dl_time * 1000)))
            await send_log(f"**Download Stopped, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")
            await asyncio.sleep(2.5) 
            
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
            
            cmd = ["ffmpeg", "-i", file_path] + map_args + [
                "-c:v", str(config_data.get("CODEC", "libx265")), 
                "-crf", str(config_data.get("CRF", "28")), 
                "-preset", str(config_data.get("PRESET", "fast")),
                "-vf", vf_string, 
                "-c:a", "libopus", 
                "-b:a", str(config_data.get("AUDIO_BITRATE", "96k")), 
                "-y", out
            ]
            
            duration_sec = getattr(msg.video, 'duration', 0) if msg.video else 0
            encode_start_time = time.time()
            
            try:
                process = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
                AppState.current_process = process
                last_update_time = time.time()
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running")]])

                line_buf = bytearray()
                while True:
                    chunk = await process.stderr.read(10)
                    if not chunk: break
                    for b in chunk:
                        if b in (13, 10): 
                            line_str = line_buf.decode('utf-8', errors='ignore').strip()
                            line_buf.clear()
                            
                            if not line_str: continue

                            if not duration_sec and "Duration:" in line_str:
                                match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})", line_str)
                                if match: duration_sec = int(match.group(1))*3600 + int(match.group(2))*60 + int(match.group(3))

                            if "time=" in line_str:
                                # FIX: The exact requested regex fallback restored perfectly!
                                time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.", line_str)
                                if not time_match: time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line_str)
                                    
                                if time_match and (time.time() - last_update_time > 8):
                                    curr_sec = int(time_match.group(1))*3600 + int(time_match.group(2))*60 + int(time_match.group(3))
                                    if duration_sec > 0:
                                        percent = (curr_sec / duration_sec) * 100
                                        elapsed = time.time() - encode_start_time
                                        speed = curr_sec / elapsed if elapsed > 0 else 0
                                        eta = (duration_sec - curr_sec) / speed if speed > 0 else 0
                                        
                                        cpu, mem, disk = get_sys_stats()
                                        est_total_bytes = os.path.getsize(file_path) * 0.4 
                                        current_bytes = (percent/100) * est_total_bytes

                                        text = (
                                            f"ℹ️ **ɴᴏᴡ:** 💡 ENCODING... 💡\n\n"
                                            f"⏱️ **ᴇᴛᴀ:** {time_formatter(eta*1000)}\n\n"
                                            f"`{AppState.active_file_name}`\n"
                                            f"[{make_bar(percent)}] {percent:.2f}%\n\n"
                                            f"⚡️ **ꜱᴘᴇᴇᴅ:** {humanbytes((current_bytes/elapsed) if elapsed else 0)}/s\n"
                                            f"⏰ **ᴇʟᴀᴘsᴇᴅ:** {time_formatter(elapsed*1000)}\n"
                                            f"📦 **sɪᴢᴇ:** {humanbytes(current_bytes)} / {humanbytes(est_total_bytes)}\n\n"
                                            f"🖥 CPU: {cpu}% | 💽 RAM: {mem}%"
                                        )
                                        try:
                                            await status_msg.edit(text, reply_markup=btn)
                                            last_update_time = time.time()
                                        except: pass
                        else:
                            line_buf.append(b)

                await process.wait()
                if AppState.current_process == process: AppState.current_process = None
                if process.returncode != 0: raise Exception("FFmpeg Process Crashed or Cancelled")
                    
            except Exception as e:
                await status_msg.edit(Localisation.COMPRESS_FAILED)
                await send_log(f"**Compression Failed, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
                if file_path and os.path.exists(file_path): os.remove(file_path)
                if out and os.path.exists(out): os.remove(out)
                continue

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

                split_cmd = ["ffmpeg", "-i", out, "-c", "copy", "-f", "segment", "-segment_time", split_time, "-reset_timestamps", "1", f"{base_name}_part%03d{ext}"]
                s_proc = await asyncio.create_subprocess_exec(*split_cmd)
                await s_proc.communicate()
                files_to_upload = sorted([f for f in os.listdir(".") if f.startswith(base_name + "_part") and f.endswith(ext)])
                os.remove(out) 

            await send_log(f"**Uploading Video ...** \n\nProcess Started at {get_ist()}")

            actual_thumb = custom_thumb if os.path.exists(custom_thumb) else None
            if not actual_thumb and files_to_upload: actual_thumb = await take_screen_shot(files_to_upload[0], Config.THUMB_DIR, 5)

            as_doc = config_data.get("AS_DOCUMENT", True)

            for idx, upload_file in enumerate(files_to_upload):
                part_size_bytes = os.path.getsize(upload_file)
                part_size_str = humanbytes(part_size_bytes)
                    
                final_caption = f"✅ <b>{upload_file}</b>\n**Size:** {part_size_str}\n\n<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
                if len(files_to_upload) > 1: final_caption = f"**[Part {idx+1}/{len(files_to_upload)}]**\n" + final_caption

                try:
                    upload_start = time.time()
                    last_up_time = [time.time()]
                    
                    uploaded_msg = None
                    if as_doc:
                        uploaded_msg = await user_app.send_document(
                            chat_id=msg.chat.id, document=upload_file, thumb=actual_thumb, caption=final_caption, force_document=True,
                            progress=progress_bar, progress_args=("Uploading", status_msg, upload_start, last_up_time),
                            reply_to_message_id=msg.id
                        )
                    else:
                        uploaded_msg = await user_app.send_video(
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
                    await status_msg.edit(Localisation.UPLOAD_FAILED)
                    await send_log(f"**Upload Stopped, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
                finally:
                    if os.path.exists(upload_file): os.remove(upload_file)

            await status_msg.edit("✅ Process Complete!")
            await asyncio.sleep(3) 
            try: await status_msg.delete() 
            except: pass
            
            await send_log(f"**Upload Done, Bot is Free Now !!** \n\nProcess Done at {get_ist()}")
            
        except Exception as e: logger.error(f"Fatal Worker Error: {e}")
        finally: 
            if file_path and os.path.exists(file_path): os.remove(file_path)
            if actual_thumb and actual_thumb != custom_thumb and os.path.exists(actual_thumb): os.remove(actual_thumb)
            AppState.active_file_name = "None"
            queue.task_done()