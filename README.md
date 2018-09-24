# eBilal

1. Install latest Raspbian Lite
2. Setup Wifi and SSH
3. Boot and SSH
4. sudo apt install git python-pip vlc-nox
5. pip install python-vlc paho-mqtt
6. cd /opt/
7. sudo git clone https://<your_username>@bitbucket.org/mitpeople/ebilal.git
8. sudo chown -R pi:pi ebilal
9. sudo cp ebilal/other/ebilal.service /lib/systemd/system/
10. sudo chmod 644 /lib/systemd/system/ebilal.service
11. sudo systemctl daemon-reload
12. sudo systemctl enable ebilal.service
13. reboot



