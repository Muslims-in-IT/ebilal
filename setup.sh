#!/bin/bash
# Exit if any subcommand fails
set -e
printf "[1/5]⏳   Installing apt packages"
sudo apt update && sudo apt -y install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev nginx
printf "[2/5]⏳   Fetching eBilal code"
cd /opt/
sudo git clone https://bitbucket.org/mitpeople/ebilal.git
printf "[3/5]⏳   Fetching Python dependencies"
sudo chown -R pi:pi ebilal
cd ebilal
pip3 install -r requirements.txt
cp ebilal/settings_example.toml ebilal/settings.toml
printf "[4/5]⏳   Setting up eBilal as a service"
sudo cp other/*.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/ebilal*
sudo systemctl daemon-reload
sudo systemctl enable ebilal.service
sudo systemctl start ebilal.service
printf "[4/5]⏳   Setting up eBilal web"
cd /var/www/html/
sudo ln -s /opt/ebilal/ebilal_web .
sudo cp other/ebilal_site_nginx /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/ebilal_site_nginx /etc/nginx/sites-enabled/ebilal_site_nginx
sudo systemctl enable nginx
sudo systemctl start nginx
printf "[5/5]🎉   Finished! Visit http://ebilal.local on your browser.\n"