#!/bin/bash
# Exit if any subcommand fails
set -e
printf "[1/5]⏳   Installing apt packages"
sudo apt update
sudo apt -y install git python3 python3-pip python3-venv ffmpeg ssh-client build-essential libsystemd-dev libasound2-dev nginx
printf "[2/5]⏳   Fetching eBilal code"
cd /opt/
if [ ! -d "ebilal" ]; then
  sudo git clone https://github.com/Muslims-in-IT/ebilal
else
  echo "Directory ebilal already exists, skipping clone operation."
fi
printf "[2.5/5]⏳   Creating ebilal user and setting permissions"
if id "ebilal" &>/dev/null; then
    echo "User ebilal already exists, skipping adduser operation."
else
    sudo adduser --disabled-password --gecos "" ebilal
fi
sudo adduser ebilal users
sudo adduser ebilal audio
sudo chown -R ebilal:users ebilal
printf "[3/5]⏳   Fetching Python dependencies"
cd ebilal
sudo -u ebilal python3 -m venv venv
sudo -u ebilal bash -c "source venv/bin/activate && pip3 install --no-cache-dir -r requirements.txt"
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