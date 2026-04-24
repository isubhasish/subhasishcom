import os
import sys
import asyncio
import logging
import time
import re
import math
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

# --- GLOBALS & TRACKERS ---
START_TIME = time.time()
current_process = None  

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler()] 
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 1234567     # Replace with your actual API ID
API_HASH = "your_api_hash" # Replace with your actual API HASH

app = Client("subhasish_compressor", api_id=API_ID, api_hash=API_HASH)
queue = asyncio.Queue()

# --- YOUR DYNAMIC SETTINGS ---
settings = {
    "crf": 28,          
    "resolution": 720,
    "audio": "libopus -b:a 160k -vbr on",  
    "preset": "medium"  
}

# --- PROGRESS BAR HELPERS ---
def humanbytes(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    Dic_powerN = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {Dic_powerN[n]}"

def time_formatter(milliseconds):
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def make_bar(percent):
    filled = int(percent / 5)
    return "█" * filled + "░" * (20 - filled)

async def progress_for_pyrogram(current, total, ud_type, message, start_time, last_update_time):
    if time.time() - last_update_time[0] > 3: # Update every 3 seconds
        now = time.time()
        diff = now - start_time
        speed = current / diff if diff > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0
        percent = (current / total) * 100 if total > 0 else 0
        
        text = (
            f"{ud_type}\n"
            f"[{make_bar(percent)}] `{percent:.1f}%`\n\n"
            f"📦 **Size:** `{humanbytes(current)} / {humanbytes(total)}`\n"
            f"🚀 **Speed:** `{humanbytes(speed)}/s`\n"
            f"⏱ **ETA:** `{time_formatter(eta * 1000)}`"
        )
        try:
            await message.edit(text)
            last_update_time[0] = now
        except:
            pass

# --- UTILITY COMMANDS ---
@app.on_message(filters.command("start") & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def start_cmd(client, message):
    await message.reply("🤖 **Premium Compressor is Online!**\nSend me a video or link to begin.")

@app.on_message(filters.command("ping") & filters.me)
async def ping_cmd(client, message):
    uptime = int(time.time() - START_TIME)
    mins, secs = divmod(uptime, 60)
    hours, mins = divmod(mins, 60)
    await message.reply(f"🏓 **Pong! Bot is active.**\n\n🕒 **Uptime:** `{hours}h {mins}m {secs}s`")

@app.on_message(filters.command("clear") & filters.me)
async def clear_cmd(client, message):
    while not queue.empty():
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break
    await message.reply("🗑️ **Queue Cleared!** All pending videos have been removed.")

@app.on_message(filters.command("restart") & filters.me)
async def restart_cmd(client, message):
    await message.reply("🔄 **Restarting server script...** Please wait.")
    os.execl(sys.executable, sys.executable, *sys.argv)

@app.on_message(filters.command("cancel") & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def cancel_cmd(client, message):
    global current_process
    if current_process:
        current_process.terminate()  
        await message.reply("🛑 **Task Cancelled.** Moving to next in queue...")
        current_process = None
    else:
        await message.reply("⚠️ No active compression task running right now.")

# --- SETTINGS COMMANDS ---
@app.on_message(filters.command("setcrf") & filters.me)
async def set_crf(client, message):
    try:
        settings["crf"] = int(message.command[1])
        await message.reply(f"✅ CRF set to: {settings['crf']}")
    except:
        await message.reply("Use: /setcrf 28")

@app.on_message(filters.command("setpreset") & filters.me)
async def set_preset(client, message):
    try:
        settings["preset"] = message.command[1]
        await message.reply(f"✅ Preset set to: {settings['preset']}")
    except:
        await message.reply("Use: /setpreset fast/medium/slow")

@app.on_message(filters.command("setres") & filters.me)
async def set_res(client, message):
    try:
        val = message.command[1]
        settings["resolution"] = val
        await message.reply(f"✅ Resolution set to: {val}")
    except:
        await message.reply("Use: /setres 720 OR /setres 820x480")

@app.on_message(filters.command("settings") & filters.me)
async def check_settings(client, message):
    text = (f"🛠 **Current Encoding Settings**\n\n"
            f"CRF: `{settings['crf']}`\n"
            f"Resolution: `{settings['resolution']}p`\n"
            f"Audio: `{settings['audio']}`\n"
            f"Preset: `{settings['preset']}`")
    await message.reply(text)

@app.on_message(filters.command("metadata") & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def check_metadata(client, message):
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply("⚠️ Please reply to a video file with /metadata.")
        return
    vid = message.reply_to_message.video
    size_mb = vid.file_size / (1024 * 1024) if vid.file_size else 0
    text = (f"📊 **Video Metadata**\n\n"
            f"**Name:** `{vid.file_name or 'Unknown'}`\n"
            f"**Size:** `{size_mb:.2f} MB`\n"
            f"**Resolution:** `{vid.width} x {vid.height}`\n"
            f"**Duration:** `{vid.duration} seconds`\n"
            f"**Mime Type:** `{vid.mime_type}`")
    await message.reply(text)

# --- DIRECT LINK DOWNLOADER ---
async def download_link(url, message):
    ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s'}
    os.makedirs('downloads', exist_ok=True)
    status = await message.reply("🔗 Downloading link safely...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            await status.delete()
            return filename
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status.edit("❌ Failed to download.")
        return None

# --- QUEUE & FFMPEG WORKER ---
async def worker():
    logger.info("Worker started. Waiting for videos...")
    while True:
        message, file_path, original_name = await queue.get()
        logger.info(f"Starting job: {original_name}")
        try:
            await process_video(message, file_path)
        except Exception as e:
            logger.error(f"Crash during processing: {e}")
            try:
                await message.reply("❌ Fatal error during compression.")
            except:
                pass
        finally:
            queue.task_done()
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Cleaned up original file.")

async def process_video(message, input_path):
    global current_process
    output_path = f"compressed_{os.path.basename(input_path)}"
    
    if not output_path.endswith('.mkv'):
         output_path = output_path.rsplit('.', 1)[0] + '.mkv'

    status_msg = await message.reply("⚙️ **Preparing Compression...**")
    logger.info(f"FFmpeg running for HEVC: {input_path}")

    scale_val = f"scale={settings['resolution']}" if "x" in str(settings['resolution']) else f"scale=-2:{settings['resolution']}"
    audio_args = settings["audio"].split()
    
    cmd = [
        "ffmpeg", "-i", input_path,
        "-c:v", "libx265", 
        "-crf", str(settings["crf"]),
        "-preset", settings["preset"],
        "-vf", scale_val,  
        "-c:a"
    ] + audio_args + [
        "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    current_process = process 
    
    # --- LIVE FFMPEG PROGRESS TRACKER ---
    last_update_time = time.time()
    duration_sec = 0
    start_time = time.time()

    while True:
        line = await process.stderr.readline()
        if not line:
            break
        line_str = line.decode('utf-8', errors='ignore').strip()
        
        # Get total duration to calculate ETA
        if not duration_sec and "Duration:" in line_str:
            match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})", line_str)
            if match:
                duration_sec = int(match.group(1))*3600 + int(match.group(2))*60 + int(match.group(3))

        if "time=" in line_str:
            time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line_str)
            if time_match and (time.time() - last_update_time > 5):
                curr_sec = int(time_match.group(1))*3600 + int(time_match.group(2))*60 + int(time_match.group(3))
                
                if duration_sec > 0:
                    percent = (curr_sec / duration_sec) * 100
                    elapsed = time.time() - start_time
                    speed = curr_sec / elapsed if elapsed > 0 else 0
                    eta = (duration_sec - curr_sec) / speed if speed > 0 else 0
                    
                    text = (
                        f"⚙️ **Processing Video**\n"
                        f"[{make_bar(percent)}] `{percent:.1f}%`\n\n"
                        f"⏱ **Time:** `{time_match.group(1)} / {time_formatter(duration_sec*1000)}`\n"
                        f"⏳ **ETA:** `{time_formatter(eta*1000)}`\n"
                        f"*(CRF {settings['crf']}, {settings['preset']})*\n\n"
                        f"💡 *Type /cancel to stop.*"
                    )
                else:
                    text = f"⚙️ **Processing Video...**\n⏱ **Time Encoded:** `{time_match.group(1)}`\n💡 *Type /cancel to stop.*"

                try:
                    await status_msg.edit(text)
                    last_update_time = time.time()
                except:
                    pass

    await process.wait()
    if current_process == process: current_process = None

    if process.returncode != 0:
        logger.warning("Compression cancelled or crashed.")
        if os.path.exists(output_path): os.remove(output_path) 
        try: await status_msg.edit("🛑 **Task Cancelled or Failed.**")
        except: pass
        return 

    # --- UPLOAD WITH PROGRESS BAR ---
    if os.path.exists(output_path):
        logger.info("Uploading compressed file...")
        upload_start = time.time()
        last_up_time = [time.time()]
        
        await message.reply_video(
            output_path, 
            caption="✅ Compressed Successfully!",
            progress=progress_for_pyrogram,
            progress_args=("☁️ **Uploading to Telegram...**", status_msg, upload_start, last_up_time)
        )
        os.remove(output_path)
        logger.info("Upload finished.")
        await status_msg.delete()
    else:
        logger.error("Output missing. Compression failed.")
        await status_msg.edit("❌ Compression failed.")

# --- INCOMING HANDLERS WITH DOWNLOAD PROGRESS ---
@app.on_message((filters.video | filters.document) & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def handle_video(client, message: Message):
    status = await message.reply("📥 **Starting Download...**")
    dl_start = time.time()
    last_up_time = [time.time()]

    file_path = await message.download(
        progress=progress_for_pyrogram,
        progress_args=("📥 **Downloading File...**", status, dl_start, last_up_time)
    )
    
    await queue.put((message, file_path, "Telegram_Video"))
    await status.edit(f"✅ **Downloaded & Queued!**\nPosition in queue: `{queue.qsize()}`")

@app.on_message(filters.text & filters.regex(r"http[s]?://") & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def handle_direct_link(client, message: Message):
    file_path = await download_link(message.text, message)
    if file_path:
        await queue.put((message, file_path, message.text))
        await message.reply(f"✅ **Link Queued!**\nPosition in queue: `{queue.qsize()}`")

# --- START ---
if __name__ == "__main__":
    logger.info("Starting up Modern Compressor...")
    loop = asyncio.get_event_loop()
    loop.create_task(worker())
    app.run()