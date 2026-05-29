import os
import asyncio
import time
import re
import traceback
import signal
import socket
from datetime import datetime, timezone, timedelta
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from bot import bot_app, user_app, logger, config_data
from bot.config import Config
from bot.localisation import Localisation
from bot.helper_funcs.utils import queue, AppState, TaskState, get_ist, send_log, get_sys_stats, get_file_info, kill_running_process, get_readable_time, START_TIME, delete_message_later
from bot.helper_funcs.display_progress import progress_bar, humanbytes, time_formatter, make_bar, render_active_status

async def safe_readline(stream, timeout=10):
    try:
        return await asyncio.wait_for(stream.readline(), timeout=timeout)
    except asyncio.TimeoutError:
        return None  

async def abort_current_task(status_msg=None, file_path=None, out=None, chat_id=None):
    await kill_running_process()
    for p in [file_path, out]:
        try:
            if p and os.path.exists(p): os.remove(p)
        except: pass
        
    target_msg = status_msg or AppState.active_status_msg
    try:
        if target_msg: await target_msg.delete()
    except: pass
    
    try:
        if chat_id and AppState.active_origin_msg:
            done_msg = await bot_app.send_message(
                chat_id,
                "🛑 **Task Cancelled.**",
                reply_parameters=ReplyParameters(message_id=AppState.active_origin_msg.id)
            )
            asyncio.create_task(delete_message_later(done_msg, 10))
    except: pass

    AppState.task_state = TaskState.IDLE
    AppState.cancel_task = False
    AppState.active_file_name = "None"
    AppState.active_origin_msg = None
    AppState.active_status_msg = None
    AppState.status_snapshot = ""
    AppState.task_kind = "compress"

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.getsockname()[1]

