import os
import json
import time
import asyncio
import signal
import traceback
import re
from bot import logger, bot_app
from bot.helper_funcs.utils import AppState, get_sys_stats, kill_running_process
from bot.helper_funcs.display_progress import humanbytes, time_formatter, make_bar, render_active_status
from pyrogram.errors import MessageNotModified, FloodWait

async def safe_readline(stream, timeout=10):
    try:
        return await asyncio.wait_for(stream.readline(), timeout=timeout)
    except asyncio.TimeoutError:
        return None

async def get_video_signature(file_path: str) -> dict:
    """
    Scans a video file using ffprobe and returns a 'signature' of its streams.
    This is the core of the Smart Detector.
    """
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        
        if not stdout:
            return {"error": "Could not read media streams."}
            
        data = json.loads(stdout.decode('utf-8', errors='ignore'))
        streams = data.get("streams", [])
        
        if not streams:
            return {"error": "No streams found in the file."}
            
        signature = {
            "video_codecs": [],
            "audio_codecs": [],
            "subtitle_codecs": [],
            "total_streams": len(streams)
        }
        
        for s in streams:
            codec = s.get("codec_name", "unknown")
            if s.get("codec_type") == "video":
                signature["video_codecs"].append(codec)
            elif s.get("codec_type") == "audio":
                signature["audio_codecs"].append(codec)
            elif s.get("codec_type") == "subtitle":
                signature["subtitle_codecs"].append(codec)
                
        # Sort them so order doesn't cause false mismatches
        signature["video_codecs"].sort()
        signature["audio_codecs"].sort()
        signature["subtitle_codecs"].sort()
        
        return {"success": True, "signature": signature}
        
    except asyncio.TimeoutError:
        try: os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except: pass
        return {"error": "FFprobe timed out while scanning the file."}
    except Exception as e:
        return {"error": f"Error scanning file: {str(e)}"}

def compare_signatures(sig1: dict, sig2: dict) -> tuple[bool, str]:
    """
    Compares two video signatures to ensure they are 100% safe to merge.
    """
    if sig1["total_streams"] != sig2["total_streams"]:
        return False, f"Stream count mismatch! Base video has {sig1['total_streams']} streams, but new video has {sig2['total_streams']}."
        
    if sig1["video_codecs"] != sig2["video_codecs"]:
        return False, f"Video codec mismatch! Expected {sig1['video_codecs']}, got {sig2['video_codecs']}."
        
    if sig1["audio_codecs"] != sig2["audio_codecs"]:
        return False, f"Audio codec mismatch! Expected {sig1['audio_codecs']}, got {sig2['audio_codecs']}."
        
    return True, "Compatible"

async def run_mkvmerge(input_files: list, output_file: str, status_msg, cancel_markup, title: str = None) -> bool: 
    if len(input_files) < 2:
        raise ValueError("At least 2 files are required to merge.")

    total_size_bytes = sum(os.path.getsize(f) for f in input_files if os.path.exists(f))
    
    cmd = ["mkvmerge", "--gui-mode", "-o", output_file]

    if title:
        cmd.extend(["--title", title])

    cmd.append(input_files[0])
    for f in input_files[1:]:
        cmd.extend(["+", f])
        
    start_time = time.time()
    last_update_time = time.time() - 10

    cpu, mem, _ = get_sys_stats()
    AppState.status_snapshot = render_active_status(
        0.0, "0 B", humanbytes(total_size_bytes), "Calculating...", "0 B", "0s", display_status="Merging Videos"
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True
        )
        
        async with AppState.process_lock:
            AppState.current_process = process
        output_log = [] 
        progress_logged = False

        while True:
            if AppState.cancel_task:
                await kill_running_process()
                raise asyncio.CancelledError("Merge Task Cancelled by User")

            line_bytes = await safe_readline(process.stdout, timeout=5)
            
            if line_bytes is None:
                if process.returncode is not None: break
                continue

            if line_bytes == b"":
                break
                
            line_str = line_bytes.decode('utf-8', errors='ignore').strip()
            
            if not line_str:
                continue

            output_log.append(line_str)

            # 🧠 CLAUDE FIX 1: Bulletproof progress detection
            if not progress_logged and ("progress" in line_str.lower()):
                logger.info("✅ MKVMerge progress detected successfully.")
                progress_logged = True

            # 🧠 CLAUDE FIX 2: Bulletproof Regex to catch any percentage format
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", line_str)
            
            if match:
                try:
                    percent = float(match.group(1))
                    
                    now = time.time()
                    if now - last_update_time >= 3.5:
                        elapsed = max(now - start_time, 0.001)
                        current_bytes = (percent / 100.0) * total_size_bytes
                        speed = current_bytes / elapsed if elapsed > 0 else 0
                        eta = (total_size_bytes - current_bytes) / speed if speed > 0 else 0
                        
                        cpu, mem, _ = get_sys_stats()
                        
                        done_str = humanbytes(current_bytes)
                        total_str = humanbytes(total_size_bytes)
                        speed_str = humanbytes(speed)
                        eta_str = time_formatter(eta * 1000)
                        elapsed_str = time_formatter(elapsed * 1000)
                        
                        AppState.status_snapshot = render_active_status(
                            percent, done_str, total_str, eta_str, speed_str, elapsed_str, display_status="Merging Videos"
                        )
                        
                        text = (
                            f"ℹ️ **ɴᴏᴡ:** 💡 MERGING VIDEOS...💡\n\n"
                            f"⏱️ **ᴇᴛᴀ:** {eta_str}\n\n"
                            f"[{make_bar(percent)}] {percent:.2f}%\n\n"
                            f"⚡️ **ꜱᴘᴇᴇᴅ:** {speed_str}/s\n"
                            f"⏰ **ᴇʟᴀᴘsᴇᴅ:** {elapsed_str}\n"
                            f"📦 **sɪᴢᴇ:** {done_str} of {total_str}\n\n"
                            f"🖥 CPU: {cpu}% | 💽 RAM: {mem}%"
                        )

                        try:
                            await bot_app.edit_message_text(
                                chat_id=status_msg.chat.id,
                                message_id=status_msg.id,
                                text=text,
                                reply_markup=cancel_markup
                            )
                            last_update_time = now
                        except MessageNotModified:
                            last_update_time = now
                        except FloodWait as e:
                            await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
                            # 🧠 CLAUDE FIX 3: Reset timer after FloodWait to prevent deadlock
                            last_update_time = time.time()
                        except Exception as e:
                            logger.error(f"MERGE EDIT FAILED [{type(e).__name__}] {e}")
                            last_update_time = now
                except ValueError:
                    continue

        await process.wait()
        
        async with AppState.process_lock:
            if AppState.current_process == process:
                AppState.current_process = None

        if process.returncode != 0 and process.returncode != 1:
            if not AppState.cancel_task:
                error_msg = "\n".join(output_log)[-3000:]
                logger.error(f"mkvmerge failed with code {process.returncode}: {error_msg}")
                return False
                
        return True

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"[MERGE ERROR] {e}\n{traceback.format_exc()}")
        return False
    finally:
        await kill_running_process()