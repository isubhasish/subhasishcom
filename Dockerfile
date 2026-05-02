FROM python:3.10-slim-bookworm

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    tini \
    build-essential \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Create and activate the virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Force Python logs to stream instantly to the Docker console
ENV PYTHONUNBUFFERED=1

# Install Python dependencies cleanly inside the venv
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Use tini as the init process to reap zombie FFmpeg threads
ENTRYPOINT ["/usr/bin/tini", "--"]

# Execute the bot using the venv's primary python binary
CMD ["python", "-m", "bot"]