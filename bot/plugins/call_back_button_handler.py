import os
import json
import re 
import uuid
import signal
import asyncio
from functools import wraps
from pyrogram import filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, ReplyParameters
from bot import bot_app, user_app, config_data, logger
from bot.config import Config
from bot.helper_funcs.utils import AppState, TaskState, queue, get_file_info, kill_running_process
from bot.helper_funcs.download import get_graph_link
from bot.localisation import Localisation

QUEUE_MSG = "<b>Added To Queue... 🚦</b>\n<b>Please Be Patient, Your Compression Will Start Soon... 😊</b>"
UNAUTH_MSG = "<b>You are not allowed to do that 🤭</b>"

def get_bsetting_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("API_ID", callback_data="bsetting_select_API_ID", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("API_HASH", callback_data="bsetting_select_API_HASH", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("TG_BOT_TOKEN", callback_data="bsetting_select_TG_BOT_TOKEN", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("OWNER_ID", callback_data="bsetting_select_OWNER_ID", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("LOG_CHANNEL", callback_data="bsetting_select_LOG_CHANNEL", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("AUTH_USERS", callback_data="bsetting_select_AUTH_USERS", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("USER_SESSION_STRING", callback_data="bsetting_select_USER_SESSION_STRING", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("CRF", callback_data="bsetting_select_CRF", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("PRESET", callback_data="bsetting_select_PRESET", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("RESOLUTION", callback_data="bsetting_select_RESOLUTION", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("AUDIO_BITRATE", callback_data="bsetting_select_AUDIO_BITRATE", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("CODEC", callback_data="bsetting_select_CODEC", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("WATERMARK", callback_data="bsetting_select_WATERMARK_TEXT", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("AS_DOCUMENT", callback_data="bsetting_toggle_AS_DOCUMENT", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("❌ Close", callback_data="bsetting_close", style=ButtonStyle.DANGER)]
    ])

def is_sudo(cb):
    user_id = cb.from_user.id
    auth_users = config_data.get("AUTH_USERS", [])
    owner_id = config_data.get("OWNER_ID", 0)
    
    if isinstance(auth_users, str):
        try: auth_users = json.loads(auth_users)
        except Exception: auth_users = []
        
    return user_id in auth_users or user_id == owner_id

def safe_callback(func):
    @wraps(func)
    async def wrapper(client, cb):
        from bot.plugins.commands import safe_edit
        answered = False
        original_answer = cb.answer

        async def tracked_answer(*args, **kwargs):
            nonlocal answered
            result = await original_answer(*args, **kwargs)
            answered = True  
            return result

        cb.answer = tracked_answer

        try: 
            return await func(client, cb)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Callback error in {func.__name__}: {e}")
            if not answered:
                try: await original_answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)
                except: pass
            await safe_edit(cb.message, f"⚠️ **Error Occurred:**\n`{e}`")
        finally:
            if not answered:
                try: await original_answer()
                except: pass
    return wrapper

@bot_app.on_callback_query(filters.regex(r"^panel_(close|info|back|all|select|input)_(.+)$"))
@safe_callback
async def panel_handler(client, cb):
    from bot.plugins.commands import safe_edit, safe_delete, spawn_temporary_task
    
    action = cb.matches[0].group(1)
    tid = cb.matches[0].group(2)
    
    async with AppState.state_lock:
        task = AppState.pending_tasks.get(tid)
    if not task: 
        await cb.answer("⚠️ Task Expired", show_alert=True)
        await safe_edit(cb.message, "⚠️ Task Expired")
        return

    if action == "close":
        if not is_sudo(cb): return await cb.answer(UNAUTH_MSG, show_alert=True)
        await cb.answer() 
        async with AppState.state_lock:
            AppState.pending_tasks.pop(tid, None)
        await safe_delete(cb.message, log_context="Panel close message")
        if 'msg' in task: await safe_delete(task['msg'], log_context="Panel task msg")
        return

    if action == "info":
        await cb.answer() 
        await safe_edit(cb.message, "📝 Probing MediaInfo...")
        chunk_path = f"/tmp/probe_{uuid.uuid4().hex}.mkv"
        
        try:
            active_client = user_app if user_app else bot_app
            with open(chunk_path, "wb") as f:
                dl_size = 0
                async for chunk in active_client.stream_media(task['msg']):
                    f.write(chunk)
                    dl_size += len(chunk)
                    if dl_size >= 25 * 1024 * 1024: break
                        
            size_str, _ = get_file_info(task['msg'])
            
            process = await asyncio.create_subprocess_exec(
                "mediainfo", chunk_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True
            )
            try: stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
            except asyncio.TimeoutError:
                raise Exception("MediaInfo Process Timed Out")
            finally:
                if process.returncode is None:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except Exception as e:
                        logger.debug(f"MediaInfo kill failed: {e}")
                    await process.wait()
                
            raw_info = stdout.decode('utf-8', errors='replace').strip()
            raw_info = re.sub(r"Complete name\s+:\s+.*", f"Complete name                            : {task.get('name', 'video.mp4')}", raw_info)
            raw_info = re.sub(r"File size\s+:\s+.*", f"File size                                : {size_str}", raw_info)
            
            content_json = [{"tag": "h3", "children": [task.get('name', 'video.mp4')]}]
            current_pre = ""
            for line in raw_info.split('\n'):
                clean_line = line.strip()
                if clean_line in ["General", "Video", "Text", "Menu"] or clean_line.startswith("Audio"):
                    if current_pre:
                        content_json.append({"tag": "pre", "children": [current_pre]})
                        current_pre = ""
                    icon = "📄" if clean_line == "General" else "🎬" if clean_line == "Video" else "💬" if clean_line == "Text" else "📑" if clean_line == "Menu" else "🔊"
                    content_json.append({"tag": "h3", "children": [f"{icon} {clean_line}"]})
                else:
                    if line.strip(): current_pre += line + "\n"
            
            if current_pre: content_json.append({"tag": "pre", "children": [current_pre]})
            
            link = await get_graph_link(content_json, title="Subhasish Encoder Mediainfo", author="Subhasish Encoder")
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"panel_back_{tid}")]])
            await safe_edit(cb.message, f"📊 **MediaInfo Link:**\n{link}", reply_markup=btn)
        except asyncio.CancelledError:
            raise
        except Exception as e: await safe_edit(cb.message, f"❌ **MediaInfo Error:** `{e}`")
        finally:
            if os.path.exists(chunk_path):
                try: os.remove(chunk_path)
                except Exception as e: logger.debug(f"Failed to remove probe chunk: {e}")

    elif action == "back":
        await cb.answer()
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ ᴄᴏᴍᴘʀᴇss ▶️", callback_data=f"panel_all_{tid}", style=ButtonStyle.SUCCESS), InlineKeyboardButton("🎞 sᴇʟᴇᴄᴛ sᴛʀᴇᴀᴍ 🎞", callback_data=f"panel_select_{tid}", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton("📊 ᴍᴇᴅɪᴀɪɴғᴏ 📊", callback_data=f"panel_info_{tid}", style=ButtonStyle.PRIMARY), InlineKeyboardButton("❌ ᴄʟᴏsᴇ ❌", callback_data=f"panel_close_{tid}", style=ButtonStyle.DANGER)]
        ])
        await safe_edit(cb.message, "👇 Choose an action:", reply_markup=btn)

    elif action == "all":
        if not is_sudo(cb): return await cb.answer(UNAUTH_MSG, show_alert=True)
        await cb.answer("Added to queue!", show_alert=False)
        await safe_delete(cb.message, log_context="Panel compress message")
        
        new_status_msg = await bot_app.send_message(
            cb.message.chat.id, 
            QUEUE_MSG, 
            reply_parameters=ReplyParameters(message_id=task['msg'].id)
        )
        await queue.put((task['msg'], task.get('name', 'video.mp4'), ["-map", "0"], new_status_msg))

        async with AppState.state_lock:
            AppState.pending_tasks.pop(tid, None)

    elif action == "select":
        await cb.answer() 
        await safe_edit(cb.message, "⏳ Fetching Stream List...")
        chunk_path = f"/tmp/probe_{uuid.uuid4().hex}.mkv"
        try:
            active_client = user_app if user_app else bot_app
            with open(chunk_path, "wb") as f:
                dl_size = 0
                async for chunk in active_client.stream_media(task['msg']):
                    f.write(chunk)
                    dl_size += len(chunk)
                    if dl_size >= 25 * 1024 * 1024: break
                        
            process = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "stream=index,codec_type,codec_name:stream_tags=language", "-of", "json", chunk_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True
            )
            try: stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
            except asyncio.TimeoutError:
                raise Exception("FFProbe Process Timed Out")
            finally:
                if process.returncode is None:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except Exception as e:
                        logger.debug(f"Stream select kill failed: {e}")
                    await process.wait()
                
            streams = stdout.decode('utf-8', errors='replace').strip()
            data = json.loads(streams).get("streams", [])
            txt = "**Available Streams:**\n"
            for s in data: txt += f"Index `{s['index']}`: {s['codec_type'].upper()} ({s.get('tags',{}).get('language','und')})\n"
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Input Indexes", callback_data=f"panel_input_{tid}", style=ButtonStyle.PRIMARY)]])
            await safe_edit(cb.message, txt, reply_markup=btn)
        except asyncio.CancelledError:
            raise
        except Exception as e: await safe_edit(cb.message, f"❌ **Stream Select Error:** `{e}`")
        finally:
            if os.path.exists(chunk_path):
                try: os.remove(chunk_path)
                except Exception as e: logger.debug(f"Failed to remove probe chunk: {e}")

    elif action == "input":
        if not is_sudo(cb): return await cb.answer(UNAUTH_MSG, show_alert=True)
        await cb.answer()
        
        prompt = await bot_app.send_message(
            cb.message.chat.id,
            "Reply with indexes (e.g. 0,2,4):",
            reply_parameters=ReplyParameters(message_id=cb.message.id),
            reply_markup=ForceReply(selective=True)
        )
        
        state_key = (cb.message.chat.id, cb.from_user.id)
        async with AppState.state_lock:
            AppState.awaiting_index[state_key] = {"tid": tid, "menu_msg_id": prompt.id, "stream_msg_id": cb.message.id}

        async def auto_clear_state():
            await asyncio.sleep(300) 
            async with AppState.state_lock:
                if AppState.awaiting_index.get(state_key, {}).get("tid") == tid:
                    AppState.awaiting_index.pop(state_key, None)
            from bot.plugins.commands import safe_delete
            await safe_delete(prompt, log_context="Timeout input prompt")
                    
        spawn_temporary_task(auto_clear_state(), max_timeout=360)

@bot_app.on_callback_query(filters.regex(r"^bsetting_(.*)"))
@safe_callback
async def bsetting_cb(client, cb):
    from bot.plugins.commands import safe_edit, safe_delete_by_id, safe_delete
    user_id = cb.from_user.id
    if user_id != config_data.get("OWNER_ID", 0): return await cb.answer(UNAUTH_MSG, show_alert=True)
    action = cb.matches[0].group(1)

    if action == "remove":
        await cb.answer()
        async with AppState.state_lock:
            if user_id not in AppState.bsetting_state: return
            key = AppState.bsetting_state[user_id]["key"]
            if key in config_data:
                del config_data[key]
                Config.save_config(config_data)
            del AppState.bsetting_state[user_id]
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"), InlineKeyboardButton("❌ Close", callback_data="bsetting_close", style=ButtonStyle.DANGER)]])
        await safe_edit(cb.message, f"✅ **{key}** has been successfully removed.\n\n✨ **𝘛𝘺𝘱𝘦 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘢𝘱𝘱𝘭𝘺.** ✨", reply_markup=btn)
        return

    if action.startswith("toggle_"):
        key = action.replace("toggle_", "")
        current_val = config_data.get(key, True if key == "AS_DOCUMENT" else False)
        config_data[key] = not current_val
        Config.save_config(config_data)
        await cb.answer(f"✅ {key} instantly changed to {not current_val}!", show_alert=True)
        await safe_edit(cb.message, f"**⚙️ Bot Settings Menu**\n✅ Successfully toggled `{key}` to `{not current_val}`\n✨ **𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵** ✨", reply_markup=get_bsetting_menu())
        return

    if action.startswith("select_"):
        await cb.answer()
        key = action.replace("select_", "")
        async with AppState.state_lock:
            AppState.bsetting_state[user_id] = {"key": key, "step": "awaiting_value"}
        hide_keys = ["API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID", "USER_SESSION_STRING"]
        lock_keys = ["API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID"]
        current_val = "******** (Hidden for Security)" if key in hide_keys else config_data.get(key, "Not Set")
        btn_list = [[InlineKeyboardButton("🔙 Back", callback_data="bsetting_back"), InlineKeyboardButton("❌ Close", callback_data="bsetting_close", style=ButtonStyle.DANGER)]]
        if key != "AS_DOCUMENT" and key not in lock_keys and key in config_data: btn_list.insert(0, [InlineKeyboardButton("🗑 Remove Value", callback_data="bsetting_remove", style=ButtonStyle.DANGER)])
        btn = InlineKeyboardMarkup(btn_list)
        if key == "WATERMARK_TEXT": await safe_edit(cb.message, f"📝 **Editing {key}**\n\n**Current Value:** `{current_val}`\n\n👇 **Send your Watermark text.**", reply_markup=btn)
        else: await safe_edit(cb.message, f"📝 **Editing {key}**\n\n**Current Value:** `{current_val}`\n\n👇 **Send the new value as a normal message now.**", reply_markup=btn)

    elif action == "confirm_yes":
        async with AppState.state_lock:
            if user_id not in AppState.bsetting_state or "pending_value" not in AppState.bsetting_state[user_id]: return await cb.answer("Session expired.", show_alert=True)
            await cb.answer()
            key = AppState.bsetting_state[user_id]["key"]
            raw_val = AppState.bsetting_state[user_id]["pending_value"]
            msg_to_delete = AppState.bsetting_state[user_id].get("msg_to_delete")
            del AppState.bsetting_state[user_id]
        hide_keys = ["API_ID", "API_HASH", "TG_BOT_TOKEN", "OWNER_ID", "USER_SESSION_STRING"]
        try:
            v = raw_val
            if key == "AUTH_USERS": v = json.loads(v) 
            elif key in ["API_ID", "OWNER_ID", "LOG_CHANNEL"]: v = int(v)
            elif key in ["USER_SESSION_STRING", "API_HASH", "TG_BOT_TOKEN", "CRF", "PRESET", "RESOLUTION", "AUDIO_BITRATE", "CODEC", "WATERMARK_TEXT"]: v = str(v)
            config_data[key] = v
            Config.save_config(config_data)
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="bsetting_back"), InlineKeyboardButton("❌ Close", callback_data="bsetting_close", style=ButtonStyle.DANGER)]])
            if key in hide_keys: await safe_edit(cb.message, f"✅ **{key}** successfully securely stored.\n\n✨ **𝘛𝘺𝘱𝘦 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘢𝘱𝘱𝘭𝘺 𝘤𝘰𝘳𝘦 𝘤𝘩𝘢𝘯𝘨𝘦𝘴.** ✨", reply_markup=btn)
            else: await safe_edit(cb.message, f"✅ **{key}** successfully updated to `{v}`.\n\n✨ **𝘛𝘺𝘱𝘦 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘢𝘱𝘱𝘭𝘺.** ✨", reply_markup=btn)
            if msg_to_delete:
                await safe_delete_by_id(client, cb.message.chat.id, msg_to_delete, log_context="Bsetting old msg")
        except asyncio.CancelledError:
            raise
        except Exception as e: await safe_edit(cb.message, f"❌ **Error formatting variable:**\n{e}")

    elif action == "confirm_no":
        await cb.answer()
        async with AppState.state_lock:
            if user_id in AppState.bsetting_state: 
                msg_to_delete = AppState.bsetting_state[user_id].get("msg_to_delete")
                del AppState.bsetting_state[user_id]
            else:
                msg_to_delete = None

        if msg_to_delete:
            await safe_delete_by_id(client, cb.message.chat.id, msg_to_delete, log_context="Bsetting old msg")
        await safe_edit(cb.message, "❌ Update cancelled.")
        await asyncio.sleep(2)
        await safe_edit(cb.message, "**⚙️ Bot Settings Menu**", reply_markup=get_bsetting_menu())

    elif action in ["back", "close"]:
        await cb.answer()
        async with AppState.state_lock:
            if user_id in AppState.bsetting_state: 
                msg_to_delete = AppState.bsetting_state[user_id].get("msg_to_delete")
                del AppState.bsetting_state[user_id]
            else:
                msg_to_delete = None

        if msg_to_delete:
            await safe_delete_by_id(client, cb.message.chat.id, msg_to_delete, log_context="Bsetting old msg")
        if action == "close":
            from bot.plugins.commands import safe_delete
            await safe_delete(cb.message, log_context="Bsetting close msg")
            if cb.message.reply_to_message: await safe_delete(cb.message.reply_to_message, log_context="Bsetting close reply msg")
            return
       
        help_text = (
            "**⚙️ Bot Settings Menu**\n"
            "Click a variable below to change its value interactively.\n"
            "✨ 𝘊𝘰𝘳𝘦 𝘴𝘺𝘴𝘵𝘦𝘮 𝘤𝘩𝘢𝘯𝘨𝘦𝘴 𝘳𝘦𝘲𝘶𝘪𝘳𝘦 𝘢 /𝘳𝘦𝘴𝘵𝘢𝘳𝘵 𝘵𝘰 𝘵𝘢𝘬𝘦 𝘧𝘶𝘭𝘭 𝘦𝘧𝘧𝘦𝘤𝘵 ✨"
        )
        await safe_edit(cb.message, help_text, reply_markup=get_bsetting_menu())

