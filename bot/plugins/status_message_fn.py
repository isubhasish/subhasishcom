import time
import asyncio
from pyrogram import filters
from bot.__init__ import bot_app, config_data
from bot.helper_funcs.utils import AppState, TaskState, queue, get_sys_stats, get_network_io, get_readable_time, START_TIME
from bot.helper_funcs.display_progress import humanbytes

def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    return user_id in config_data["AUTH_USERS"] or user_id == config_data["OWNER_ID"] or chat_id in config_data["AUTH_USERS"]

# FIX: Added aggressive prefixes to guarantee Supergroup responsiveness!
@bot_app.on_message(filters.command("status", prefixes=["/", "!", "."]))
async def status_cmd(client, message):
    if not is_sudo(message): return
    
    if AppState.task_state != TaskState.IDLE and AppState.status_snapshot:
        text = AppState.status_snapshot
    else:
        cpu, mem, disk = get_sys_stats()
        sent, recv = get_network_io()
        import psutil
        free_disk_gb = round(psutil.disk_usage('/').free / (1024**3), 2)
        uptime_str = get_readable_time((time.time() - START_TIME)*1000)
        
        text = (
            f"**🌐 Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs 🌐**\n\n"
            f"**Status:** Idle\n\n"
            f"**📥 Files in Queue:** {queue.qsize()}\n\n"
            f"**🖥 Hardware Info:**\n"
            f"**CPU:** {cpu}% | **Free:** {free_disk_gb}GB ({100-disk}%)\n"
            f"**In:** {humanbytes(recv)} | **Out:** {humanbytes(sent)}\n"
            f"**Ram:** {mem}% | **Uptime:** {uptime_str}\n\n"
            f"**🏷Maintained By: @Subhasish_bot**"
        )
    
    msg = await message.reply(text)
    
    await asyncio.sleep(30)
    try: await message.delete()
    except: pass
    try: await msg.delete()
    except: pass