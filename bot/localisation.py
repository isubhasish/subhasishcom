#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) @AbirHasan2005

from bot.get_cfg import get_config


class Localisation:
    START_TEXT = "<b>Hey,</b> \n\n<b>I'm a Telegram Video Encoder Bot... 🙂</b> \n\n<b>Please Send Me Any Telegram Big Video File, I Will Compress It Small Video File As Your Requirements! 🙃</b> \n\n<b>Pʀᴇsᴇɴᴛᴇᴅ Bʏ:</b> <b>@subhasishcloudmirror</b>"
   
    ABS_TEXT = "<b>Please Don't Be Selfish..</b>"
    
    FORMAT_SELECTION = "Select the desired format: <a href='{}'>file size might be approximate</a> \nIf you want to set custom thumbnail, send photo before or quickly after tapping on any of the below buttons.\nYou can use /deletethumbnail to delete the auto-generated thumbnail."
    
    
    DOWNLOAD_START = "ℹ️ <b>sᴛᴀᴛᴜs:</b> 📥 <b>Downloading ...</b> 📥 \n"
    
    UPLOAD_START = "ℹ️ <b>sᴛᴀᴛᴜs:</b> 📤 <b>Uploading ...</b> 📤 \n"
    
    COMPRESS_START = "📀 <b>Preparing For Compression ...</b> 💿"
    
    RCHD_BOT_API_LIMIT = "<b>Size Greater Than Maximum Allowed Size (50MB). Neverthless, Trying To Upload.</b>"
    
    RCHD_TG_API_LIMIT = "Downloaded in {} seconds.\nDetected File Size: {}\nSorry. But, I cannot upload files greater than 1.95GB due to Telegram API limitations."
    
    COMPRESS_SUCCESS = "<b>©ᴇɴᴄᴏᴅᴇᴅ Bʏ:</b> <b>@SubhasishEncoderRobot</b>"

    COMPRESS_PROGRESS = "⏰ <b>ᴇᴛᴀ:</b> {}\n⚡️ <b>ᴘʀᴏɢʀᴇss:</b> {}%"

    SAVED_CUSTOM_THUMB_NAIL = "✅ <b>Custom Video / File Thumbnail Saved. This Image Will Be Used In The Video / File.</b>"
    
    DEL_ETED_CUSTOM_THUMB_NAIL = "✅ <b>Custom Thumbnail Cleared Succesfully.</b>"
    
    FF_MPEG_DEL_ETED_CUSTOM_MEDIA = "✅ <b>Media Cleared Succesfully.</b>"
    
    SAVED_RECVD_DOC_FILE = "✅ <b>Downloaded Successfully.</b>"
    
    CUSTOM_CAPTION_UL_FILE = " "
    
    NO_CUSTOM_THUMB_NAIL_FOUND = "<b>No Custom ThumbNail Found.</b>"
    
    NO_VOID_FORMAT_FOUND = "no-one gonna help you\n{}"
    
    USER_ADDED_TO_DB = "User <a href='tg://user?id={}'>{}</a> added to {} till {}."
    
    FF_MPEG_RO_BOT_STOR_AGE_ALREADY_EXISTS = "⚠️ Already one Process going on! ⚠️ \n\nCheck Live Status on Updates Channel."
    
    HELP_MESSAGE = get_config(
        "STRINGS_HELP_MESSAGE",
        "Hi, I am Video Compressor Bot \n\n1. Send me your telegram big video file \n2. Reply to the file with: `/compress 50` \n\nMY MASTER: @idsubhasish"
    )
    WRONG_MESSAGE = get_config(
        "STRINGS_WRONG_MESSAGE",
        "current CHAT ID: <code>{CHAT_ID}</code>"
    )