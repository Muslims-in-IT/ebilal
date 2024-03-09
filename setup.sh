#!/bin/bash
# Exit if any subcommand fails
set -e
printf "[1/6]⏳   Installing apt packages"
sudo apt update
sudo apt -y install git python3 python3-pip python3-venv ffmpeg ssh-client build-essential libsystemd-dev libasound2-dev nginx
printf "[2/6]⏳   Creating ebilal user and setting permissions"
if id "ebilal" &>/dev/null; then
    echo "User ebilal already exists, skipping adduser operation."
else
    sudo adduser --disabled-password --gecos "" ebilal
fi
cd /opt/
sudo adduser ebilal users
sudo adduser ebilal audio
printf "[3/6]⏳   Fetching eBilal code"
if [ ! -d "ebilal" ]; then
  sudo git clone https://github.com/Muslims-in-IT/ebilal
else
  echo "Directory ebilal already exists, skipping clone operation."
fi
sudo chown -R ebilal:users ebilal
printf "[4/6]⏳   Fetching Python dependencies"
sudo su - ebilal << EOF
cd /opt/ebilal
python3 -m venv venv
source venv/bin/activate
pip3 install --no-cache-dir -r requirements.txt
cp settings_example.toml settings.toml
EOF
printf "[5/6]⏳   Setting up eBilal as a service"
cd /opt/ebilal
sudo cp other/*.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/ebilal*
sudo systemctl daemon-reload
sudo systemctl enable ebilal.service
sudo systemctl start ebilal.service
printf "[6/6]⏳   Setting up eBilal web"
cd /var/www/html/
if [ ! -L "./ebilal_web" ]; then
    sudo ln -s /opt/ebilal/ebilal_web .
fi
sudo cp /opt/ebilal/other/ebilal_site_nginx /etc/nginx/sites-available/
sudo systemctl restart nginx