import os
import json
import re # FIX: Imported Regex to cleanly overwrite the dummy chunk data
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from bot.__init__ import bot_app, user_app, config_data
from bot.config import Config
from bot.helper_funcs.utils import AppState, queue, get_file_info
from bot.helper_funcs.download import get_graph_link
from bot.localisation import Localisation

QUEUE_MSG = "<b>Added To Queue... 🚦</b>\n<b>Please Be Patient, Your Compression Will Start Soon... 😊</b>"

def get_bsetting_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("API_ID", callback_data="bsetting_select_API_ID"),
         InlineKeyboardButton("API_HASH", callback_data="bsetting_select_API_HASH")],
        [InlineKeyboardButton("TG_BOT_TOKEN", callback_data="bsetting_select_TG_BOT_TOKEN"),
         InlineKeyboardButton("OWNER_ID", callback_data="bsetting_select_OWNER_ID")],
        [InlineKeyboardButton("LOG_CHANNEL", callback_data="bsetting_select_LOG_CHANNEL"),
         InlineKeyboardButton("AUTH_USERS", callback_data="bsetting_select_AUTH_USERS")],
        [InlineKeyboardButton("USER_SESSION_STRING", callback_data="bsetting_select_USER_SESSION_STRING")],
        [InlineKeyboardButton("CRF", callback_data="bsetting_select_CRF"),
         InlineKeyboardButton("PRESET", callback_data="bsetting_select_PRESET")],
        [InlineKeyboardButton("RESOLUTION", callback_data="bsetting_select_RESOLUTION"),
         InlineKeyboardButton("AUDIO_BITRATE", callback_data="bsetting_select_AUDIO_BITRATE")],
        [InlineKeyboardButton("CODEC", callback_data="bsetting_select_CODEC"),
         InlineKeyboardButton("WATERMARK", callback_data="bsetting_select_WATERMARK_TEXT")],
        [InlineKeyboardButton("AS_DOCUMENT", callback_data="bsetting_toggle_AS_DOCUMENT")],
        [InlineKeyboardButton("❌ Close", callback_data="bsetting_close")]
    ])

