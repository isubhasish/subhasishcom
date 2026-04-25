FROM python:3.10-slim

# Installs FFmpeg and MediaInfo safely
RUN apt-get update && apt-get install -y ffmpeg mediainfo git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "-m", "bot.bot"]