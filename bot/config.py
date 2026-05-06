import os
import json

class Config:
    ENV_DIR = "subhasishenv"

    CONFIG_FILE = os.path.join(ENV_DIR, "config.json")
    THUMB_DIR = os.path.join(ENV_DIR, "thumbnails")
    TG_BOT_TOKEN = "your_bot_token"
    API_ID = 123456
    API_HASH = "your_api_hash"
    OWNER_ID = 123456789
    LOG_CHANNEL = -100123456789
    AUTH_USERS = [123456789]
    USER_SESSION_STRING = "" 
    
    CRF = "33.5"
    RESOLUTION = "820x480"
    AUDIO_BITRATE = "112k"
    PRESET = "fast"
    CODEC = "libx265"
    
    WATERMARK_TEXT = "None"
    AS_DOCUMENT = True

    @classmethod
    def load_config(cls):
        if not os.path.exists(cls.ENV_DIR):
            os.makedirs(cls.ENV_DIR)

        if not os.path.exists(cls.THUMB_DIR):
            os.makedirs(cls.THUMB_DIR)

        if not os.path.exists(cls.CONFIG_FILE):
            default_config = cls.get_default_config()
            cls.save_config(default_config)
            return default_config
        with open(cls.CONFIG_FILE, "r") as file:
            return json.load(file)

    @classmethod
    def save_config(cls, config_data):
        if not os.path.exists(cls.ENV_DIR):
            os.makedirs(cls.ENV_DIR)
            
        with open(cls.CONFIG_FILE, "w") as file:
            json.dump(config_data, file, indent=4)

    @classmethod
    def get_default_config(cls):
        return {
            "API_ID": cls.API_ID,
            "API_HASH": cls.API_HASH,
            "TG_BOT_TOKEN": cls.TG_BOT_TOKEN,
            "OWNER_ID": cls.OWNER_ID,
            "LOG_CHANNEL": cls.LOG_CHANNEL,
            "AUTH_USERS": cls.AUTH_USERS,
            "USER_SESSION_STRING": cls.USER_SESSION_STRING,
            "CRF": cls.CRF,
            "RESOLUTION": cls.RESOLUTION,
            "AUDIO_BITRATE": cls.AUDIO_BITRATE,
            "PRESET": cls.PRESET,
            "CODEC": cls.CODEC,
            "WATERMARK_TEXT": cls.WATERMARK_TEXT,
            "AS_DOCUMENT": cls.AS_DOCUMENT
        }