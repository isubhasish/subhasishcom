FROM python:3.10-slim-bookworm

RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    tini \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["python", "-m", "bot"]