@bot_app.on_callback_query(filters.regex(r"^panel_(.*)"))
async def panel_handler(client, cb):
    action, tid = cb.data.split("_")[1:3]
    task = AppState.pending_tasks.get(tid)
    if not task: return await cb.answer("Task Expired", show_alert=True)

    if action == "close":
        AppState.pending_tasks.pop(tid, None)
        try:
            await cb.message.delete()
            if 'msg' in task: await task['msg'].delete()
        except: pass
        return

    if action == "info":
        await cb.message.edit("📝 Probing MediaInfo...")
        chunk_path = f"probe_{tid}.mkv"
        
        try:
            with open(chunk_path, "wb") as f:
                dl_size = 0
                async for chunk in user_app.stream_media(task['msg']):
                    f.write(chunk)
                    dl_size += len(chunk)
                    if dl_size >= 5 * 1024 * 1024:
                        break
                        
            size_str, _ = get_file_info(task['msg'])
            raw_info = os.popen(f"mediainfo {chunk_path}").read()
            
            # FIX: Regex violently overwrites the fake local chunk data with the true Telegram data
            raw_info = re.sub(r"Complete name\s+:\s+.*", f"Complete name                            : {task['name']}", raw_info)
            raw_info = re.sub(r"File size\s+:\s+.*", f"File size                                : {size_str}", raw_info)
            
            content_json = []
            content_json.append({"tag": "h3", "children": [task['name']]})
            content_json.append({"tag": "hr"})

            current_pre = ""
            for line in raw_info.split('\n'):
                clean_line = line.strip()
                if clean_line in ["General", "Video", "Audio", "Text", "Menu"]:
                    if current_pre:
                        content_json.append({"tag": "pre", "children": [current_pre]})
                        current_pre = ""
                    icons = {"General": "📄", "Video": "🎬", "Audio": "🔊", "Text": "💬", "Menu": "📑"}
                    content_json.append({"tag": "h3", "children": [f"{icons.get(clean_line, '')} {clean_line}"]})
                else:
                    if line.strip(): 
                        current_pre += line + "\n"
            
            if current_pre:
                content_json.append({"tag": "pre", "children": [current_pre]})
            
            # FIX: Restored Author text exactly as requested!
            link = await get_graph_link(content_json, title="Subhasish Encoder Mediainfo", author="Subhasish Encoder")
            await cb.message.edit(f"📊 **MediaInfo Link:**\n{link}")
        except Exception as e:
            await cb.message.edit(f"❌ **MediaInfo Error:** `{e}`")
        finally:
            if os.path.exists(chunk_path): os.remove(chunk_path)

    elif action == "all":
        try: await cb.message.delete()
        except: pass
        new_status_msg = await bot_app.send_message(cb.message.chat.id, QUEUE_MSG, reply_to_message_id=task['msg'].id)
        await queue.put((task['msg'], task['name'], ["-map", "0"], new_status_msg))

    elif action == "select":
        await cb.message.edit("⏳ Fetching Stream List...")
        chunk_path = f"probe_{tid}.mkv"
        
        try:
            with open(chunk_path, "wb") as f:
                dl_size = 0
                async for chunk in user_app.stream_media(task['msg']):
                    f.write(chunk)
                    dl_size += len(chunk)
                    if dl_size >= 5 * 1024 * 1024:
                        break
                        
            streams = os.popen(f"ffprobe -v error -show_entries stream=index,codec_type,codec_name:stream_tags=language -of json {chunk_path}").read()
            data = json.loads(streams).get("streams", [])
            txt = "**Available Streams:**\n"
            for s in data:
                txt += f"Index `{s['index']}`: {s['codec_type'].upper()} ({s.get('tags',{}).get('language','und')})\n"
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Input Indexes", callback_data=f"panel_input_{tid}")]])
            await cb.message.edit(txt, reply_markup=btn)
        except Exception as e:
            await cb.message.edit(f"❌ **Stream Select Error:** `{e}`")
        finally:
            if os.path.exists(chunk_path): os.remove(chunk_path)

    elif action == "input":
        AppState.awaiting_index[cb.message.chat.id] = {"tid": tid, "menu_msg_id": cb.message.id}
        await bot_app.send_message(cb.message.chat.id, "Reply with indexes (e.g. 0,2,4):", reply_markup=ForceReply(selective=True))

