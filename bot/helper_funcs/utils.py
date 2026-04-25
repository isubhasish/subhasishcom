import asyncio
import time

queue = asyncio.Queue()
START_TIME = time.time()

class AppState:
    current_process = None
    active_file_name = "None"
    pending_tasks = {}
    awaiting_index = {}