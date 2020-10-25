# eBilal

This project turns a Raspberry Pi into an alternative to Radio Bilal. Once setup, it will play your selected live audio streams from livemasjid.com.

## Roll your own instructions

1. Install latest [Raspbian Lite](https://downloads.raspberrypi.org/raspbian_lite_latest)
2. Setup [Wifi and SSH](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
3. Boot and SSH
4. `sudo apt install git python3 python3-pip ffmpeg ssh-client`
5. `wget https://bitbucket.org/mitpeople/ebilal/raw/4bec8e29ce3c7594ab815f4c83fe39ba9977e6e6/requirements.txt`
6. `pip3 install -r requirements.txt`
7. `cd /opt/`
8. `sudo git clone https://bitbucket.org/mitpeople/ebilal.git`
9. `sudo chown -R pi:pi ebilal`
10. `sudo cp ebilal/other/ebilal.service /lib/systemd/system/`
11. `sudo chmod 644 /lib/systemd/system/ebilal.service`
12. `sudo systemctl daemon-reload`
13. `sudo systemctl enable ebilal.service`
14. Modify config.json to set streams to listen to (pick from livemasjid.com using the last word in the stream URL)
15. `sudo reboot`

To check status:
`sudo systemctl status myscript.service`

## Optional

If you're using the [pimoroni](https://shop.pimoroni.com/products/pirate-radio-pi-zero-w-project-kit):
`curl https://get.pimoroni.com/phatbeat | bash`

## Docker
Experimental: A docker image has been setup, usage:
docker run mitpeople/ebilal:latest <mountname> --device /dev/snd 
