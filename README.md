# 🎬 Subhasish Encoder - Advanced Telegram Video Compressor

A high-performance, modular Telegram Bot designed to securely download, compress, and upload massive video files directly on an Oracle Always Free VPS. 

Built with advanced FFmpeg integration, `pyrofork` MTProto architecture, and a bulletproof Dockerized environment. **100% DMCA Safe.**

---

## ✨ Enterprise Features

* 🚀 **Dynamic 4GB Limit Bypass:** Natively detects Premium vs. Non-Premium User Sessions to seamlessly handle 2.0GB or 4.0GB uploads.
* 🛡️ **Mime-Type Armor:** Instantly rejects disguised ZIP/PDF documents to protect your server's bandwidth.
* 🎛️ **Interactive UI Menu (`/bsetting`):** Change `CRF`, `CODEC`, Watermarks, and Document Uploads instantly with a visual toggle board.
* ✂️ **Smart Auto-Splitter:** Safely segments files that exceed Telegram's size limits without losing video quality.
* 🖥️ **Live Hardware Telemetry:** Monitor your Oracle VPS's CPU, RAM, and Network I/O directly in your Telegram chat (`/status`).
* 🏷️ **Custom Watermarking:** Burn your own custom text natively into your compressed videos.

---

## 🛠️ Deployment (Oracle VPS via Docker)

### 1. Set Up Your Configuration
Rename `config.sample.json` to `config.json` inside your private repo and fill in your details:
* Get `API_ID` and `API_HASH` from `my.telegram.org`.
* Get `USER_SESSION_STRING` from a Pyrogram String Session generator (Required for expanded limits).

### 2. Connect via SSH (PuTTY) & Install Tools
Run this magical one-liner to securely install all necessary packages natively on your Ubuntu server:

```bash
sudo apt-get update && sudo apt-get upgrade -y && sudo apt-get install docker.io docker-compose git -y




# How to deploy?



## Deploy to Heroku (Using Dockerfile & Team)

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?team=amc-tg-dev&template=https://github.com/isubhasish/backup)

## Deploy Normally On ORACLE VPS For Our New Bot

### Advanced Installing Sequence

- Update the Server & Install Everything.
```
sudo apt-get update && sudo apt-get upgrade -y
```
```
sudo apt-get install docker.io docker-compose git -y
```

- Clone & Select This Private Repo:
```
git clone https://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@github.com/isubhasish/aiencoder/
```
```
cd aiencoder
```
Build and Run the Bot.
```sh
sudo docker-compose up -d --build
```
### Check Live Logs
Included Beautiful Custom Boot Sequence.
```sh
sudo docker logs -f subhasish_compressor
```

------


### Deploying On VPS Using Docker

- Set Up The Repository:
```
apt-get update
```
```
sudo apt-get install \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
```
- Add Docker’s Official GPG Key:
```
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
```
- Set Up The Stable Repository:
```
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

- Install Docker:
```
apt-get install -y docker.io
```
- Check The Docker:
```
docker ps
```
- Clone & Select This Private Repo:
```
git clone https://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@github.com/isubhasish/backup/
```
```
cd backup
```
- Build and Run Docker & App:
```
apt install docker-compose
```
```
docker-compose up --build
```
------
### To Stop The Container (Will Not Affect On The Image):
```
sudo docker ps
```
```
sudo docker stop id
```
```
sudo docker-compose down
```
------
### To Delete The Image (When Necessary):
```
sudo docker container prune
```
```
sudo docker image prune -a
```
```
sudo docker-compose down --rmi all
```
```
sudo docker builder prune -a -f
```
```
sudo docker system prune -a -f
```
------

### Bot Father Setting Commands:
```
start - Start The Bot 🤖
ping - Check Bot's Up Time ⏰
status - Check the active compression, queue, and server Hardware
clear - Clear Your Queued Tasks 🔫
help - For Getting Help 🤔
settings - ⚠️ Check Current Ffmpeg Code Settings [Owner/Sudo Only]
preset - ⚠️ Change Preset Settings [Owner/Sudo Only]
crf - ⚠️ Change CRF Value [Owner/Sudo Only]
audio - ⚠️ Change Audio Settings [Owner/Sudo Only]
resolution - ⚠️ Change Video Resolution [Owner/Sudo Only]
codec - ⚠️ Your Codec Settings [Owner/Sudo Only]
mediainfo - ⚠️ Get MediaInfo of a video [Owner/Sudo]
samplegen - ⚠️ Generate a random 30sec preview sample [Owner/Sudo]
setthumbnail - Reply to an image to save your custom thumbnail
delthumbnail - Safely delete your custom thumbnail
bsetting - ⚠️ Change Bot Config values live [Owner]
exec - ⚠️ Execution [Owner/Sudo Only]
stop - ⚠️ Stop The Current Task [Owner/Sudo Only]
cancel - ⚠️ Cancel all tasks [Owner/Sudo Only]
cancelall - ⚠️ Cancel all active and queued tasks [Owner/Sudo]
speedtest - ⚠️ Test the Server's Download/Upload speed [Owner/Sudo]
broadcast - ⚠️ Send a message to all authorized users [Owner]
log - ⚠️ Get the Bot Log [Owner/Sudo Only]
restart - ⚠️ Restart the Bot [Owner/Sudo Only]
```