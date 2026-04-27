FROM python:3.10-slim

# 1. Added build-essential and python3-dev to compile TgCrypto on Oracle ARM processors
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# 2. Installs the Python requirements safely
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "-m", "bot"]