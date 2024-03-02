#!/bin/bash
# Exit if any subcommand fails
set -e
printf "[1/5]⏳   Installing apt packages"
sudo apt update && sudo apt -y install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev libasound2-dev nginx
printf "[2/5]⏳   Fetching eBilal code"
cd /opt/
sudo git clone https://github.com/Muslims-in-IT/ebilal
printf "[3/5]⏳   Fetching Python dependencies"
sudo chgrp -R users ebilal
cd ebilal
python -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
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
sudo rm /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/ebilal_site_nginx /etc/nginx/sites-enabled/ebilal
sudo systemctl enable nginx
sudo systemctl start nginx
printf "[5/5]🎉   Finished! Visit http://ebilal.local on your browser.\n"
