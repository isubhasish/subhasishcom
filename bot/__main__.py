import time
import logging
import shutil
import sys
import os
import pyrogram
from datetime import datetime as dt

from bot import (APP_ID, API_HASH, AUTH_USERS, DOWNLOAD_LOCATION, LOGGER, TG_BOT_TOKEN, BOT_USERNAME, SESSION_NAME,  
                 data, app, crf, resolution, audio_b, preset, codec, watermark)

from bot.helper_funcs.utils import add_task, on_task_complete
from pyrogram import Client, filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from bot.plugins.incoming_message_fn import (
    incoming_start_message_f,
    incoming_compress_message_f,
    incoming_cancel_message_f
)


from bot.plugins.status_message_fn import (
    eval_message_f,
    exec_message_f,
    upload_log_file
)

from bot.commands import Command
from bot.plugins.call_back_button_handler import button
sudo_users = "1051485224" 
crf.append("38")
codec.append("libx265")
resolution.append("820x480")
preset.append("fast")
audio_b.append("96k")
# 🦋

# Configure logging
console_handler = logging.StreamHandler()
console_format = logging.Formatter(
        "%(asctime)s - %(levelname)s- %(filename)s:%(lineno)d - %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(console_format)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Set pyrogram logging to WARNING to avoid clutter
logging.getLogger("pyrogram").setLevel(logging.ERROR)
 
# Check for ffmpeg installation
if not shutil.which("ffmpeg"):
    logger.info("𝙁𝙁𝙈𝙋𝙀𝙂 𝙡𝙞𝙗𝙧𝙖𝙧𝙮 𝙞𝙨𝙣'𝙩 𝙞𝙣𝙨𝙩𝙖𝙡𝙡𝙚𝙙, 𝙨𝙤 𝙁𝙁𝙈𝙋𝙀𝙂-𝙧𝙚𝙡𝙖𝙩𝙚𝙙 𝙩𝙝𝙞𝙣𝙜𝙨 𝙬𝙤𝙣'𝙩 𝙬𝙤𝙧𝙠 🫠")
else:
    logger.info("𝙂𝙤𝙤𝙙 𝙗𝙤𝙮 😉 𝙁𝙁𝙈𝙋𝙀𝙂 𝙞𝙣𝙨𝙩𝙖𝙡𝙡𝙚𝙙")
 
# Check Python version 
python_version = sys.version



uptime = dt.now()

def ts(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "")
        + ((str(hours) + "h, ") if hours else "")
        + ((str(minutes) + "m, ") if minutes else "")
        + ((str(seconds) + "s, ") if seconds else "")
        + ((str(milliseconds) + "ms, ") if milliseconds else "")
    )
    return tmp[:-2]


