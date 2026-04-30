import time
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.helper_funcs.utils import AppState, get_sys_stats, queue, get_ist, get_readable_time, START_TIME

def humanbytes(size):
    if not size: return "0 B"
    power = 1024
    n = 0
    Dic_powerN = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {Dic_powerN[n]}"

def time_formatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0: return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    if minutes > 0: return f"{minutes:02d}m {seconds:02d}s"
    return f"{seconds:02d}s"

def make_bar(percent):
    done = int(percent / (100 / 15))
    return "▣" * done + "□" * (15 - done)

# FIX: Separate rendering engine just for the /status command!
def render_active_status(percent, done_str, total_str, eta_str, speed_str, elapsed_str):
    cpu, mem, disk = get_sys_stats()
    import psutil
    free_disk_gb = round(psutil.disk_usage('/').free / (1024**3), 2)
    uptime_str = get_readable_time((time.time() - START_TIME)*1000)
    net = psutil.net_io_counters()
    
    text = (
        f"**🌐 Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs 🌐**\n\n"
        f"`{AppState.active_file_name}`\n"
        f"[{make_bar(percent)}] {percent:.2f}%\n"
        f"**Processed:** {done_str} **of** {total_str}\n"
        f"**Status:** {AppState.task_state} | **ETA:** {eta_str}\n"
        f"**Speed:** {speed_str}/s | **Elapsed:** {elapsed_str}\n\n"
        f"**📥 Files in Queue:** {queue.qsize()}\n\n"
        f"**🖥 Hardware Info:**\n"
        f"**CPU:** {cpu}% | **Free:** {free_disk_gb}GB ({100-disk}%)\n"
        f"**In:** {humanbytes(net.bytes_recv)} | **Out:** {humanbytes(net.bytes_sent)}\n"
        f"**Ram:** {mem}% | **Uptime:** {uptime_str}\n\n"
        f"**🏷Maintained By: @Subhasish_bot**"
    )
    return text

async def progress_bar(current, total, status_text, message, start_time, last_update_time):
    # FIX: ONLY trigger the hard break. Do not wipe the flag.
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

        # FIX: AppState separates the UI variables so Main never overwrites /status!
        AppState.status_snapshot = render_active_status(percent, done_str, total_str, eta_str, speed_str, elapsed_str)

        text = (
            f"ℹ️ **sᴛᴀᴛᴜs:** {header}\n\n"
            f"[{make_bar(percent)}]\n"
            f"☞☢️ **ᴘʀᴏɢʀᴇss:** {percent:.2f}%\n"
            f"📦 **sɪᴢᴇ:** {done_str} of {total_str}\n"
            f"⚡️ **ꜱᴘᴇᴇᴅ:** {speed_str}/s\n"
            f"⏱️ **ᴇᴛᴀ:** {eta_str}\n"
            f"🖥 CPU: {cpu}% | 💽 RAM: {mem}%"
        )
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_running")]])
        
        try:
            await message.edit(text, reply_markup=btn)
            last_update_time[0] = now
        except Exception: pass