# eBilal

This project turns a Raspberry Pi into an alternative to Radio Bilal. Once setup, it will play your selected live audio streams from livemasjid.com.

##
Latest: 26 Jan 2022
Release notes:
* Merged API into main code
* Added web interface
* Other bug fixes

Revision: 1.0 19th April 2021
Release notes: 
* Added release notes
* Added API
* Added support for alternative ALSA audio devices in settings (still testing)

## Installation
### The quick way 
1. Download setup.sh from the link above
2. `bash setup.sh`

### The responsible way
1. Install latest [Raspbian Lite](https://downloads.raspberrypi.org/raspbian_lite_latest)
2. Setup [Wifi and SSH](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
3. Boot and SSH
4. `sudo apt update && sudo apt install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev nginx`
5. `cd /opt/`
6. `sudo git clone https://bitbucket.org/mitpeople/ebilal.git`
7. `sudo chown -R pi:pi ebilal`
8. `cd ebilal`
9. `pip3 install -r requirements.txt`
10. `cp /opt/ebilal/settings_example.toml /opt/ebilal/settings.toml`
11. `sudo cp /opt/ebilal/other/*.service /lib/systemd/system/`
12. `sudo chmod 644 /lib/systemd/system/ebilal*`
13. `sudo systemctl daemon-reload`
14. `sudo systemctl enable ebilal.service`
15. `cd /var/www/html/`
16. `sudo ln -s /opt/ebilal/ebilal_web .`
17. `sudo cp /opt/ebilal/other/ebilal_site_nginx /etc/nginx/sites-available/`
18. `sudo ln -s /etc/nginx/sites-available/ebilal_site_nginx /etc/nginx/sites-enabled/ebilal_site_nginx`
19. `sudo systemctl enable nginx`
20. `sudo systemctl start nginx`

## Test
1. `sudo systemctl start ebilal.service`
2. Visit http://ebilal.local on your browser
3. Listen for audio, if none, `sudo systemctl status ebilal.service`

## Configure audio device and stream
1. Modify settings.toml and update `MOUNTS=["activestream"]` to set streams to listen to (pick from livemasjid.com using the last word in the stream URL). e.g. `MOUNTS=["greensidemasjid"]`
2. Audio device `audio_device=""` can be set to the value of the device name when running `sudo amixer` Default is "", other options to try: "PCM" or "Master"

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

## Web interface
Visit the alpha web interface by using your browser to visit the IP address of your Raspberry pi: http://<pi ip address>/

## Optional

If you're using the [pimoroni](https://shop.pimoroni.com/products/pirate-radio-pi-zero-w-project-kit):
`curl https://get.pimoroni.com/phatbeat | bash`

## Experimental
A docker image has been setup, usage:
docker run mitpeople/ebilal:latest <mountname> --device /dev/snd 

## License
Licensed under AGPL-3.0-or-later (or AGPL-3.0-only 
