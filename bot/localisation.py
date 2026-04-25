class Localisation:
    START_TEXT = "🤖 **Gemini Modular Compressor Online!**\nSend a video to begin."
    HELP_TEXT = (
        "🤖 **Bot Help & Basic Commands**\n\n"
        "Send me any video file (up to 4GB) and I will automatically compress it into a highly optimized HEVC format.\n\n"
        "**Basic Commands:**\n"
        "• /status - Check the current compression queue\n"
        "• /ping - Check my uptime\n"
        "• /setthumbnail - Reply to an image to set a custom cover\n"
        "• /delthumbnail - Safely delete your custom thumbnail"
    )
    CANCEL_PROMPT = "⚠️ Are you sure you want to cancel the ongoing task?"
    CANCELLED_MSG = "🛑 **Task Cancelled.** Moving to next in queue..."
    NO_ACTIVE_TASK = "⚠️ No active compression task running right now."
    THUMB_SAVED = "✅ Custom thumbnail saved successfully!"
    THUMB_DELETED = "✅ Thumbnail deleted successfully."
    THUMB_WARNING = "⚠️ Your existing thumbnail will be deleted. Are you sure?"