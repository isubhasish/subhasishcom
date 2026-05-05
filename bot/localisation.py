class Localisation:
    START_TEXT = (
        "<b>Hi,</b> <b>I Am Video Encoder Bot.</b>\n\n"
        "<b>➥ Send Me Your Telegram Files.</b>\n"
        "<b>➥ I Will Encode Them One By One As I Have</b> <b>Queue Feature.</b>\n"
        "<b>➥ Just Send Me The Jpg/Pic & It Will Be Set As Your Custom Thumbnail.</b>\n"
        "<b>➥ For ffmpeg Lovers [Owner/Sudo Users Only] - You Can Change Configs By</b> <code>/bsetting</code>\n\n"
        "🏷<b>Maintained By: @Subhasish_bot</b>"
    )
    
    HELP_TEXT = (
        "🤖 **Bot Help & Basic Commands**\n\n"
        "Send me any video file (up to 4GB) and I will automatically compress it into a highly optimized HEVC format.\n\n"
        "**Basic Commands:**\n"
        "• /status - Check the current compression queue & Server Hardware\n"
        "• /ping - Check my uptime and latency\n"
        "• /setthumbnail - Reply to an image to set a custom cover\n"
        "• /delthumbnail - Safely delete your custom thumbnail"
    )
    
    # --- SMART TEXT STATUS FORMATS ---
    DOWNLOAD_START = "ℹ️ <b>sᴛᴀᴛᴜs:</b> 📥 <b>Downloading ...</b> 📥 \n"
    UPLOAD_START = "ℹ️ <b>sᴛᴀᴛᴜs:</b> 📤 <b>Uploading ...</b> 📤 \n"
    COMPRESS_START = "📀 <b>Preparing For Compression ...</b> 💿"
    DOWNLOADED_SUCCESS = "✅ <b>Downloaded Successfully.</b>\n⏱ <b>Time Taken:</b> {}"
    
    # --- SMART TEXT ERRORS & LIMITS ---
    INVALID_THUMB = "❌ <b>No Custom ThumbNail Found.</b>\n⚠️ Please reply to a valid Image (JPG/PNG) to set it as a thumbnail."
    FILE_SIZE_LIMIT = "⚠️ <b>Telegram API Limit Reached!</b>\nDetected File Size: <b>{}</b>.\n\n✨ 𝘛𝘦𝘭𝘦𝘨𝘳𝘢𝘮 𝘳𝘦𝘴𝘵𝘳𝘪𝘤𝘵𝘴 𝘣𝘰𝘵 𝘶𝘱𝘭𝘰𝘢𝘥𝘴 𝘵𝘰 4.0𝘎𝘉 𝘮𝘢𝘹𝘪𝘮𝘶𝘮. 𝘊𝘰𝘮𝘱𝘳𝘦𝘴𝘴𝘪𝘰𝘯 𝘤𝘢𝘯𝘯𝘰𝘵 𝘱𝘳𝘰𝘤𝘦𝘦𝘥 𝘧𝘰𝘳 𝘵𝘩𝘪𝘴 𝘧𝘪𝘭𝘦. ✨"
    
    # --- NEW: FAILURE STATES ---
    COMPRESS_FAILED = "⚠️ <b>Compression Failed</b> ⚠️"
    UPLOAD_FAILED = "⚠️ <b>Upload Stopped</b> ⚠️"
    DOWNLOAD_FAILED = "⚠️ <b>Download Stopped</b> ⚠️"
    METADATA_FAILED = "⚠️ <b>Getting Video Meta Data Failed</b> ⚠️"
    FILE_NOT_FOUND = "⚠️ <b>Failed Downloaded path not exist</b> ⚠️"

    # --- GENERAL PROMPTS ---
    CANCEL_PROMPT = "<b>Are You Sure? 🚫 This Will Stop The Current Compression..!!🙁</b>"
    CANCELLED_MSG = "🛑 **Task Cancelled.** Moving to next in queue..."
    NO_ACTIVE_TASK = "⚠️ No active compression task running right now."
    THUMB_ADDED = "✅ <b>Thumbnail Added.</b>"
    THUMB_REMOVED = "✅ <b>Thumbnail Removed.</b>"
    THUMB_WARNING = "⚠️ Your existing thumbnail will be deleted. Are you sure?"
    QUEUE_CLEARED = "✅ <b>Successfully Cleared Queue...</b>"
    
    # --- SAMPLE GEN TEXTS ---
    SAMPLE_BUSY = "⚠️ **Bot is Busy!**\nCannot generate a sample while a compression task is running or in queue."
    SAMPLE_DOWNLOADING = "ℹ️ **sᴛᴀᴛᴜs:** 📥 Downloading ... 📥"
    SAMPLE_PROBING = "📼 **Generating Video Duration...** 📼"
    SAMPLE_CUTTING = "🔄 **Generating Sample...**🔄"
    SAMPLE_UPLOADING = "ℹ️ **sᴛᴀᴛᴜs:** 📤 Uploading ... 📤"