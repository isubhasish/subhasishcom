import os
import json

class Config:
    CONFIG_FILE = "config.json"
    THUMB_DIR = "thumbnails"

    TG_BOT_TOKEN = "your_bot_token"
    API_ID = 123456
    API_HASH = "your_api_hash"
    OWNER_ID = 123456789
    LOG_CHANNEL = -100123456789
    AUTH_USERS = [123456789]
    USER_SESSION_STRING = "" # Add your string session here dynamically via /setvar
    
    # FFmpeg Defaults
    CRF = "33.5"
    RESOLUTION = "820x480"
    AUDIO_BITRATE = "112k"
    PRESET = "fast"
    CODEC = "libx265"

    @staticmethod
    def load_config():
        if not os.path.exists(Config.CONFIG_FILE):
            default = {
                "API_ID": Config.API_ID, "API_HASH": Config.API_HASH, "TG_BOT_TOKEN": Config.TG_BOT_TOKEN,
                "OWNER_ID": Config.OWNER_ID, "LOG_CHANNEL": Config.LOG_CHANNEL, "AUTH_USERS": Config.AUTH_USERS,
                "USER_SESSION_STRING": Config.USER_SESSION_STRING, "CRF": Config.CRF, 
                "RESOLUTION": Config.RESOLUTION, "AUDIO_BITRATE": Config.AUDIO_BITRATE, 
                "PRESET": Config.PRESET, "CODEC": Config.CODEC
            }
            with open(Config.CONFIG_FILE, "w") as f: json.dump(default, f, indent=4)
            return default
        with open(Config.CONFIG_FILE, "r") as f: return json.load(f)

    @staticmethod
    def save_config(config_data):
        with open(Config.CONFIG_FILE, "w") as f: json.dump(config_data, f, indent=4)