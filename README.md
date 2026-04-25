# How to deploy?



## Deploy to Heroku (Using Dockerfile & Team)

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?team=amc-tg-dev&template=https://github.com/isubhasish/backup)

## Deploy Normally On VPS

### Installing Requirements

- Preparing Terminal
```
sudo su
```
```
sudo apt-get update
```
```
sudo apt-get upgrade
```
```
sudo apt install python3-pip
```
- Clone & Select This Private Repo:
```
git clone https://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@github.com/isubhasish/backup/
```
```
cd backup
```
Install The Required Python Modules In Your Machine.
```sh
apt-get -qq install ffmpeg
```
```
pip3 install -r requirements.txt
```
### Deployment
With python3.7 or later.
```sh
python3 -m bot
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
------
### To Delete The Image (When Necessary):
```
sudo docker container prune
```
```
sudo docker image prune -a
```
------
## Easy Deploy:
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)
 
### Bot Father Setting Commands:
```
start - Start The Bot 🤖
ping - Check Bot's Up Time ⏰
status - Check the active compression and queue
clear - Clear Your Queued Tasks 🔫
help - For Getting Help 🤔
settings - ⚠️ Check Current Ffmpeg Code Settings [Owner/Sudo Only]
preset - ⚠️ Change Preset Settings [Owner/Sudo Only]
crf - ⚠️ Change CRF Value [Owner/Sudo Only]
audio - ⚠️ Change Audio Settings [Owner/Sudo Only]
resolution - ⚠️ Change Video Resolution [Owner/Sudo Only]
codec - ⚠️ Your Codec Settings [Owner/Sudo Only]
setthumbnail - Reply to an image to save your custom thumbnail
delthumbnail - Safely delete your custom thumbnail
setvar - ⚠️ Change Config values live (e.g. /setvar CRF 26) [Owner]
exec - ⚠️ Execution [Owner/Sudo Only]
stop - ⚠️ Stop The Current Task [Owner/Sudo Only]
cancel - ⚠️ Cancel all tasks [Owner/Sudo Only]
cancelall - ⚠️ Cancel all active and queued tasks [Owner/Sudo]
log - ⚠️ Get the Bot Log [Owner/Sudo Only]
restart - ⚠️ Restart the Bot [Owner/Sudo Only]
```