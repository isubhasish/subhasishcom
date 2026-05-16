import os
import json
from pyrogram import filters
from pyrogram.enums import ChatType, ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from bot import bot_app, config_data
from bot.helper_funcs.utils import queue, AppState, get_file_info
from bot.localisation import Localisation

UNAUTH_MSG = "<b>You are not allowed to do that 🤭</b>"
QUEUE_MSG = "<b>Added To Queue... 🚦</b>\n<b>Please Be Patient, Your Compression Will Start Soon... 😊</b>"

def is_sudo(message):
    user_id = message.from_user.id if message.from_user else 0
    auth_users = config_data.get("AUTH_USERS", [])
    owner_id = config_data.get("OWNER_ID", 0)
    
    if isinstance(auth_users, str):
        try: auth_users = json.loads(auth_users)
        except Exception: auth_users = []
        
    return user_id in auth_users or user_id == owner_id

@bot_app.on_message(filters.video | filters.document)
async def incoming_media(client, message):
    if message.caption and message.caption.startswith(("/", "!", ".")): return

    if not is_sudo(message):
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]: 
            return await bot_app.send_message(
                message.chat.id, 
                UNAUTH_MSG, 
                reply_parameters=ReplyParameters(message_id=message.id)
            )
        else: 
            return await bot_app.send_message(
                message.chat.id, 
                UNAUTH_MSG, 
                reply_parameters=ReplyParameters(message_id=message.id)
            )

    media = message.video or message.document
    if not media: return
        
    if media.file_size < 1024 * 1024:
        return await bot_app.send_message(
            message.chat.id, 
            "⚠️ File is too small.", 
            reply_parameters=ReplyParameters(message_id=message.id)
        )
        
    if message.document:
        mime = getattr(message.document, "mime_type", "") or ""
        if mime.startswith("audio/"): 
            return await bot_app.send_message(
                message.chat.id, 
                "⚠️ **Invalid File:** Audio files are not supported.", 
                reply_parameters=ReplyParameters(message_id=message.id)
            )
            
        if not mime.startswith("video/"):
            file_name = getattr(message.document, "file_name", "") or ""
            ext = file_name.split(".")[-1].lower() if "." in file_name else ""
            valid_extensions = ["mp4", "mkv", "avi", "webm", "flv", "mov", "wmv", "m4v", "ts"]
            if ext not in valid_extensions:
                return await bot_app.send_message(
                    message.chat.id, 
                    "⚠️ **Invalid File:** Please send a valid video file.", 
                    reply_parameters=ReplyParameters(message_id=message.id)
                )

    file_name = getattr(media, "file_name", "video.mkv")
    tid = str(message.id) + str(message.chat.id)
    
    size_str, dc_str = get_file_info(message)
    
    async with AppState.state_lock:
        AppState.pending_tasks[tid] = {"msg": message, "name": file_name}

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ ᴄᴏᴍᴘʀᴇss ▶️", callback_data=f"panel_all_{tid}", style=ButtonStyle.SUCCESS), InlineKeyboardButton("🎞 sᴇʟᴇᴄᴛ sᴛʀᴇᴀᴍ 🎞", callback_data=f"panel_select_{tid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("📊 ᴍᴇᴅɪᴀɪɴғᴏ 📊", callback_data=f"panel_info_{tid}", style=ButtonStyle.PRIMARY), InlineKeyboardButton("❌ ᴄʟᴏsᴇ ❌", callback_data=f"panel_close_{tid}", style=ButtonStyle.DANGER)]
    ])
    
    await bot_app.send_message(
        message.chat.id,
        f"**🤔 What you want to do with this file? 🧐**\n\n"
        f"**Name:** `{file_name}`\n"
        f"**Size:** **{size_str}**\n"
        f"**Data Center:** **{dc_str}**\n\n"
        f"**🌞 Choose an Action: 👇**",
        reply_markup=btn, 
        reply_parameters=ReplyParameters(message_id=message.id)
    )

@bot_app.on_message(filters.reply & filters.text, group=2)
async def index_receiver(client, message):
    if not is_sudo(message): return
    if not message.reply_to_message: return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    state_key = (chat_id, user_id)

    async with AppState.state_lock:
        state_data = AppState.awaiting_index.get(state_key)

    if state_data and state_data.get("menu_msg_id") == message.reply_to_message.id:
        tid = state_data["tid"]
        stream_msg_id = state_data.get("stream_msg_id")

        async with AppState.state_lock:
            task = AppState.pending_tasks.get(tid)
        
        if not task:
            async with AppState.state_lock:
                AppState.awaiting_index.pop(state_key, None)
            return await bot_app.send_message(
                chat_id, 
                "⚠️ Task expired.", 
                reply_parameters=ReplyParameters(message_id=message.id)
            )
            
        try:
            indexes = [int(i.strip()) for i in message.text.split(",")]
            map_args = []
            for i in indexes:
                map_args.extend(["-map", f"0:{i}"])
            
            try: await message.reply_to_message.delete()
            except: pass
            try: await message.delete()
            except: pass
            
            if stream_msg_id:
                try: await bot_app.delete_messages(chat_id, stream_msg_id)
                except: pass
                
            async with AppState.state_lock:
                AppState.awaiting_index.pop(state_key, None)
            
            new_status_msg = await bot_app.send_message(
                chat_id, 
                QUEUE_MSG, 
                reply_parameters=ReplyParameters(message_id=task['msg'].id)
            )
            await queue.put((task['msg'], task['name'], map_args, new_status_msg))
            
        except ValueError:
            await bot_app.send_message(
                chat_id, 
                "⚠️ Invalid input. Please enter numbers separated by commas (e.g. 0,2,4).", 
                reply_parameters=ReplyParameters(message_id=message.id)
            )