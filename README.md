# eBilal

This project turns a Raspberry Pi into an alternative to Radio Bilal. Once setup, it will play your selected live audio streams from livemasjid.com.

1. Install latest [Raspbian Lite](https://downloads.raspberrypi.org/raspbian_lite_latest)
2. Setup [Wifi and SSH](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
3. Boot and SSH
4. `sudo apt install git python-pip vlc-nox`
5. `pip install python-vlc paho-mqtt`
6. `cd /opt/`
7. `sudo git clone https://<your_username>@bitbucket.org/mitpeople/ebilal.git`
8. `sudo chown -R pi:pi ebilal`
9. `sudo cp ebilal/other/ebilal.service /lib/systemd/system/`
10. `sudo chmod 644 /lib/systemd/system/ebilal.service`
11. `sudo systemctl daemon-reload`
12. `sudo systemctl enable ebilal.service`
13. Modify config.json to set streams to listen to (pick from livemasjid.com using the last word in the stream URL)
13. `sudo reboot`

To check status:
`sudo systemctl status myscript.service`

## Optional

If you're using the [pimoroni](https://shop.pimoroni.com/products/pirate-radio-pi-zero-w-project-kit):
`curl https://get.pimoroni.com/phatbeat | bash`