@bot_app.on_callback_query(filters.regex(r"^bsetting_(.*)"))
async def bsetting_cb(client, cb):
    user_id = cb.from_user.id
    if user_id != config_data["OWNER_ID"]:
        return await cb.answer("⚠️ Only the Owner can use these buttons!", show_alert=True)
        
    action = cb.matches[0].group(1)

    if action.startswith("toggle_"):
        key = action.replace("toggle_", "")
        default_val = True if key == "AS_DOCUMENT" else False
        current_val = config_data.get(key, default_val)
        
        config_data[key] = not current_val
        Config.save_config(config_data)
        
        await cb.answer(f"✅ {key} instantly changed to {not current_val}!", show_alert=True)
        await cb.message.edit(
            f"**⚙️ Bot Settings Menu**\n✅ Successfully toggled `{key}` to `{not current_val}`\n✨ 𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵 ✨",
            reply_markup=get_bsetting_menu()
        )
        return

    if action.startswith("select_"):
        key = action.replace("select_", "")
        AppState.bsetting_state[user_id] = {"key": key, "step": "awaiting_value"}
        
        sensitive_keys = ["USER_SESSION_STRING", "API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID"]
        
        if key in sensitive_keys: current_val = "******** (Hidden for Security)"
        else: current_val = config_data.get(key, "Not Set")

        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bsetting_back"), InlineKeyboardButton("❌ Close", callback_data="bsetting_close")]])
        
        if key == "WATERMARK_TEXT":
            await cb.message.edit(f"📝 **Editing {key}**\n\n**Current Value:** `{current_val}`\n\n👇 **Send your Watermark text.**\n✨ 𝘛𝘺𝘱𝘦 𝘕𝘰𝘯𝘦 𝘵𝘰 𝘳𝘦𝘮𝘰𝘷𝘦 𝘵𝘩𝘦 𝘸𝘢𝘵𝘦𝘳𝘮𝘢𝘳𝘬 ✨", reply_markup=btn)
        else:
            await cb.message.edit(f"📝 **Editing {key}**\n\n**Current Value:** `{current_val}`\n\n👇 **Send the new value as a normal message now.**", reply_markup=btn)

    elif action == "confirm_yes":
        if user_id not in AppState.bsetting_state or "pending_value" not in AppState.bsetting_state[user_id]:
            return await cb.answer("Session expired.", show_alert=True)

        key = AppState.bsetting_state[user_id]["key"]
        raw_val = AppState.bsetting_state[user_id]["pending_value"]
        sensitive_keys = ["USER_SESSION_STRING", "API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID"]

        try:
            v = raw_val
            if key == "AUTH_USERS": v = json.loads(v) 
            elif key in ["API_ID", "OWNER_ID", "LOG_CHANNEL"]: v = int(v)
            elif key in ["USER_SESSION_STRING", "API_HASH", "TG_BOT_TOKEN", "CRF", "PRESET", "RESOLUTION", "AUDIO_BITRATE", "CODEC", "WATERMARK_TEXT"]: v = str(v)
            
            config_data[key] = v
            Config.save_config(config_data)
            
            if key in sensitive_keys: await cb.message.edit(f"✅ **{key}** successfully securely stored.\n\n⚠️ **Type /restart to apply core changes.**")
            else: await cb.message.edit(f"✅ **{key}** successfully updated to `{v}`.\n\n⚠️ **Type /restart to apply.**")
        except Exception as e: 
            await cb.message.edit(f"❌ **Error formatting variable:**\n{e}")

        del AppState.bsetting_state[user_id]

    elif action == "confirm_no":
        if user_id in AppState.bsetting_state: del AppState.bsetting_state[user_id]
        await cb.message.edit("❌ Update cancelled.")

    elif action == "back" or action == "close":
        if user_id in AppState.bsetting_state: del AppState.bsetting_state[user_id]
        
        if action == "close":
            try:
                await cb.message.delete()
                if cb.message.reply_to_message:
                    await cb.message.reply_to_message.delete()
            except: pass
            return
        
        help_text = (
            "**⚙️ Bot Settings Menu**\n"
            "Click a variable below to change its value interactively.\n"
            "✨ 𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵 ✨"
        )
        await cb.message.edit(help_text, reply_markup=get_bsetting_menu())

@bot_app.on_callback_query(filters.regex(r"^delthumb_(.*)"))
async def delthumb_cb(client, cb):
    user_id = cb.from_user.id
    if user_id != config_data["OWNER_ID"]:
        return await cb.answer("⚠️ Only the Owner can delete thumbnails!", show_alert=True)

    action = cb.matches[0].group(1)
    if action == "yes":
        path = os.path.join(Config.THUMB_DIR, f"{cb.from_user.id}.jpg")
        if os.path.exists(path): os.remove(path)
        await cb.message.edit(Localisation.THUMB_REMOVED)
    else:
        await cb.message.edit("❌ Thumbnail deletion cancelled.")

@bot_app.on_callback_query(filters.regex("cancel_running"))
async def cancel_running_cb(client, cb):
    if not AppState.current_process:
        return await cb.answer("No active task.", show_alert=True)
        
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes✅", callback_data="confirm_cancel_yes"), InlineKeyboardButton("No ❌", callback_data="confirm_cancel_no")]
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