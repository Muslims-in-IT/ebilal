#!/bin/bash
sudo apt install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev
cd /opt/
sudo git clone https://bitbucket.org/mitpeople/ebilal.git
sudo chown -R pi:pi ebilal
cd ebilal
pip3 install -r requirements.txt
sudo cp other/*.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/ebilal*
sudo systemctl daemon-reload
sudo systemctl enable ebilal.service
sudo systemctl enable ebilal_api.service
sudo systemctl start ebilal.service
sudo systemctl start ebilal_api.service