# -*- coding: utf-8 -*-
#from gluon import *
import paho.mqtt.client as mqtt
import time
import argparse
import json
import logging
import logging.config
from logging.handlers import RotatingFileHandler
import os
import subprocess
import threading
import urllib.request
from dynaconf import LazySettings
from dynaconf.loaders.toml_loader import write
from cysystemd.journal import JournaldLogHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn
logger = logging.getLogger(__name__)

# instantiate the JournaldLogHandler to hook into systemd
journald_handler = JournaldLogHandler()

# set a formatter to include the level name
journald_handler.setFormatter(logging.Formatter(
    '[%(levelname)s] %(message)s'
))

file_handler = RotatingFileHandler('ebilal_web/web.log', maxBytes=1024, backupCount=1)
file_handler.setLevel(level=logging.DEBUG)

# set a formatter with date and message
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(message)s'
))

# add the journald handler to the current logger
logger.addHandler(journald_handler)
logger.addHandler(file_handler)

# LiveMasjid client
class LivemasjidClient:
    """Livemasjid client Object"""
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.livestreams = []
        self.mounts = {}
        self.state = {"status":"starting"}
        self.mountToPlay = []
        self.audio_device = ""
        self.playing = ""
        self.current_url = ""
        self.volume = 80  # 0-100, applied in the player (ffplay -af volume=)
        self.load_config()

    def load_config(self, reload = False):
        logger.debug("reloading config file")
        settings = LazySettings(settings_file="settings.toml")
        self.baseURL = settings.default.server_url
        logger.debug("Server URL: "+ self.baseURL)
        self.mountToPlay = settings.default.mounts
        self.audio_device = settings.default.audio_device
        self.pimoroni = settings.default.pimoroni
        try:
            self.volume = int(settings.default.get("volume", self.volume))
        except Exception:
            pass
        if (settings.default.loglevel == "DEBUG"):
            logger.setLevel(logging.DEBUG)
        elif (settings.default.loglevel == "INFO"):
            logger.setLevel(logging.INFO)
            
        #Stop any playing streams and start any live streams
        if (reload):
            self.stop()
            for mount in self.mountToPlay:
                if (mount in self.livestreams):
                    self.playmount(mount)
                    return
    
    def set_mounts(self,mounts):
        self.mountToPlay = mounts

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self,client, userdata, flags, rc):
        logger.info("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("mounts/#")
        self.state["status"] = "connected"

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self,client, userdata, msg):
        logger.debug(msg.topic+" "+str(msg.payload))
        message = msg.topic.split('/')
        self.mounts[message[1]] = msg.payload.decode()
        if (message[1] in self.mountToPlay):
            if ("started" in msg.payload.decode()):
                self.playmount(message[1])
                self.livestreams.append(message[1])
            elif "stopped" in msg.payload.decode():
                self.stop()
                if message[1] in self.livestreams: self.livestreams.remove(message[1])

    def playmount(self,mount):
        logger.debug("Playing mount "+mount)
        self.playing = mount
        self.playurl(self.baseURL+mount)
        self.state["status"] = "playing"
        self.state["mount"] = mount

    def playurl(self,url):
        self.stop()
        self.current_url = url
        # ffmpeg volume filter takes a linear gain: 0.0 (mute) .. 1.0 (unity).
        gain = max(0.0, min(1.0, self.volume / 100.0))
        logger.debug("Starting media player at volume %s%%", self.volume)
        self.process = subprocess.Popen(
            ["ffplay", "-vn", "-nostats", "-loglevel", "error",
             "-autoexit", "-nodisp", "-af", "volume=%.3f" % gain, url],
            shell=False)

    def stop(self):
        logger.debug("stopping media player")
        if hasattr(self, 'process') and self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            # Reap the child so it does not linger as a zombie
            try:
                self.process.wait(timeout=5)
            except Exception as e:
                logger.error("Error reaping player process: %s", e)
            self.process = None
        self.state["status"] = "stopped"
        self.state["mount"] = ""

    def tunein(self,mount,start=False):
        self.mountToPlay=mount
        if start:
            self.playmount(mount)

    def connect(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect("livemasjid.com", 1883, 60)

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
    
    def get_volume(self):
        return self.volume

    def set_volume(self, v):
        """Set volume 0-100, persist it, and re-apply live by relaunching the
        current stream (ffmpeg has no runtime volume control for a live feed)."""
        self.volume = max(0, min(100, int(v)))
        try:
            s = LazySettings(settings_file="settings.toml")
            s.default.volume = self.volume
            write('settings.toml', s.to_dict(), merge=True)
        except Exception as e:
            logger.error("Could not persist volume: %s", e)
        if self.state.get("status") == "playing" and self.current_url:
            self.playurl(self.current_url)
        return self.volume

    def volup(self):
        return self.set_volume(self.volume + 10)

    def voldown(self):
        return self.set_volume(self.volume - 10)

    def getlivestreams(self):
        return self.livestreams
    
    def getmounts(self):
        return self.mounts

    def getstate(self):
        return self.state

    def getplaying(self):
        return self.playing

livemasjid = LivemasjidClient()


#API stuff
app = FastAPI(root_path="/api")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = LazySettings(settings_file="/opt/ebilal/settings.toml")

# Volume is handled in the player (ffplay -af volume=) via the LivemasjidClient,
# so it works regardless of the DAC's mixer controls or the service user's ALSA
# view. See LivemasjidClient.set_volume / get_volume.

@app.get("/favourites")
def read_mounts():
    return {"favourites": settings.default.mounts}

class favourites(BaseModel):
    favourites: List[str]

@app.post("/favourites")
def write_mounts(favourites: favourites):
    settings.default.mounts = favourites.favourites
    write('settings.toml', settings.to_dict() , merge=False)
    livemasjid.set_mounts(favourites.favourites)
    return {"favourites": settings.default.mounts}

@app.get("/server_url")
def read_server_url():
    return {"server_url": settings.default.server_url}

@app.post("/server_url/")
def write_url(url: str):
    settings.default.server_url = url
    write('settings.toml', settings.to_dict(), merge=True)
    return {"server_url": settings.default.server_url}

@app.get("/volume")
def read_volume():
    return {"volume": livemasjid.get_volume()}

@app.post("/volume")
def volset(volume:int):
    return {"volume": livemasjid.set_volume(volume)}

@app.post("/volume/up")
def volup():
    return {"volume": livemasjid.volup()}

@app.post("/volume/down")
def voldown():
    return {"volume": livemasjid.voldown()}


# ---------------------------------------------------------------------------
# Software updates (GitHub Releases)
# ---------------------------------------------------------------------------
APP_DIR = "/opt/ebilal"
GITHUB_REPO = "Muslims-in-IT/ebilal"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _git(*args, timeout=60):
    return subprocess.run(
        ["git", "-C", APP_DIR, *args],
        capture_output=True, text=True, timeout=timeout,
    )


def current_version():
    """Installed version from git describe; falls back to the short SHA."""
    r = _git("describe", "--tags", "--always")
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "unknown"


def latest_release():
    """Fetch the latest release tag + notes from GitHub. Returns dict or None."""
    try:
        req = urllib.request.Request(
            RELEASES_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "ebilal"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return {
            "tag": data.get("tag_name"),
            "name": data.get("name"),
            "notes": data.get("body", ""),
            "url": data.get("html_url"),
            "published_at": data.get("published_at"),
        }
    except Exception as e:
        logger.error("Could not fetch latest release: %s", e)
        return None


@app.get("/version")
def get_version():
    return {"version": current_version()}


@app.get("/update/check")
def update_check():
    cur = current_version()
    latest = latest_release()
    if not latest or not latest.get("tag"):
        return {"current": cur, "latest": None, "update_available": False,
                "error": "Could not reach GitHub."}
    available = latest["tag"] != cur
    return {
        "current": cur,
        "latest": latest["tag"],
        "update_available": available,
        "name": latest.get("name"),
        "notes": latest.get("notes"),
        "url": latest.get("url"),
    }


def _do_update(tag):
    """Fetch and check out the given release tag, refresh deps, then restart.
    Runs detached so the HTTP response returns before the service restarts."""
    script = f"""
set -e
cd {APP_DIR}
git fetch --tags --prune origin
git reset --hard {tag}
if [ -f venv/bin/pip ]; then
  venv/bin/pip install --no-cache-dir -r requirements.txt || true
fi
sudo systemctl restart ebilal.service
"""
    # nohup so the restart (which kills us) does not abort mid-script
    subprocess.Popen(
        ["nohup", "bash", "-c", script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@app.post("/update/apply")
def update_apply():
    latest = latest_release()
    if not latest or not latest.get("tag"):
        return {"ok": False, "error": "Could not reach GitHub."}
    tag = latest["tag"]
    if tag == current_version():
        return {"ok": False, "error": "Already on the latest version.", "version": tag}
    logger.info("Applying update to %s", tag)
    _do_update(tag)
    return {"ok": True, "updating_to": tag,
            "message": "Update started. eBilal will restart shortly."}


@app.get("/player/play/{mount}")
def play(mount:str):
    livemasjid.playmount(mount)
    return livemasjid.getstate()

@app.get("/player/stop")
def stop():
    livemasjid.stop()
    return livemasjid.getstate()

@app.get("/player")
def state():
    return livemasjid.getstate()

@app.get("/mounts")
def mounts():
    return {"mounts": livemasjid.getmounts()}

def main():
    logger.info("Starting..")
    parser = argparse.ArgumentParser(description='Linux client for Livemasjid.com streams.')
    livemasjid.connect()

    #Setup the Pimoroni module if it is enabled in settings
    if (livemasjid.pimoroni):
        logger.info("Phatbeat found")
        import phatbeat
        phatbeat.set_all(0,128,0,0.1)
        phatbeat.show()
        time.sleep(1)
        phatbeat.clear()
        phatbeat.show()

        @phatbeat.on(phatbeat.BTN_VOLDN)
        def pb_volume_down(pin):
            livemasjid.voldown()
            logger.debug("Volume down pressed")

        @phatbeat.on(phatbeat.BTN_VOLUP)
        def pb_volume_up(pin):
            livemasjid.volup()
            logger.debug("Volume up pressed")

        @phatbeat.on(phatbeat.BTN_PLAYPAUSE)
        def pb_play_pause(pin):
            time.sleep(0.1)
            phatbeat.clear()
            phatbeat.show()
            if livemasjid.player.is_playing:
                livemasjid.player.pause
            else: livemasjid.player.play

        @phatbeat.on(phatbeat.BTN_FASTFWD)
        def pb_fast_forward(pin):
            try:
                index = livemasjid.livestreams.index(livemasjid.playing)
                livemasjid.playmount(livemasjid.getlivestreams()[index+1])
            except Exception as e:
                livemasjid.playmount(livemasjid.getlivestreams()[0])
                logger.error(e.message, e.args)

        @phatbeat.on(phatbeat.BTN_REWIND)
        def pb_rewind(pin):
            try:
                index = livemasjid.livestreams.index(livemasjid.playing)
                livemasjid.playmount(livemasjid.getlivestreams()[index-1])
            except Exception as e:
                livemasjid.playmount(livemasjid.getlivestreams()[0])
                logger.error(e.message, e.args)

        @phatbeat.on(phatbeat.BTN_ONOFF)
        def perform_shutdown(pin):
            os.system("sudo shutdown -h now")

    #Start the API
    # NOTE: reload=True spawns a filesystem watcher that pegs the Pi Zero's
    # single core at ~85% CPU. It is a dev-only feature and must stay off in
    # production. The code below uvicorn.run was unreachable dead code (uvicorn
    # blocks), so it has been removed; config is reloaded via load_config().
    uvicorn.run(app, host='0.0.0.0', port=8000)


if __name__ == "__main__":
    main()
