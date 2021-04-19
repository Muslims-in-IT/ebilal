# eBilal

This project turns a Raspberry Pi into an alternative to Radio Bilal. Once setup, it will play your selected live audio streams from livemasjid.com.

##
Latest revision: 1.0 19th April 2021
Release notes: 
* Added release notes
* Added API
* Added support for alternative ALSA audio devices in settings (still testing)

## Installation

1. Install latest [Raspbian Lite](https://downloads.raspberrypi.org/raspbian_lite_latest)
2. Setup [Wifi and SSH](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
3. Boot and SSH
4. `sudo apt install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev`
5. `cd /opt/`
6. `sudo git clone https://bitbucket.org/mitpeople/ebilal.git`
7. `sudo chown -R pi:pi ebilal`
8. `cd ebilal`
9. `pip3 install -r requirements.txt`
10. `sudo cp other/*.service /lib/systemd/system/`
11. `sudo chmod 644 /lib/systemd/system/ebilal*`
12. `sudo systemctl daemon-reload`
13. `sudo systemctl enable ebilal.service`
14. `sudo systemctl enable ebilal_api.service`

## Test
1. `sudo systemctl start ebilal.service`
2. `sudo systemctl start ebilal_api.service`
3. Listen for audio, if none, 1. `sudo systemctl status ebilal.service`

## Configure audio device and stream
1. Modify settings.toml and update MOUNTS=["activestream"] to set streams to listen to (pick from livemasjid.com using the last word in the stream URL). e.g. MOUNTS=["greensidemasjid"]
2. Audio device audio_device="" can be set to the value of the device name when running `sudo amixer` Default is "", other options to try: "PCM" or "Master"

### To check status and debug:
`sudo systemctl status ebilal.service`
`journalctl -u ebilal.service -f`

## Updates
1. `cd /opt/ebilal`
2. `git reset --hard origin/master`    (Note: this will override your settings.toml, so make a copy 1st)
3. `git pull`
4. `pip3 install -r requirements.txt`
5. `sudo systemctl restart ebilal.service`

## API
Try the new API here:
http://ebilal.local:8000/docs  (if hostname is ebilal)


## Optional

If you're using the [pimoroni](https://shop.pimoroni.com/products/pirate-radio-pi-zero-w-project-kit):
`curl https://get.pimoroni.com/phatbeat | bash`

## Experimental
A docker image has been setup, usage:
docker run mitpeople/ebilal:latest <mountname> --device /dev/snd 
