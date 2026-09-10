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

### Supported OS / Python version
This has been verified against **Raspberry Pi OS Bookworm (32-bit, "Legacy")**, which ships Python 3.11. Raspberry Pi OS Trixie (Python 3.13) is not currently supported - if you picked "latest" from the [Raspberry Pi OS downloads page](https://www.raspberrypi.com/software/operating-systems/), choose the Bookworm Legacy image instead.

## API
Try the new API here:
http://ebilal.local:8000/docs  (if hostname is ebilal)

## Web interface
Visit the alpha web interface by using your browser to visit the IP address of your Raspberry pi: http://<pi ip address>/

## Optional

If you're using the [pimoroni](https://shop.pimoroni.com/products/pirate-radio-pi-zero-w-project-kit) pHAT Beat:
`curl https://get.pimoroni.com/phatbeat | bash`

**Note:** as of this writing, Pimoroni's installer script fails on current Raspberry Pi OS (Bookworm) for two reasons: it tries to fetch a WiringPi `.deb` from a URL that no longer exists (WiringPi has been discontinued upstream), and its `pip install` step doesn't account for [PEP 668](https://peps.python.org/pep-0668/) ("externally-managed-environment"), which Bookworm enforces by default. The script dies before it reaches the step that enables the I2S DAC, so audio won't work even though it reports partial success. Until the installer is fixed, set it up manually:

1. Add the DAC overlay to `/boot/firmware/config.txt`:
   ```
   echo "dtoverlay=hifiberry-dac" | sudo tee -a /boot/firmware/config.txt
   sudo reboot
   ```
2. The pHAT Beat's DAC chip (PCM5102A) has no hardware volume control, so `aplay -l` will show the card but `amixer scontrols` will be empty. Create `/etc/asound.conf` to add a software volume control:
   ```
   pcm.hifiberry_out {
       type hw
       card sndrpihifiberry
   }
   pcm.softvol {
       type softvol
       slave.pcm "hifiberry_out"
       control {
           name "PCM"
           card 0
       }
       min_dB -51.0
       max_dB 0.0
   }
   pcm.!default {
       type plug
       slave.pcm "softvol"
   }
   ctl.!default {
       type hw
       card 0
   }
   ```
3. The `softvol` control is only registered with ALSA the first time something opens the `default` PCM device, so trigger and persist it once before starting the service:
   ```
   speaker-test -D default -c 2 -t sine -f 440 -l 1
   sudo alsactl store
   ```
   This persists the control so `alsa-restore.service` recreates it automatically on every boot, before `ebilal.service` starts.
4. Set `audio_device="PCM"` in `settings.toml` and set `pimoroni=true` to enable the pHAT Beat's buttons and LEDs.

## Experimental
A docker image has been setup, usage:
`docker run -ti --rm -v /dev/snd:/dev/snd --privileged mitpeople/ebilal_pi0:latest`
`docker run -it --rm --device /dev/snd mitpeople/ebilal:latest`

## License
Licensed under AGPL-3.0-or-later (or AGPL-3.0-only 
