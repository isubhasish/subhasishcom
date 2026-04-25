import os
import json
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from bot.__init__ import bot_app, user_app
from bot.helper_funcs.utils import AppState, queue
from bot.helper_funcs.download import get_graph_link
from bot.config import Config
from bot.localisation import Localisation

@bot_app.on_callback_query(filters.regex(r"^panel_(.*)"))
async def panel_handler(client, cb):
    action, tid = cb.data.split("_")[1:3]
    task = AppState.pending_tasks.get(tid)
    if not task: return await cb.answer("Task Expired", show_alert=True)

    if action == "info":
        await cb.message.edit("📝 Probing MediaInfo (No download)...")
        chunk_path = f"probe_{tid}.mkv"
        await user_app.download_media(task['msg'], file_name=chunk_path, limit=1) 
        info = os.popen(f"mediainfo {chunk_path}").read()
        os.remove(chunk_path)
        link = await get_graph_link(info)
        await cb.message.edit(f"📊 **MediaInfo Link:** {link}", disable_web_page_preview=True)

    elif action == "all":
        await queue.put((task['msg'], task['name'], ["-map", "0"], cb.message))
        await cb.message.edit(f"✅ Added to Queue (All Tracks).\n`{task['name']}`")

    elif action == "select":
        await cb.message.edit("⏳ Fetching Stream List...")
        chunk_path = f"probe_{tid}.mkv"
        await user_app.download_media(task['msg'], file_name=chunk_path, limit=1)
        streams = os.popen(f"ffprobe -v error -show_entries stream=index,codec_type,codec_name:stream_tags=language -of json {chunk_path}").read()
        os.remove(chunk_path)
        data = json.loads(streams).get("streams", [])
        txt = "**Available Streams:**\n"
        for s in data:
            txt += f"Index `{s['index']}`: {s['codec_type'].upper()} ({s.get('tags',{}).get('language','und')})\n"
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Input Indexes", callback_data=f"panel_input_{tid}")]])
        await cb.message.edit(txt, reply_markup=btn)

    elif action == "input":
        AppState.awaiting_index[cb.message.chat.id] = tid
        await cb.message.delete()
        await bot_app.send_message(cb.message.chat.id, "Reply with indexes (e.g. 0,2,4):", reply_markup=ForceReply(selective=True))

@bot_app.on_callback_query(filters.regex(r"^delthumb_(.*)"))
async def delthumb_cb(client, cb):
    action = cb.matches[0].group(1)
    if action == "yes":
        path = os.path.join(Config.THUMB_DIR, f"{cb.from_user.id}.jpg")
        if os.path.exists(path): os.remove(path)
        await cb.message.edit(Localisation.THUMB_DELETED)
    else:
        await cb.message.edit("❌ Thumbnail deletion cancelled.")

@bot_app.on_callback_query(filters.regex("cancel_running"))
async def cancel_running_cb(client, cb):
    if not AppState.current_process:
        return await cb.answer("No active task.", show_alert=True)
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Cancel Task", callback_data="confirm_cancel_yes"),
         InlineKeyboardButton("❌ No, Continue", callback_data="confirm_cancel_no")]
    ])
    await bot_app.send_message(cb.message.chat.id, Localisation.CANCEL_PROMPT, reply_markup=btn)

@bot_app.on_callback_query(filters.regex(r"^confirm_cancel_(.*)"))
async def confirm_cancel_cb(client, cb):
    action = cb.matches[0].group(1)
    if action == "yes":
        if AppState.current_process:
            AppState.current_process.terminate()
            AppState.current_process = None
            await cb.message.edit(Localisation.CANCELLED_MSG)
        else: await cb.message.edit(Localisation.NO_ACTIVE_TASK)
    else:
        await cb.message.edit("▶️ Cancellation aborted. Continuing task.")