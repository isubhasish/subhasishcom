from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.__init__ import bot_app, user_app, config_data
from bot.helper_funcs.utils import AppState, queue

@user_app.on_message((filters.video | filters.document) & filters.user(config_data["AUTH_USERS"]))
async def incoming_file(client, message):
    tid = str(message.id)
    name = (message.video or message.document).file_name or "video.mp4"
    AppState.pending_tasks[tid] = {"msg": message, "name": name}
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 MediaInfo", callback_data=f"panel_info_{tid}"), InlineKeyboardButton("✂️ Stream Select", callback_data=f"panel_select_{tid}")],
        [InlineKeyboardButton("▶️ Compress All", callback_data=f"panel_all_{tid}")]
    ])
    
    if message.chat.type in ["group", "supergroup"]:
        await bot_app.send_message(message.chat.id, f"📥 **File Received:** `{name}`\nChoose an action:", reply_to_message_id=message.id, reply_markup=btn)
    else:
        await message.reply(f"📥 **File Received:** `{name}`\nChoose an action:", reply_markup=btn)

@bot_app.on_message(filters.reply & filters.user(config_data["AUTH_USERS"]))
async def index_receiver(client, message):
    tid = AppState.awaiting_index.pop(message.chat.id, None)
    if tid and tid in AppState.pending_tasks:
        task = AppState.pending_tasks.pop(tid)
        map_args = []
        for idx in message.text.split(','): map_args.extend(["-map", f"0:{idx.strip()}"])
        await queue.put((task['msg'], task['name'], map_args, message))
        await message.reply(f"✅ Success! `{task['name']}` queued with custom streams.")