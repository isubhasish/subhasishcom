import os
import asyncio
import time
import re
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.__init__ import user_app, logger, config_data
from bot.config import Config
from bot.helper_funcs.utils import queue, AppState
from bot.helper_funcs.display_progress import progress_bar, humanbytes, time_formatter, make_bar

async def worker():
    while True:
        msg, name, map_args, status_msg = await queue.get()
        try:
            AppState.active_file_name = name
            start_time = time.time()
            last_up = [time.time()]
            await status_msg.edit("📥 **Downloading Full File...**")
            
            # Step 1: User-Session 4GB Download
            file_path = await user_app.download_media(msg, progress=progress_bar, progress_args=("Downloading", status_msg, start_time, last_up))
            
            # Step 2: Safe renaming replacing spaces with dots
            base = name.replace(" ", ".").rsplit(".", 1)[0]
            out = f"{base}.Compressed.mkv"
            
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running")]])
            await status_msg.edit(f"⚙️ **Compressing:** `{name}`", reply_markup=btn)
            
            # Auto-replace 'x' with ':' to prevent FFmpeg syntax errors on 820x480
            res = config_data['RESOLUTION'].lower().replace("x", ":")
            
            cmd = ["ffmpeg", "-i", file_path] + map_args + [
                "-c:v", "libx265", "-crf", str(config_data["CRF"]), "-preset", config_data["PRESET"],
                "-vf", f"scale={res}", "-c:a", "libopus", "-b:a", config_data["AUDIO_BITRATE"],
                "-y", out
            ]
            
            process = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
            AppState.current_process = process
            
            last_update_time = time.time()
            duration_sec = 0

            while True:
                line = await process.stderr.readline()
                if not line: break
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                if not duration_sec and "Duration:" in line_str:
                    match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})", line_str)
                    if match: duration_sec = int(match.group(1))*3600 + int(match.group(2))*60 + int(match.group(3))

                if "time=" in line_str:
                    time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line_str)
                    if time_match and (time.time() - last_update_time > 5):
                        curr_sec = int(time_match.group(1))*3600 + int(time_match.group(2))*60 + int(time_match.group(3))
                        if duration_sec > 0:
                            percent = (curr_sec / duration_sec) * 100
                            elapsed = time.time() - start_time
                            speed = curr_sec / elapsed if elapsed > 0 else 0
                            eta = (duration_sec - curr_sec) / speed if speed > 0 else 0
                            text = f"⚙️ **Processing Video**\n`[{make_bar(percent)}] {percent:.1f}%`\n\n⏱ Time: `{time_match.group(1)} / {time_formatter(duration_sec*1000)}`\n⏳ ETA: `{time_formatter(eta*1000)}`"
                        else:
                            text = f"⚙️ **Processing Video...**\n⏱ `{time_match.group(1)}`"
                        try:
                            await status_msg.edit(text, reply_markup=btn)
                            last_update_time = time.time()
                        except: pass

            await process.wait()
            if AppState.current_process == process: AppState.current_process = None

            if process.returncode != 0:
                if os.path.exists(out): os.remove(out) 
                if os.path.exists(file_path): os.remove(file_path)
                continue

            # Step 3: Apply Thumbnail & Upload Document
            thumb_path = os.path.join(Config.THUMB_DIR, f"{msg.from_user.id}.jpg")
            actual_thumb = thumb_path if os.path.exists(thumb_path) else None

            upload_start = time.time()
            last_up_time = [time.time()]
            await user_app.send_document(
                chat_id=msg.chat.id, document=out, thumb=actual_thumb,
                caption=f"✅ **{out}**\n*(Compressed by Gemini)*", force_document=True,
                progress=progress_bar, progress_args=("☁️ **Uploading...**", status_msg, upload_start, last_up_time)
            )
            await status_msg.edit("✅ Process Complete!")
            os.remove(file_path); os.remove(out)
        except Exception as e: logger.error(e)
        finally: 
            AppState.active_file_name = "None"
            queue.task_done()