import time
import json
import asyncio
from pyrogram import filters
from bot import bot_app, config_data
from bot.helper_funcs.utils import AppState, TaskState, queue, get_sys_stats, get_network_io, get_readable_time, START_TIME
from bot.helper_funcs.display_progress import humanbytes

# FIX: Claude's Logic - Restored chat_id check for Supergroup functionality & used safe parsing.
def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    auth_users = config_data.get("AUTH_USERS", [])
    owner_id = config_data.get("OWNER_ID", 0)
    
    if isinstance(auth_users, str):
        try: auth_users = json.loads(auth_users)
        except Exception: auth_users = []
        
    return user_id in auth_users or user_id == owner_id or chat_id in auth_users

# FIX: DeepSeek's Logic - Removed the buggy prefixes list to ensure the command always fires.
@bot_app.on_message(filters.command("status"))
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