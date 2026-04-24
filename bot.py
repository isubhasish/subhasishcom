import os
import sys
import asyncio
import logging
import time
import re
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

# --- GLOBALS & TRACKERS ---
START_TIME = time.time()
current_process = None  # Tracks the active FFmpeg task for the /cancel command

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

# This logs you in as a User to unlock the 4GB limit
app = Client("subhasish_compressor", api_id=API_ID, api_hash=API_HASH)
queue = asyncio.Queue()

# --- YOUR DYNAMIC SETTINGS ---
settings = {
    "crf": 28,          
    "resolution": 720,
    "audio": "libopus -b:a 160k -vbr on",  
    "preset": "medium"  
}

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
        current_process.terminate()  # Kills the active FFmpeg process instantly
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
    
    # Must use .mkv for Opus audio compatibility
    if not output_path.endswith('.mkv'):
         output_path = output_path.rsplit('.', 1)[0] + '.mkv'

    status_msg = await message.reply(f"⚙️ Compressing (CRF {settings['crf']}, {settings['preset']})...")
    logger.info(f"FFmpeg running for HEVC: {input_path}")

    scale_val = f"scale={settings['resolution']}" if "x" in str(settings['resolution']) else f"scale=-2:{settings['resolution']}"
    
    cmd = [
        "ffmpeg", "-i", input_path,
        "-c:v", "libx265", 
        "-crf", str(settings["crf"]),
        "-preset", settings["preset"],
        "-vf", scale_val,  
        "-c:a", settings["audio"],
        "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    current_process = process # Set global for /cancel command
    
    # --- LIVE TIMER DISPLAY ---
    last_update_time = time.time()
    while True:
        line = await process.stderr.readline()
        if not line:
            break
        line_str = line.decode('utf-8', errors='ignore').strip()
        
        if "time=" in line_str:
            time_match = re.search(r"time=(\d{2}:\d{2}:\d{2})", line_str)
            # Update message every 5 seconds to avoid Telegram rate limits
            if time_match and (time.time() - last_update_time > 5):
                try:
                    await status_msg.edit(
                        f"⚙️ **Compressing...**\n"
                        f"⏱ **Time Encoded:** `{time_match.group(1)}`\n"
                        f"*(CRF {settings['crf']}, {settings['preset']})*\n\n"
                        f"💡 *Type /cancel to stop this task.*"
                    )
                    last_update_time = time.time()
                except:
                    pass

    await process.wait()
    
    if current_process == process:
        current_process = None

    if process.returncode != 0:
        logger.warning("Compression cancelled or crashed.")
        if os.path.exists(output_path):
            os.remove(output_path) 
        try:
            await status_msg.edit("🛑 **Task Cancelled or Failed.**")
        except:
            pass
        return 

    if os.path.exists(output_path):
        logger.info("Uploading compressed file...")
        await status_msg.edit("☁️ **Upload in progress...**")
        await message.reply_video(output_path, caption="✅ Compressed Successfully!")
        os.remove(output_path)
        logger.info("Upload finished.")
    else:
        logger.error("Output missing. Compression failed.")
        await status_msg.edit("❌ Compression failed.")
    
    await status_msg.delete()

# --- INCOMING HANDLERS ---
@app.on_message((filters.video | filters.document) & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def handle_video(client, message: Message):
    status = await message.reply("📥 **Downloading...**")
    
    last_download_update = time.time()
    async def progress(current, total):
        nonlocal last_download_update
        if time.time() - last_download_update > 3: 
            percent = current * 100 / total
            try:
                await status.edit(f"📥 **Downloading:** `{percent:.1f}%`")
                last_download_update = time.time()
            except:
                pass

    file_path = await message.download(progress=progress)
    await queue.put((message, file_path, "Telegram_Video"))
    await status.edit(f"✅ **Downloaded & Queued!**\nPosition in queue: {queue.qsize()}")

@app.on_message(filters.text & filters.regex(r"http[s]?://") & (filters.me | filters.chat("YOUR_GROUP_ID_HERE")))
async def handle_direct_link(client, message: Message):
    file_path = await download_link(message.text, message)
    if file_path:
        await queue.put((message, file_path, message.text))
        await message.reply(f"✅ **Link Queued!**\nPosition in queue: {queue.qsize()}")

# --- START ---
if __name__ == "__main__":
    logger.info("Starting up Modern Compressor...")
    loop = asyncio.get_event_loop()
    loop.create_task(worker())
    app.run()