<div align="center">
  <img src="https://cdn.jsdelivr.net/gh/isubhasish/Images@svg/banner.svg" alt="Subhasish Encoder Banner" width="100%">
</div>

*A high-performance, modular Telegram Bot designed to securely download, compress, and upload massive video files directly on Heroku or VPS.*

Built with advanced FFmpeg integration, `kurigram` MTProto architecture, and a bulletproof Dockerized environment.

<div align="center">

**100% DMCA Safe.**

</div>

---
## ✨ Enterprise Features

* 🚀 **Dynamic 4GB Limit Bypass:** Natively detects Premium vs. Non-Premium User Sessions to seamlessly handle 2.0GB or 4.0GB uploads.
* 🛡️ **Mime-Type Armor:** Instantly rejects disguised ZIP/PDF documents to protect your server's bandwidth.
* 🎛️ **Interactive UI Menu (`/bsetting`):** Change `CRF`, `CODEC`, Watermarks, and Document Uploads instantly with a visual toggle board.
* ✂️ **Smart Auto-Splitter:** Safely segments files that exceed Telegram's size limits without losing video quality.
* 🖥️ **Live Hardware Telemetry:** Monitor your Server's CPU, RAM & Network I/O directly in your Telegram chat (`/status`).
* 🏷️ **Custom Watermarking:** Burn your own custom text natively into your compressed videos.
* 📦 **Always Up-To-Date:** The Dockerfile automatically pulls the absolute latest stable versions of Python, FFmpeg, Git, MediaInfo and everything else to guarantee maximum performance, speed, and security.

---
## ☁️ Deploy To Heroku (Using Dockerfile & Team)
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?team=amc-tg-dev&template=https://github.com/isubhasish/subhasishcom)

---
## 🛠️ Deployment (VPS Via Docker)
### 1️⃣ Advanced Installing Sequence
**Update The Server & Install Everything:**
```sh
sudo apt-get update && sudo apt-get upgrade -y
```
**Only Select If There Is An Upgrade Left Inside Putty:**
```sh
sudo apt-get dist-upgrade -y
```
```sh
sudo apt-get install docker.io docker-compose git -y
```
**Remove Any Existing Repository:**
```sh
sudo rm -rf
```
*(If you are redeploying or need to clean up an old version of the project before cloning it again, run this command to forcefully remove the old folder)*

**Switch to Root User (Superuser):**
```sh
sudo su
```
<i><b>(Note:</b> <u>To gain full administrative privileges and avoid having to type `sudo` before every single command during your setup, switch to the root user!</u></i>)

**Clone & Select This Private Repo:**
```sh
git clone https://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@github.com/isubhasish/subhasishcom/
```
```sh
cd subhasishcom
```
**Build & Run The Bot:**
```sh
sudo docker compose pull && sudo docker compose up -d --build
```
<details>
<summary>

#### ⚠️ Legacy Docker Command (Click To Expand)
</summary>
<br>
<i><b>Note:</b> <u>Do Not Use This Command If You Have Upgraded Your Docker Environment To Compose V2.</u></i>

```sh
sudo docker-compose pull && sudo docker-compose up -d --build
```
</details>

---
### 2️⃣ Check Live Logs
Included Beautiful Custom Boot Sequence.
```sh
sudo docker logs -f encoder
```
---
### 3️⃣ Rebuild The Bot In PuTTY After Making Any Changes In Github Repo
Go to your Putty terminal inside your aiencoder folder and run the clean rebuild command sequence.
```sh
cd subhasishcom
```
```
sudo docker-compose down --rmi all
```
```
git pull
```
**Run Again The Advanced Build Command Like Before After Github Is Updated Our Folder/Files:**
```
sudo docker compose pull && sudo docker compose up -d --build
```
---
## ⚙️ Alternative: Deploying On VPS Using Docker

<details>
<summary>

#### 👇🏻 Click To View The Full Manual Docker Setup Sequence. 👇🏻
</summary>
<br>

**Set Up The Repository:**
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
**Add Docker’s Official GPG Key:**
```
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
```
**Set Up The Stable Repository:**
```
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```
**Install Docker:**
```
apt-get install -y docker.io
```
**Check The Docker:**
```
docker ps
```
**Clone & Select This Private Repo:**
```
git clone https://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@github.com/isubhasish/subhasishcom/
```
```
cd subhasishcom
```
**Build And Run Docker & App:**
```
apt install docker-compose
```
```
docker-compose pull
```
```
docker-compose up --build
```
</details>

---
## 🛑 Container Management

<details>
<summary>

#### 👇🏻 Click To View Here (When Necessary). 👇🏻
</summary>

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
---
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
</details>

---
### ⚡ One Click Stop & Clean (When Necessary):
*If this bot is the ONLY thing running on your VPS, you don't even need to look up the container ID. Run this from anywhere to auto-detect the bot, stop it, and wipe all unused data/volumes instantly.*

```sh
sudo docker stop $(sudo docker ps -aq) && sudo docker system prune -a --volumes -f
```
---
## 🔄 Maintenance

<details>
<summary>

### To Upgrade The Docker Inside VPS (When Necessary): 👇🏻
</summary>

**1️⃣ Download The Official Docker Installation Script:**
```sh
curl -fsSL https://get.docker.com -o get-docker.sh
```
**2️⃣ Run The Script To Upgrade Docker:**
```sh
sudo sh get-docker.sh
```
**3️⃣ Clean Up The Script:**
```sh
rm get-docker.sh
```
**4️⃣ Wake Docker Back Up:**
```sh
sudo systemctl start docker && sudo systemctl enable docker
```
**5️⃣ Run Your Build Using Modern Build Commands:**
```sh
sudo docker compose pull && sudo docker compose up -d --build
```
**6️⃣ Verify Docker & Docker Compose Versions:**
```sh
sudo docker version && sudo docker compose version
```
**7️⃣ Verify Your Docker Images:**
```sh
sudo docker images
```
*(This will list all the Docker images currently stored on your system along with their tags and IDs.)*
</details>

---
## 🤖 Bot Father Setting Commands

*Copy and paste this block directly into BotFather:*

```text
start - Start The Bot 🤖
ping - Check Bot's Up Time & Last Updated Status. ⏰
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
exec - ⚠️ Execution [Owner Only]
eval - ⚠️ Evaluation [Owner Only]
cancel - ⚠️ Cancel all tasks [Owner/Sudo Only]
cancelall - ⚠️ Cancel all active and queued tasks [Owner]
speedtest - ⚠️ Test the Server's Download/Upload speed [Owner/Sudo]
broadcast - ⚠️ Send a message to all authorized users [Owner]
log - ⚠️ Get the Bot Log [Owner/Sudo Only]
restart - ⚠️ Restart the Bot [Owner/Sudo Only]
```