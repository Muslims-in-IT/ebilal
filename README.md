# eBilal

This project turns a Raspberry Pi into an alternative to Radio Bilal. Once setup, it will play your selected live audio streams from livemasjid.com.

Moving the primary repo to [Github](https://github.com/Muslims-in-IT/ebilal)

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

### The quick way 
1. Download the setup script: `wget https://raw.githubusercontent.com/Muslims-in-IT/ebilal/main/setup.sh`
2. Run the setup script: `bash setup.sh`

### The responsible way
1. Install latest [Raspbian Lite](https://downloads.raspberrypi.org/raspbian_lite_latest)
2. Setup [Wifi and SSH](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
3. Boot and SSH
4. `sudo apt update && sudo apt install git python3 python3-pip ffmpeg ssh-client build-essential libsystemd-dev libasound-dev nginx`
5. `sudo adduser --disabled-password --gecos "" ebilal`
6. `cd /opt/`
7. `sudo git clone https://github.com/Muslims-in-IT/ebilal.git`
8. `sudo chown -R ebilal:ebilal ebilal`
9. `cd ebilal`
10. `sudo -u ebilal python3 -m venv venv`
11. `sudo -u ebilal bash -c "source venv/bin/activate && pip3 install -r requirements.txt"`
12. `cp settings_example.toml settings.toml`
13. `sudo cp other/*.service /lib/systemd/system/`
14. `sudo chmod 644 /lib/systemd/system/ebilal*`
15. `sudo systemctl daemon-reload`
16. `sudo systemctl enable ebilal.service`
17. `cd /var/www/html/`
18. `sudo ln -s /opt/ebilal/ebilal_web .`
19. `sudo cp other/ebilal_site_nginx /etc/nginx/sites-available/`
20. `sudo systemctl restart nginx`

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
`docker run -ti --rm -v /dev/snd:/dev/snd --privileged mitpeople/ebilal_pi0:latest`
`docker run -it --rm --device /dev/snd mitpeople/ebilal:latest`

## License
Licensed under AGPL-3.0-or-later (or AGPL-3.0-only 
