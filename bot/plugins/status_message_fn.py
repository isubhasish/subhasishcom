import time, json, asyncio, psutil
from pyrogram import filters
from pyrogram.types import ReplyParameters
from pyrogram.errors import MessageNotModified, FloodWait
from bot import bot_app, config_data, logger
from bot.helper_funcs.utils import AppState, TaskState, queue, get_sys_stats, get_network_io, get_readable_time, START_TIME
from bot.helper_funcs.display_progress import humanbytes

UNAUTH_MSG = "<b>You are not allowed to do that 🤭</b>"
ACTIVE_STATUS = {}

def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    auth_users = config_data.get("AUTH_USERS", [])
    if isinstance(auth_users, str):
        try: auth_users = json.loads(auth_users)
        except Exception: auth_users = []
    if not isinstance(auth_users, list): auth_users = [auth_users] if auth_users else []
    return user_id in auth_users or user_id == config_data.get("OWNER_ID", 0)

def get_idle_text():
    cpu, mem, disk = get_sys_stats()
    sent, recv = get_network_io()
    free_disk_gb = round(psutil.disk_usage('/').free / (1024**3), 2)
    uptime_str = get_readable_time((time.time() - START_TIME)*1000)
    
    return (
        f"🌐 <b><u>Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs</u></b> 🌐\n\n"
        f"**Status:** Idle\n\n"
        f"**📥 Files in Queue:** {queue.qsize()}\n\n"
        f"🔰 <b><u>Hardware Info:</u></b> 🔰\n"
        f"**CPU:** {cpu}% | **Free:** {free_disk_gb}GB ({100-disk}%)\n"
        f"**In:** {humanbytes(recv)} | **Out:** {humanbytes(sent)}\n"
        f"**Ram:** {mem}% | **Uptime:** {uptime_str}\n\n"
        f"**🏷 Maintained By: @Subhasish_bot**"
    )

async def auto_delete_unauth(msg):
    await asyncio.sleep(10)
    try: await msg.delete()
    except Exception: pass

@bot_app.on_message(filters.command("status"))
async def status_cmd(client, message):
    if not is_sudo(message): 
        unauth_msg = await bot_app.send_message(message.chat.id, UNAUTH_MSG, reply_parameters=ReplyParameters(message_id=message.id))
        asyncio.create_task(auto_delete_unauth(unauth_msg))
        return
    chat_id = message.chat.id
    if chat_id in ACTIVE_STATUS:
        try: await bot_app.delete_messages(chat_id, [ACTIVE_STATUS[chat_id]["u"], ACTIVE_STATUS[chat_id]["b"]])
        except Exception: pass
    if AppState.task_state != TaskState.IDLE:
        text = AppState.status_snapshot or (
            f"🌐 <b><u>Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs</u></b> 🌐\n\n"
            f"**Status:** {AppState.task_state}\n\n"
            f"**📥 Files in Queue:** {queue.qsize()}"
        )
    else: text = get_idle_text()
    msg = await bot_app.send_message(message.chat.id, text, reply_parameters=ReplyParameters(message_id=message.id))
    ACTIVE_STATUS[chat_id] = {"u": message.id, "b": msg.id}
    total_target_time = 30.0
    time_per_loop = 4.0
    loop_start_time = time.perf_counter()
    time_elapsed = 0.0

    for _ in range(7):
        time_left = total_target_time - time_elapsed
        if time_left <= 0:
            break

        current_loop_time = min(time_per_loop, time_left)
        await asyncio.sleep(current_loop_time)
        time_elapsed = time.perf_counter() - loop_start_time
        if AppState.task_state != TaskState.IDLE:
            new_text = AppState.status_snapshot or (
                f"🌐 <b><u>Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs</u></b> 🌐\n\n"
                f"**Status:** {AppState.task_state}\n\n"
                f"**📥 Files in Queue:** {queue.qsize()}"
            )
        else: new_text = get_idle_text()
        if new_text != text:
            try:
                await msg.edit_text(new_text)
                text = new_text
            except MessageNotModified: pass
            except FloodWait as e: await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
            except Exception as e:
                if "MESSAGE_ID_INVALID" in str(e).upper() or "DELETED" in str(e).upper(): break
                logger.debug(f"Status edit skipped: {e}")
    try: await message.delete()
    except Exception: pass
    try: await msg.delete()
    except Exception: pass