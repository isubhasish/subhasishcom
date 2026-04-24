import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

# --- LOGGING SETUP (Real-time Putty Logs) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler()] # Outputs directly to Putty console
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 1234567     # Get from my.telegram.org
API_HASH = "your_api_hash"

# To bypass the 2GB limit and allow 4GB, you must log in as a User, NOT a bot.
# When you run this script for the first time, Putty will ask for your phone number 
# and login code. It will save a session file so you only do it once.
app = Client("subhasish_compressor", api_id=API_ID, api_hash=API_HASH)
queue = asyncio.Queue()

# --- YOUR DYNAMIC SETTINGS ---
settings = {
    "crf": 28,          # 26-28 is the sweet spot for HEVC (H.265) 200MB targets
    "resolution": 720,
    "audio": "aac",
    "preset": "medium"  # slower = better compression, but takes longer
}

# --- COMMANDS ---
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
        settings["resolution"] = int(message.command[1])
        await message.reply(f"✅ Resolution set to: {settings['resolution']}p")
    except:
        await message.reply("Use: /setres 720")

@app.on_message(filters.command("settings") & filters.me)
async def check_settings(client, message):
    text = (f"🛠 **Current Encoding Settings**\n\n"
            f"CRF: `{settings['crf']}`\n"
            f"Resolution: `{settings['resolution']}p`\n"
            f"Audio: `{settings['audio']}`\n"
            f"Preset: `{settings['preset']}`")
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
            await message.reply("❌ Fatal error during compression.")
        finally:
            queue.task_done()
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Cleaned up original file.")

async def process_video(message, input_path):
    output_path = f"compressed_{os.path.basename(input_path)}"
    if not output_path.endswith('.mp4'):
         output_path = output_path.rsplit('.', 1)[0] + '.mp4'

    status_msg = await message.reply(f"⚙️ Compressing (CRF {settings['crf']}, {settings['preset']})... Check Putty logs.")
    logger.info(f"FFmpeg running for HEVC: {input_path}")

    # HEVC (H.265) Command for maximum compression / best quality
    cmd = [
        "ffmpeg", "-i", input_path,
        "-c:v", "libx265", 
        "-crf", str(settings["crf"]),
        "-preset", settings["preset"],
        "-vf", f"scale=-2:{settings['resolution']}",
        "-c:a", settings["audio"],
        "-y", output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    await process.wait()

    if os.path.exists(output_path):
        logger.info("Uploading compressed file to Telegram...")
        await status_msg.edit("☁️ Uploading...")
        await message.reply_video(output_path, caption="✅ Compressed Successfully!")
        os.remove(output_path)
        logger.info("Upload finished.")
    else:
        logger.error("Output missing. Compression failed.")
        await status_msg.edit("❌ Compression failed.")
    
    await status_msg.delete()

# --- INCOMING HANDLERS ---
@app.on_message((filters.video | filters.document) & filters.me)
async def handle_video(client, message: Message):
    logger.info(f"Incoming video detected. Size: {message.video.file_size if message.video else 'Unknown'}")
    status = await message.reply("📥 Downloading to Oracle server...")
    
    async def progress(current, total):
        # Prevent log spam, print every 10%
        percent = current * 100 / total
        if int(percent) % 10 == 0:
            logger.info(f"Downloading: {percent:.1f}%")

    file_path = await message.download(progress=progress)
    await queue.put((message, file_path, "Telegram_Video"))
    await status.edit(f"✅ Added to Queue. Position: {queue.qsize()}")

@app.on_message(filters.text & filters.regex(r"http[s]?://") & filters.me)
async def handle_direct_link(client, message: Message):
    url = message.text
    logger.info(f"Incoming link: {url}")
    file_path = await download_link(url, message)
    if file_path:
        await queue.put((message, file_path, url))
        await message.reply(f"✅ Added to Queue. Position: {queue.qsize()}")

# --- START ---
if __name__ == "__main__":
    logger.info("Starting up Subhasish's Modern Compressor...")
    loop = asyncio.get_event_loop()
    loop.create_task(worker())
    app.run()