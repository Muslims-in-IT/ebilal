# eBilal

1. Install latest Raspbian Lite
2. Setup Wifi and SSH
3. Boot and SSH
4. sudo apt install git python-pip
5. cd /opt/
6. sudo git clone https://yusuf_kaka@bitbucket.org/mitpeople/ebilal.git
7. sudo cp ebilal/other/ebilal.service /lib/systemd/system/
8. sudo chmod 644 /lib/systemd/system/ebilal.service
9. sudo systemctl daemon-reload
10. sudo systemctl enable ebilal.service
11. reboot