if __name__ == "__main__" :
    # create download directory, if not exist
    if not os.path.isdir(DOWNLOAD_LOCATION):
        os.makedirs(DOWNLOAD_LOCATION)
    #
    logger.info(f"𝖯𝖸𝖳𝖧𝖮𝖭 𝖵𝖤𝖱𝖲𝖨𝖮𝖭: {python_version}")
    logger.info(f"ᴘʏʀᴏɢʀᴀᴍ ᴠᴇʀꜱɪᴏɴ - v{pyrogram.__version__} | ʟᴀʏᴇʀ:{layer}\n🤖 𝘽𝙤𝙩 𝙨𝙩𝙖𝙧𝙩𝙚𝙙 𝙨𝙪𝙘𝙘𝙚𝙨𝙨𝙛𝙪𝙡𝙡𝙮 🎉")
    app.set_parse_mode(enums.ParseMode.HTML)

    incoming_start_message_handler = MessageHandler(
        incoming_start_message_f,
        filters=filters.command(["start", f"start@{BOT_USERNAME}"])
    )
    app.add_handler(incoming_start_message_handler)
    
    
    @app.on_message(filters.incoming & filters.command(["crf", f"crf@{BOT_USERNAME}"]))
    async def changecrf(app, message):
        if message.from_user.id in AUTH_USERS:
            cr = message.text.split(" ", maxsplit=1)[1]
            OUT = f"I will be using : {cr} crf"
            crf.insert(0, f"{cr}")
            await message.reply_text(OUT)
        else:
            await message.reply_text("Error")
            
    @app.on_message(filters.incoming & filters.command(["settings", f"settings@{BOT_USERNAME}"]))
    async def settings(app, message):
        if message.from_user.id in AUTH_USERS:
            await message.reply_text(f"<b>The current settings will be added to your video file :</b>\n\n<b>Codec</b> : {codec[0]} \n<b>Crf</b> : {crf[0]} \n<b>Resolution</b> : {resolution[0]} \n<b>Preset</b> : {preset[0]} \n<b>Audio Bitrates</b> : {audio_b[0]}")
            
            
               
    @app.on_message(filters.incoming & filters.command(["resolution", f"resolution@{BOT_USERNAME}"]))
    async def changer(app, message):
        if message.from_user.id in AUTH_USERS:
            r = message.text.split(" ", maxsplit=1)[1]
            OUT = f"I will be using : {r} resolution"
            resolution.insert(0, f"{r}")
            await message.reply_text(OUT)
        else:
            await message.reply_text("Error")

            
               
    @app.on_message(filters.incoming & filters.command(["preset", f"preset@{BOT_USERNAME}"]))
    async def changepr(app, message):
        if message.from_user.id in AUTH_USERS:
            pop = message.text.split(" ", maxsplit=1)[1]
            OUT = f"I will be using : {pop} preset"
            preset.insert(0, f"{pop}")
            await message.reply_text(OUT)
        else:
            await message.reply_text("Error")

            
    @app.on_message(filters.incoming & filters.command(["codec", f"codec@{BOT_USERNAME}"]))
    async def changecode(app, message):
        if message.from_user.id in AUTH_USERS:
            col = message.text.split(" ", maxsplit=1)[1]
            OUT = f"I will be using : {col} codec"
            codec.insert(0, f"{col}")
            await message.reply_text(OUT)
        else:
            await message.reply_text("Error")
             
    @app.on_message(filters.incoming & filters.command(["audio", f"audio@{BOT_USERNAME}"]))
    async def changea(app, message):
        if message.from_user.id in AUTH_USERS:
            aud = message.text.split(" ", maxsplit=1)[1]
            OUT = f"I will be using : {aud} audio"
            audio_b.insert(0, f"{aud}")
            await message.reply_text(OUT)
        else:
            await message.reply_text("Error")
            
        
    @app.on_message(filters.incoming & filters.command(["compress", f"compress@{BOT_USERNAME}"]))
    async def help_message(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<b>Opps You Need To Donate Some Amount To Use Meh...🐸👀</b>")
        query = await message.reply_text("<b>Added To Queue... 🚦</b>\n<b>Please Be Patient, Your Compression Will Start Soon... 😊</b>", quote=True)
        data.append(message.reply_to_message)
        if len(data) == 1:
         await query.delete()   
         await add_task(message.reply_to_message)     
 
    @app.on_message(filters.incoming & filters.command(["restart", f"restart@{BOT_USERNAME}"]))
    async def restarter(app, message):
        if message.from_user.id in AUTH_USERS:
            await message.reply_text("<b>•Restarting</b>")
            quit(1)
        
    @app.on_message(filters.incoming & filters.command(["clear", f"clear@{BOT_USERNAME}"]))
    async def restarter(app, message):
      data.clear()
      await message.reply_text("✅ <b>Successfully Cleared Queue...</b>")
         
        
    @app.on_message(filters.incoming & (filters.video | filters.document))
    async def help_message(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<b>Opps You Need To Donate Some Amount To Use Meh...🐸👀</b>")
        query = await message.reply_text("<b>Added To Queue... 🚦</b>\n<b>Please Be Patient, Your Compression Will Start Soon... 😊</b>", quote=True)
        data.append(message)
        if len(data) == 1:
         await query.delete()   
         await add_task(message)
            
    @app.on_message(filters.incoming & (filters.photo))
    async def help_message(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<b>Opps You Need To Donate Some Amount To Use Meh...🐸👀</b>")
        os.system('rm thumb.jpg')
        await message.download(file_name='/app/thumb.jpg')
        await message.reply_text('✅ <b>Thumbnail Added.</b>')
        
    @app.on_message(filters.incoming & filters.command(["cancel", f"cancel@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await incoming_cancel_message_f(app, message)
        
        
    @app.on_message(filters.incoming & filters.command(["exec", f"exec@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await exec_message_f(app, message)
        
    @app.on_message(filters.incoming & filters.command(["eval", f"eval@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await eval_message_f(app, message)
        
    @app.on_message(filters.incoming & filters.command(["stop", f"stop@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await on_task_complete()    
   
    @app.on_message(filters.incoming & filters.command(["help", f"help@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await message.reply_text("<b>Hi,</b> <b>I Am Video Encoder Bot.</b>\n\n<b>➥ Send Me Your Telegram Files.</b>\n<b>➥ I Will Encode Them One By One As I Have</b> <b>Queue Feature.</b>\n<b>➥ Just Send Me The Jpg/Pic & It Will Be Set As Your Custom Thumbnail.</b> \n<b>➥ For ffmpeg Lovers [Owner/Sudo Users Only] - You Can Change CRF By</b> /eval crf.insert(0, 'crf value')\n<b>➥ Join @subhasishcloudmirror For Torrenting.</b> \n\n🏷<b>Maintained By: @Subhasish_bot</b>", quote=True)
  
    @app.on_message(filters.incoming & filters.command(["log", f"log@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await upload_log_file(app, message)
    @app.on_message(filters.incoming & filters.command(["ping", f"ping@{BOT_USERNAME}"]))
    async def up(app, message):
      stt = dt.now()
      ed = dt.now()
      v = ts(int((ed - uptime).seconds) * 1000)
      ms = (ed - stt).microseconds / 1000
      p = f"📶Pɪɴɢ = {ms}ms"
      await message.reply_text(v + "\n" + p)

    call_back_button_handler = CallbackQueryHandler(
        button
    )
    app.add_handler(call_back_button_handler)

    # run the APPlication
    
    app.run()
