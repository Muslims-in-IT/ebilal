#!/bin/bash
# Exit if any subcommand fails
set -e
printf "[1/4]⏳   Installing apt packages"
sudo apt -y install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev
printf "[2/4]⏳   Fetching eBilal code"
cd /opt/
sudo git clone https://bitbucket.org/mitpeople/ebilal.git
printf "[3/4]⏳   Fetching Python dependencies"
sudo chown -R pi:pi ebilal
cd ebilal
pip3 install -r requirements.txt
printf "[4/4]⏳   Setting up eBilal as a service"
sudo cp other/*.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/ebilal*
sudo systemctl daemon-reload
sudo systemctl enable ebilal.service
sudo systemctl enable ebilal_api.service
sudo systemctl start ebilal.service
sudo systemctl start ebilal_api.service
printf "[4/4]🎉  Finished! nano /opt/ebilal/settings.toml to configure.\n"