@bot_app.on_callback_query(filters.regex("cancel_running"))
@safe_callback
async def cancel_running_cb(client, cb):
    from bot.plugins.commands import safe_delete, spawn_temporary_task
    if not is_sudo(cb): return await cb.answer(UNAUTH_MSG, show_alert=True)
    if AppState.task_state == TaskState.IDLE: return await cb.answer("No active task.", show_alert=True)
    await cb.answer()
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Yes ✅", callback_data="confirm_cancel_yes", style=ButtonStyle.SUCCESS), InlineKeyboardButton("No ❌", callback_data="confirm_cancel_no", style=ButtonStyle.DANGER)]])
    
    reply_params = ReplyParameters(message_id=AppState.active_origin_msg.id) if AppState.active_origin_msg else None
    
    prompt = await bot_app.send_message(
        cb.message.chat.id, 
        Localisation.CANCEL_PROMPT, 
        reply_parameters=reply_params, 
        reply_markup=btn
    )
    
    async def auto_delete_prompt():
        await asyncio.sleep(10)
        await safe_delete(prompt, log_context="Cancel prompt auto-delete")
    spawn_temporary_task(auto_delete_prompt(), max_timeout=20)

@bot_app.on_callback_query(filters.regex(r"^confirm_cancel_(.*)"))
@safe_callback
async def confirm_cancel_cb(client, cb):
    from bot.plugins.commands import safe_edit, safe_delete
    if not is_sudo(cb): return await cb.answer(UNAUTH_MSG, show_alert=True)
    action = cb.matches[0].group(1)
    if action == "yes":
        if AppState.task_state == TaskState.CANCELLING: return await cb.answer("⚠️ Cancellation already in progress...", show_alert=True)
        await cb.answer()
        if AppState.task_state != TaskState.IDLE:
            AppState.task_state = TaskState.CANCELLING
            AppState.cancel_task = True
            await kill_running_process()
            await safe_delete(cb.message, log_context="Confirm cancel YES msg")
        else: await safe_edit(cb.message, Localisation.NO_ACTIVE_TASK)
    else:
        await cb.answer()
        await safe_delete(cb.message, log_context="Confirm cancel NO msg")

@bot_app.on_callback_query(filters.regex(r"^delthumb_(.*)"))
@safe_callback
async def delthumb_cb(client, cb):
    from bot.plugins.commands import safe_edit, safe_delete
    user_id = cb.from_user.id
    if user_id != config_data.get("OWNER_ID", 0): return await cb.answer(UNAUTH_MSG, show_alert=True)
    action = cb.matches[0].group(1)
    await cb.answer()
    if action == "yes":
        path = os.path.join(Config.THUMB_DIR, f"{user_id}.jpg")
        if os.path.exists(path): 
            try: os.remove(path)
            except Exception as e: logger.debug(f"Failed to remove thumb: {e}")
        await safe_edit(cb.message, Localisation.THUMB_REMOVED)
    else:
        await safe_edit(cb.message, "❌ Thumbnail deletion cancelled.")
        await asyncio.sleep(2)
        await safe_delete(cb.message, log_context="Thumb cancel menu")