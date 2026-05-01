from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot_app, user_app, config_data
from bot.helper_funcs.utils import queue, AppState, get_file_info
import os

@bot_app.on_message((filters.video | filters.document) & ~filters.forwarded)
async def incoming_media(client, message):
    if message.caption and message.caption.startswith(("/", "!", ".")):
        return

    # FIX: Removed chat_id check. Authorization is strictly User ID based now.
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in config_data["AUTH_USERS"] and user_id != config_data["OWNER_ID"]:
        return await message.reply("<b>Opps You Need To Donate Some Amount To Use Meh...🐸👀</b>")

    media = message.video or message.document
    if not media:
        return
        
    if media.file_size < 1024 * 1024:
        return await message.reply("⚠️ File is too small.", quote=True)
        
    if message.document:
        mime = getattr(message.document, "mime_type", "") or ""
        if mime.startswith("audio/"):
            return await message.reply("⚠️ **Invalid File:** Audio files are not supported.", quote=True)
            
        if not mime.startswith("video/"):
            file_name = getattr(message.document, "file_name", "") or ""
            ext = file_name.split(".")[-1].lower() if "." in file_name else ""
            valid_extensions = ["mp4", "mkv", "avi", "webm", "flv", "mov", "wmv", "m4v", "ts"]
            if ext not in valid_extensions:
                return await message.reply("⚠️ **Invalid File:** Please send a valid video file.", quote=True)

    file_name = getattr(media, "file_name", "video.mkv")
    tid = str(message.id) + str(message.chat.id)
    
    size_str, dc_str = get_file_info(message)
    
    AppState.pending_tasks[tid] = {
        "msg": message,
        "name": file_name
    }

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ ᴄᴏᴍᴘʀᴇss ▶️", callback_data=f"panel_all_{tid}"), 
         InlineKeyboardButton("🎞 sᴇʟᴇᴄᴛ sᴛʀᴇᴀᴍ 🎞", callback_data=f"panel_select_{tid}")],
        [InlineKeyboardButton("📊 ᴍᴇᴅɪᴀɪɴғᴏ 📊", callback_data=f"panel_info_{tid}"), 
         InlineKeyboardButton("❌ ᴄʟᴏsᴇ ❌", callback_data=f"panel_close_{tid}")]
    ])
    
    await message.reply(
        f"📥 **File Received:** `{file_name}`\n"
        f"**Size:** {size_str}\n"
        f"**Data Center:** {dc_str}\n\n"
        f"👇 Choose an action:",
        reply_markup=btn,
        quote=True
    )

@bot_app.on_message(filters.reply & filters.text, group=2)
async def index_receiver(client, message):
    if not message.reply_to_message: return
    
    chat_id = message.chat.id
    if chat_id in AppState.awaiting_index and AppState.awaiting_index[chat_id]["menu_msg_id"] == message.reply_to_message.id:
        tid = AppState.awaiting_index[chat_id]["tid"]
        task = AppState.pending_tasks.get(tid)
        
        if not task:
            del AppState.awaiting_index[chat_id]
            return await message.reply("⚠️ Task expired.")

        try:
            indexes = [int(i.strip()) for i in message.text.split(",")]
            map_args = []
            for i in indexes:
                map_args.extend(["-map", f"0:{i}"])
                
            await message.reply_to_message.delete()
            try: await message.delete() 
            except: pass
            
            del AppState.awaiting_index[chat_id]
            
            new_status_msg = await bot_app.send_message(chat_id, "<b>Added To Queue... 🚦</b>\n<b>Please Be Patient, Your Compression Will Start Soon... 😊</b>", reply_to_message_id=task['msg'].id)
            await queue.put((task['msg'], task['name'], map_args, new_status_msg))
            
        except ValueError:
            await message.reply("⚠️ Invalid input. Please enter numbers separated by commas (e.g. 0,2,4).")