async def start_tg_http_proxy(
    active_client,
    target_message,
    port: int,
    file_size: int,
    progress_dict: dict
) -> asyncio.AbstractServer:
    BLOCK_SIZE: int = 1024 * 1024  

    async def _handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = b""
            while b"\r\n\r\n" not in raw:
                try:
                    part = await asyncio.wait_for(reader.read(8192), timeout=15)
                except asyncio.TimeoutError:
                    return
                if not part:
                    break
                raw += part
            
            req_start: int = 0
            req_end: int = file_size - 1
            
            for line in raw.decode("utf-8", errors="ignore").split("\r\n"):
                if line.lower().startswith("range:"):
                    rng = line.split(":", 1)[1].strip()
                    if rng.startswith("bytes="):
                        parts = rng[6:].split("-")
                        token_start = parts[0]
                        token_end = parts[1] if len(parts) > 1 else ""
                        req_start = int(token_start) if token_start else 0
                        req_end = int(token_end) if token_end else file_size - 1
                    break
            
            req_start = max(0, min(req_start, file_size - 1))
            req_end = max(req_start, min(req_end, file_size - 1))
            
            chunk_offset: int = req_start // BLOCK_SIZE
            byte_skip:    int = req_start - (chunk_offset * BLOCK_SIZE)
            
            bytes_to_send = (req_end - req_start) + 1
            chunk_limit = (bytes_to_send + byte_skip) // BLOCK_SIZE + 2
            
            resp_header = (
                "HTTP/1.1 206 Partial Content\r\n"
                "Content-Type: application/octet-stream\r\n"
                f"Content-Range: bytes {req_start}-{req_end}/{file_size}\r\n"
                f"Content-Length: {bytes_to_send}\r\n"
                "Accept-Ranges: bytes\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            writer.write(resp_header.encode())
            await writer.drain()
            
            sent_bytes = 0
            stream = active_client.stream_media(target_message, offset=chunk_offset, limit=chunk_limit)
            try:
                stream_iter = stream.__aiter__()
                while True:
                    next_task = asyncio.create_task(stream_iter.__anext__())
                    try: chunk = await asyncio.wait_for(next_task, timeout=15.0)
                    except asyncio.TimeoutError: next_task.cancel(); break
                    except StopAsyncIteration: break

                    if AppState.cancel_task or writer.is_closing():
                        break
                    if byte_skip > 0:
                        trim = min(len(chunk), byte_skip)
                        chunk = chunk[trim:]
                        byte_skip -= trim
                        if not chunk:
                            continue
                    if sent_bytes + len(chunk) > bytes_to_send:
                        chunk = chunk[:bytes_to_send - sent_bytes]

                    try:
                        writer.write(chunk)
                        await writer.drain()
                        sent_bytes += len(chunk)
                        progress_dict["downloaded"] += len(chunk) 
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
                    
                    if sent_bytes >= bytes_to_send:
                        break
            finally:
                if hasattr(stream, 'aclose'):
                    try: await asyncio.wait_for(stream.aclose(), timeout=5.0)
                    except Exception as exc: logger.debug(f"[TG_HTTP_PROXY] Stream aclose failed: {exc}")

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            logger.debug("[TG_HTTP_PROXY] handler error: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
                
    return await asyncio.start_server(_handler, "127.0.0.1", port)

async def take_screen_shot(video_file: str, output_directory: str, ttl: int) -> str | None:
    out_path = os.path.join(output_directory, f"{time.time()}_thumb.jpg")
    fallback_times = sorted({ttl, max(0, ttl - 2), max(0, ttl // 2), 0})
    for seek_t in fallback_times:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "quiet",
            "-ss", str(seek_t),
            "-i",  video_file,
            "-vframes", "1",
            "-vf", "scale='if(gt(iw,ih),320,-2)':'if(gt(iw,ih),-2,320)'",   
            "-q:v", "2",             
            "-y", out_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            await asyncio.wait_for(proc.communicate(), timeout=20)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                return out_path
        except asyncio.TimeoutError:
            logger.warning("take_screen_shot: ffmpeg timed out at seek=%ss", seek_t)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                await proc.wait()
            except Exception:
                pass
        except Exception as e:
            logger.error("take_screen_shot at seek=%ss failed: %s", seek_t, e)
            
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
                
    logger.warning("take_screen_shot: all attempts exhausted for '%s'", video_file)
    return None

async def worker():
    active_client = user_app if user_app else bot_app
    
    while True:
        try:
            task = await asyncio.wait_for(queue.get(), timeout=30)
        except asyncio.TimeoutError:
            continue
            
        msg, name, map_args, status_msg = task
        chat_id_target = msg.chat.id
        
        AppState.task_state = TaskState.DOWNLOADING
        AppState.active_file_name = name
        AppState.active_origin_msg = msg
        AppState.active_status_msg = status_msg
        AppState.task_kind = "compress"
        AppState.cancel_task = False 
        
        start_time = time.time()
        last_up = [time.time()]
        file_path = None
        out = None
        actual_thumb = None 
        files_to_upload = []
        
        user_id = msg.from_user.id if msg.from_user else 0
        custom_thumb = os.path.join(Config.THUMB_DIR, f"{user_id}.jpg")
        default_thumb = os.path.join(Config.ENV_DIR, "thumb.jpg")
        
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
                await abort_current_task(status_msg, file_path, chat_id=chat_id_target)
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
                await abort_current_task(status_msg, file_path, chat_id=chat_id_target)
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
                clean_wm = re.sub(r"[\\'%:,\[\]]", "", watermark)
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
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=True
                    )
                    probe_stdout, _ = await asyncio.wait_for(probe.communicate(), timeout=30)
                    duration_sec = int(float(probe_stdout.decode().strip()))
                except Exception:
                    duration_sec = 0

            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-nostdin", "-i", file_path
            ] + map_args + [
                "-c:v", str(config_data.get("CODEC", "libx265")), 
                "-crf", crf_val, 
                "-preset", str(config_data.get("PRESET", "fast")),
                "-filter:v:0", vf_string, 
                "-c:a", "libopus", 
                "-b:a", str(config_data.get("AUDIO_BITRATE", "96k")), 
                "-c:s", "copy",
                "-max_muxing_queue_size", "1024",
                "-progress", "pipe:1",
                "-y", out
            ]
            
            encode_start_time = time.time()
            stderr_lines = []
            # Localized async function to safely drain stderr without global memory leaks
            async def drain_stderr(proc):
                if proc.stderr is None: return
                try:
                    while True:
                        line = await proc.stderr.readline()
                        if not line: break
                        stderr_lines.append(line.decode("utf-8", errors="ignore"))
                except Exception:
                    pass

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.PIPE, 
                    start_new_session=True
                )
                stderr_task = asyncio.create_task(drain_stderr(process))
                async with AppState.process_lock:
                    AppState.current_process = process
                last_update_time = time.time() - 10 
                last_progress_seen = time.time()
                last_heartbeat_time = time.time()
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running", style=ButtonStyle.DANGER)]])

                while True:
                    if AppState.cancel_task:
                        await kill_running_process()
                        raise asyncio.CancelledError("Task Cancelled by User")

                    line_bytes = await safe_readline(process.stdout, timeout=5)
                    
                    if line_bytes is None:
                        if process.returncode is not None: break
                        # [NEW] The UI Heartbeat Logic
                        if time.time() - last_progress_seen > 15 and time.time() - last_heartbeat_time > 10:
                            try:
                                elapsed_hb = time.time() - encode_start_time
                                await status_msg.edit(
                                    f"📀 **Preparing For Compression ...**\n\n"
                                    f"⏳ **Status:** Processing headers/metadata...\n"
                                    f"⏱ **Time taken so far:** {time_formatter(elapsed_hb * 1000)}",
                                    reply_markup=btn
                                )
                                last_heartbeat_time = time.time()
                            except Exception:
                                pass
                        continue 
                    if line_bytes == b"":
                        break    

                    line_str = line_bytes.decode('utf-8', errors='ignore').strip()
                    if not line_str: continue

                    if line_str.startswith("out_time_ms="):
                        last_progress_seen = time.time()
                        try:
                            out_time_ms = int(line_str.split("=", 1)[1])
                        except ValueError:
                            continue

                        if time.time() - last_update_time > 3.5:
                            curr_sec = out_time_ms / 1_000_000
                            safe_duration = duration_sec if duration_sec > 0 else max(curr_sec + 1, 1)

                            percent = min((curr_sec / safe_duration) * 100, 100.0)
                            elapsed = max(time.time() - encode_start_time, 0.001)
                            speed = curr_sec / elapsed if elapsed > 0 else 0
                            eta = (safe_duration - curr_sec) / speed if speed > 0 else 0

                            cpu, mem, _ = get_sys_stats()
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

                try:
                    await asyncio.wait_for(process.wait(), timeout=30)
                except asyncio.TimeoutError:
                    try: 
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        await process.wait()
                    except: pass
                await stderr_task
                async with AppState.process_lock:
                    if AppState.current_process == process: AppState.current_process = None
                # Capture actual stderr for real error logging
                if process.returncode != 0 and not AppState.cancel_task: 
                    error_msg = "".join(stderr_lines)[-3000:]
                    raise Exception(f"FFmpeg exit {process.returncode}. Log: {error_msg}")
                    
            except asyncio.CancelledError:
                await abort_current_task(status_msg, file_path, out, chat_id=chat_id_target)
                continue
            except Exception as e:
                if AppState.cancel_task:
                    await abort_current_task(status_msg, file_path, out, chat_id=chat_id_target)
                    continue
                else:
                    await status_msg.edit(Localisation.COMPRESS_FAILED)
                    await send_log(f"**Compression Failed, Bot is Free Now !!** \n\nProcess Done at {get_ist()}\nError: {e}")
                    if file_path and os.path.exists(file_path): os.remove(file_path)
                    if out and os.path.exists(out): os.remove(out)
                    continue
            finally:
                if 'stderr_task' in locals() and not stderr_task.done():
                    stderr_task.cancel()
            
            if AppState.cancel_task:
                await abort_current_task(status_msg, file_path, out, chat_id=chat_id_target)
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
                    safe_split_sec = max(30, int((MAX_SIZE / final_size) * duration_sec))
                    st_h, st_rem = divmod(safe_split_sec, 3600)
                    st_m, st_s = divmod(st_rem, 60)
                    split_time = f"{st_h:02d}:{st_m:02d}:{st_s:02d}"

                split_cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-nostdin",
                    "-i", out, "-c", "copy", "-f", "segment", "-segment_time", split_time, 
                    "-reset_timestamps", "1", f"{base_name}_part%03d{ext}"
                ]
                s_proc = await asyncio.create_subprocess_exec(
                    *split_cmd, 
                    stdin=asyncio.subprocess.DEVNULL,
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
                            reply_parameters=ReplyParameters(message_id=msg.id)
                        )
                    else:
                        uploaded_msg = await active_client.send_video(
                            chat_id=msg.chat.id, video=upload_file, thumb=actual_thumb, caption=final_caption,
                            progress=progress_bar, progress_args=("Uploading", status_msg, upload_start, last_up_time),
                            reply_parameters=ReplyParameters(message_id=msg.id)
                        )
                        
                    if uploaded_msg:
                        _, new_dc_str = get_file_info(uploaded_msg)
                        updated_caption = f"✅ <b>{upload_file}</b>\n**Size:** {part_size_str}\n**Data Center:** {new_dc_str}\n\n<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@{AppState.bot_username}</b>"
                        if len(files_to_upload) > 1: updated_caption = f"**[Part {idx+1}/{len(files_to_upload)}]**\n" + updated_caption
                        await uploaded_msg.edit_caption(updated_caption)

                except asyncio.CancelledError:
                    upload_aborted = True
                    await abort_current_task(status_msg, file_path, out, chat_id=chat_id_target)
                except Exception as e:
                    if AppState.cancel_task or "Cancelled" in str(e) or "400" in str(e):
                        upload_aborted = True
                        await abort_current_task(status_msg, file_path, out, chat_id=chat_id_target)
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
            if out and os.path.exists(out): os.remove(out)
            for f in files_to_upload:
                if os.path.exists(f): os.remove(f)
            if actual_thumb and actual_thumb != custom_thumb and actual_thumb != default_thumb and os.path.exists(actual_thumb): 
                os.remove(actual_thumb)
            
            AppState.task_state = TaskState.IDLE
            AppState.cancel_task = False
            AppState.active_file_name = "None"
            AppState.active_origin_msg = None
            AppState.active_status_msg = None
            AppState.status_snapshot = ""
            AppState.task_kind = "compress"
            if queue.empty(): AppState.task_state = TaskState.IDLE
            
            queue.task_done()