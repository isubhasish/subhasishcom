FROM python:3.10-slim

# Silence the red debconf warnings
ENV DEBIAN_FRONTEND=noninteractive 

RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# This is the magic line! It upgrades pip inside the container BEFORE installing requirements
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "-m", "bot"]