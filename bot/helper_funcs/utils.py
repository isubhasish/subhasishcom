import asyncio
import time
import os
import signal
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
    cancel_task = False
    cancelling = False
    task_state = TaskState.IDLE
    active_file_name = "None"
    active_origin_msg = None
    main_progress_text = ""
    status_snapshot = ""
    pending_tasks = {}
    awaiting_index = {}
    bot_username = "Bot"
    bsetting_state = {}
    is_premium = False

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

def get_readable_time(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "")
        + ((str(hours) + "h, ") if hours else "")
        + ((str(minutes) + "m, ") if minutes else "")
        + ((str(seconds) + "s") if seconds else "")
    )
    return tmp

def get_ist():
    tz = timezone(timedelta(hours=5, minutes=30))
    return f"\n`{datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')} (GMT+05:30)`\n"

async def send_log(msg_text: str):
    log_channel = config_data.get("LOG_CHANNEL")
    if log_channel:
        try:
            await bot_app.send_message(log_channel, msg_text)
        except Exception as e:
            logger.error(f"Failed to send log: {e}")

def get_sys_stats():
    import psutil
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return cpu, mem, disk

def get_network_io():
    import psutil
    net = psutil.net_io_counters()
    sent = net.bytes_sent
    recv = net.bytes_recv
    return sent, recv

def get_file_info(message):
    media = message.video or message.document
    if not media: return "Unknown", "Unknown"
    size_bytes = media.file_size
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