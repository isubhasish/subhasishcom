import asyncio
import time
import os
import signal
import psutil
import re
from datetime import datetime, timezone, timedelta
from pyrogram.file_id import FileId
from bot import bot_app, logger, config_data

queue = asyncio.Queue()
START_TIME = time.time()

class TaskState:
    IDLE = "Idle"
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    ENCODING = "Encoding"
    UPLOADING = "Uploading"
    CANCELLING = "Cancelling"
    SAMPLEGEN = "Generating Sample"

class AppState:
    current_process = None
    process_lock = asyncio.Lock()
    state_lock = asyncio.Lock()
    cancel_task = False
    cancelling = False
    task_state = TaskState.IDLE
    active_file_name = "None"
    active_origin_msg = None
    active_status_msg = None
    task_kind = "compress"
    main_progress_text = ""
    status_snapshot = ""
    pending_tasks = {}
    awaiting_index = {}
    bot_username = "Bot"
    bsetting_state = {}
    is_premium = False

_cpu_cache: float = 0.0

async def cpu_monitor():
    global _cpu_cache
    psutil.cpu_percent()
    await asyncio.sleep(0.5)

    while True:
        try:
            val = await asyncio.to_thread(psutil.cpu_percent, 0.5)
            _cpu_cache = val
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"CPU Monitor Error: {e}")
        await asyncio.sleep(1.5)

async def kill_running_process():
    async with AppState.process_lock:
        proc = AppState.current_process
        if not proc: return
        if AppState.cancelling: return
        AppState.cancelling = True
        try:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                await asyncio.wait_for(proc.wait(), timeout=4)
            except asyncio.TimeoutError:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                await asyncio.wait_for(proc.wait(), timeout=3)
            except Exception: pass
        except Exception: pass
        finally:
            AppState.current_process = None
            AppState.cancelling = False

async def delete_message_later(message, delay=10):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

def get_readable_time(milliseconds: int) -> str:
    seconds = int(milliseconds // 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    if days: return f"{days}d{hours:02d}h{minutes:02d}m{seconds:02d}s"
    if hours: return f"{hours:02d}h{minutes:02d}m{seconds:02d}s"
    return f"{minutes:02d}m{seconds:02d}s"

def get_ist():
    tz = timezone(timedelta(hours=5, minutes=30))
    return f"\n`{datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')} (GMT+05:30)`\n"

async def send_log(msg_text: str):
    log_channel = config_data.get("LOG_CHANNEL")
    if log_channel:
        try: 
            await asyncio.wait_for(bot_app.send_message(log_channel, msg_text), timeout=15)
        except Exception as e: 
            logger.error(f"Failed to send log: {e}")

def get_sys_stats():
    cpu  = _cpu_cache                           
    mem  = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return cpu, mem, disk

def get_network_io():
    net = psutil.net_io_counters()
    sent = net.bytes_sent
    recv = net.bytes_recv
    return sent, recv

def get_file_info(message):
    media = message.video or message.document
    if not media: return "Unknown", "Unknown"
    size_bytes = media.file_size
    size_str = "Unknown"   
    if not size_bytes: size_str = "0 B"
    else:
        for unit in ['B','KB','MB','GB','TB']:
            if size_bytes < 1024:
                size_str = f"{size_bytes:.2f} {unit}"
                break
            size_bytes /= 1024
    try:
        file_id_obj = FileId.decode(media.file_id)
        dc_id = file_id_obj.dc_id
        dc_map = {1: "Miami, USA - DC1", 2: "Amsterdam, NL - DC2", 3: "Miami, USA - DC3", 4: "Amsterdam, NL - DC4", 5: "Singapore, SG - DC5"}
        dc_str = dc_map.get(dc_id, f"DC{dc_id}")
    except: dc_str = "Unknown DC"
    return size_str, dc_str

async def download_media_chunk(active_client, message, chunk_path, limit_bytes=25 * 1024 * 1024):
    dl_size = 0
    stream = active_client.stream_media(message)
    with open(chunk_path, "wb") as f:
        try:
            stream_iter = stream.__aiter__()
            while True:
                next_task = asyncio.create_task(stream_iter.__anext__())
                try: chunk = await asyncio.wait_for(next_task, timeout=15.0)
                except asyncio.TimeoutError: next_task.cancel(); break
                except StopAsyncIteration: break
                f.write(chunk); dl_size += len(chunk)
                if dl_size >= limit_bytes: break
        finally:
            if hasattr(stream, 'aclose'):
                try: await asyncio.wait_for(stream.aclose(), timeout=5.0)
                except Exception as e: logger.debug(f"Stream aclose timed out/failed: {e}")
    return dl_size

def format_mediainfo_output(raw_info: str, file_name: str, size_str: str) -> list:
    """Universal helper to clean up mediainfo regex output and format it for Telegraph/Graph APIs."""
    raw_info = re.sub(r"^\s*(Conformance errors|General compliance|IsTruncated|FileExtension_Invalid|Overall bit rate|Matroska)\s*:.*$\n?", "", raw_info, flags=re.MULTILINE)
    raw_info = re.sub(r"^\s*Complete name\s*:.*$", f"Complete name                            : {file_name}", raw_info, flags=re.MULTILINE)
    raw_info = re.sub(r"^\s*File size\s*:.*$", f"File size                                : {size_str}", raw_info, flags=re.MULTILINE)
    
    content_json = [{"tag": "h3", "children": [file_name]}]
    current_pre = ""
    for line in raw_info.split('\n'):
        clean_line = line.strip()
        if clean_line == "General" or clean_line.startswith(("Video", "Audio", "Text", "Menu")):
            if current_pre: 
                content_json.append({"tag": "pre", "children": [current_pre]})
                current_pre = ""
            icon = "📄" if clean_line == "General" else "🎬" if clean_line.startswith("Video") else "💬" if clean_line.startswith("Text") else "📑" if clean_line.startswith("Menu") else "🔊"
            content_json.append({"tag": "h3", "children": [f"{icon} {clean_line}"]})
        elif line.strip(): 
            current_pre += line + "\n"

    if current_pre: 
        content_json.append({"tag": "pre", "children": [current_pre]})
    return content_json