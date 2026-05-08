import time
import os
import math
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.helper_funcs.utils import AppState, get_sys_stats, START_TIME, get_readable_time

def humanbytes(size):
    if not size: return "0 B"
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if size < 1024.0:
            return "%3.2f %sB" % (size, unit)
        size /= 1024.0
    return "%.2f PB" % (size)

def compact_time(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0: return f"{hours:02d}h{minutes:02d}m{seconds:02d}s"
    elif minutes > 0: return f"{minutes:02d}m{seconds:02d}s"
    else: return f"{seconds:02d}s"

def time_formatter(milliseconds: int) -> str:
    return compact_time(milliseconds / 1000)

def make_bar(percent):
    done = int(percent / 100 * 10)
    return "▣" * done + "□" * (10 - done)

def render_active_status(percent, done_str, total_str, eta_str, speed_str, elapsed_str, display_status=None):
    cpu, mem, disk = get_sys_stats()
    import psutil
    free_disk_gb = round(psutil.disk_usage('/').free / (1024**3), 2)
    uptime_str = get_readable_time((time.time() - START_TIME) * 1000)
    net = psutil.net_io_counters()
    
    status_text = display_status if display_status else AppState.task_state
    
    text = (
        f"🌐 <b><u>Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs</u></b> 🌐\n\n"
        f"`{AppState.active_file_name}`\n"
        f"[{make_bar(percent)}] {percent:.2f}%\n"
        f"**Processed:** {done_str} of {total_str}\n"
        f"**Status:** {status_text} | **ETA:** {eta_str}\n"
        f"**Speed:** {speed_str}/s | **Elapsed:** {elapsed_str}\n\n"
        f"🔰 <b><u>Hardware Info:</u></b> 🔰\n"
        f"**CPU:** {cpu}% | **Free:** {free_disk_gb}GB ({100-disk}%)\n"
        f"**In:** {humanbytes(net.bytes_recv)} | **Out:** {humanbytes(net.bytes_sent)}\n"
        f"**Ram:** {mem}% | **Uptime:** {uptime_str}\n\n"
        f"**🏷 Maintained By: @Subhasish_bot**"
    )
    return text

async def progress_bar(current, total, status_text, message, start_time, last_update_time):
    if AppState.cancel_task:
        raise asyncio.CancelledError("Task Cancelled by User")

    now = time.time()
    if round((now - last_update_time[0])) >= 5 or current == total:
        percent = current * 100 / total
        speed = current / (now - start_time)
        eta_ms = round((total - current) / speed) * 1000 if speed > 0 else 0
        
        cpu, mem, disk = get_sys_stats()
        
        if "Downloading" in status_text: header = "📥 Downloading ... 📥"
        elif "Uploading" in status_text: header = "📤 Uploading ... 📤"
        else: header = "💡 ENCODING...💡"
        
        done_str = humanbytes(current)
        total_str = humanbytes(total)
        speed_str = humanbytes(speed)
        eta_str = time_formatter(eta_ms)
        elapsed_str = time_formatter((now - start_time)*1000)

        AppState.status_snapshot = render_active_status(percent, done_str, total_str, eta_str, speed_str, elapsed_str, display_status=status_text)

        text = (
            f"ℹ️ **sᴛᴀᴛᴜs:** {header}\n\n"
            f"[{make_bar(percent)}]\n"
            f"☞☢️ **ᴘʀᴏɢʀᴇss:** {percent:.2f}%\n"
            f"📦 **sɪᴢᴇ:** {done_str} of {total_str}\n"
            f"⚡️ **ꜱᴘᴇᴇᴅ:** {speed_str}/s\n"
            f"⏱️ **ᴇᴛᴀ:** {eta_str}\n"
            f"🖥 CPU: {cpu}% | 💽 RAM: {mem}%"
        )
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task 🔴", callback_data="cancel_running")]])
        
        try:
            await message.edit(text, reply_markup=btn)
            last_update_time[0] = now
        except Exception: pass