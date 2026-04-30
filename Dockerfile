# Use a slim, secure Debian-based Python image
FROM python:3.10-slim-buster

# FIX: Install FFmpeg, MediaInfo, and 'tini' (the ultimate zombie process reaper)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    tini \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy only the requirements first to cache the pip install step
COPY requirements.txt .

# FIX: Create a virtual environment to bypass the pip root warning and ensure C-extensions compile safely
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install the requirements
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# FIX: Use Tini as the entrypoint to manage the async process tree and prevent zombie deadlocks
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the Master Bootloader
CMD ["python", "-m", "bot"]