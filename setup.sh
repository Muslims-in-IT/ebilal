#!/bin/bash
# Exit if any subcommand fails
set -e
printf "[1/5]⏳   Installing apt packages"
sudo apt update && sudo apt -y install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev libasound2-dev nginx
printf "[2/5]⏳   Fetching eBilal code"
cd /opt/
sudo git clone https://github.com/Muslims-in-IT/ebilal
printf "[2.5/5]⏳   Creating ebilal user and setting permissions"
sudo adduser --disabled-password --gecos "" ebilal
sudo adduser ebilal users
sudo adduser ebilal audio
sudo chown -R ebilal:users ebilal
printf "[3/5]⏳   Fetching Python dependencies"
cd ebilal
sudo -u ebilal python -m venv venv
source venv/bin/activate
sudo -u ebilal pip3 install -r requirements.txt
cp settings_example.toml settings.toml
printf "[4/5]⏳   Setting up eBilal as a service"
sudo cp other/*.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/ebilal*
sudo systemctl daemon-reload
sudo systemctl enable ebilal.service
sudo systemctl start ebilal.service
printf "[4/5]⏳   Setting up eBilal web"
cd /var/www/html/
sudo ln -s /opt/ebilal/ebilal_web .
sudo cp /opt/ebilal/other/ebilal_site_nginx /etc/nginx/sites-available/
sudo systemctl restart nginx