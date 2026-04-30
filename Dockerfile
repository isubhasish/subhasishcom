FROM python:3.10-slim-bookworm

RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    tini \
    build-essential \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot"]