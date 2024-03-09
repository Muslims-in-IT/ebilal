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
4. Download the setup script: `wget https://raw.githubusercontent.com/Muslims-in-IT/ebilal/main/setup.sh`
5. Review the setup script: `cat setup.sh`
6. Run the steps manually one at a time or if you're comfortable with the script, run it: `bash setup.sh`

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
