# -*- coding: utf-8 -*-
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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn
# Named "ebilal" (not __name__, which is "__main__" when run as a script) so
# module loggers such as "ebilal.pimoroni" share these handlers.
logger = logging.getLogger("ebilal")

# Paths. Everything is relative to where this file lives so the app runs the
# same from /opt/ebilal (systemd), a Docker image, or a dev checkout.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.environ.get("EBILAL_SETTINGS", os.path.join(APP_DIR, "settings.toml"))
WEB_DIR = os.path.join(APP_DIR, "ebilal_web")

# Feeds pinned to the top of the web UI until the user unpins them.
DEFAULT_PINNED = ["activestream"]  # 24/7 Quraan recitation

# Log to journald when running under systemd, otherwise to stderr (Docker, dev).
try:
    from cysystemd.journal import JournaldLogHandler
    journald_handler = JournaldLogHandler()
    journald_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(journald_handler)
except Exception:  # not on a systemd host, or cysystemd not installed
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(stream_handler)

# Small rotating file, shown in the web UI's Diagnostics box
try:
    file_handler = RotatingFileHandler(os.path.join(WEB_DIR, 'web.log'), maxBytes=1024, backupCount=1)
    file_handler.setLevel(level=logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(file_handler)
except OSError:
    pass


class Config:
    """Thread-safe view of settings.toml.

    One source of truth for the player and the API, so a write from one can
    never clobber a newer value written by the other. Reads are cached until
    the file's mtime changes. Writes replace lists wholesale (dynaconf's
    merge=True would concatenate them, which breaks removing a favourite).
    """

    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self._mtime = None
        self._data = {}

    def _load(self):
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return {}
        if mtime != self._mtime:
            data = LazySettings(settings_file=self.path).to_dict().get("DEFAULT", {})
            self._data, self._mtime = dict(data), mtime
        return self._data

    def get(self, key, default=None):
        with self._lock:
            return self._load().get(key, default)

    def update(self, **values):
        with self._lock:
            data = dict(self._load())
            data.update(values)
            write(self.path, {"DEFAULT": data}, merge=False)
            self._mtime = None  # force re-read next time
            return data


config = Config(SETTINGS_PATH)

# LiveMasjid client
class LivemasjidClient:
    """Livemasjid client Object"""
    VOLUME_COMMIT_DELAY = 0.5  # seconds of button quiet before a volume change is applied

    def __init__(self, cfg=None):
        self.cfg = cfg or config
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.livestreams = []
        self.mounts = {}
        self.state = {"status":"starting"}
        self.mountToPlay = []
        self.audio_device = ""
        self.playing = ""
        self.current_url = ""
        self.process = None
        self.volume = 80  # 0-100, applied in the player (ffplay -af volume=)
        self._vol_lock = threading.Lock()
        self._vol_timer = None
        self.load_config()

    def load_config(self, reload = False):
        logger.debug("reloading config file")
        self.baseURL = self.cfg.get("server_url", "http://livemasjid.com:8000/")
        logger.debug("Server URL: "+ self.baseURL)
        self.mountToPlay = list(self.cfg.get("mounts", []))
        self.audio_device = self.cfg.get("audio_device", "")
        self.pimoroni = bool(self.cfg.get("pimoroni", False))
        try:
            self.volume = int(self.cfg.get("volume", self.volume))
        except Exception:
            pass
        loglevel = self.cfg.get("loglevel", "INFO")
        if loglevel == "DEBUG":
            logger.setLevel(logging.DEBUG)
        elif loglevel == "INFO":
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
        if self.state.get("status") in ("starting", None):
            self.state["status"] = "connected"

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self,client, userdata, msg):
        logger.debug(msg.topic+" "+str(msg.payload))
        message = msg.topic.split('/')
        mount, payload = message[1], msg.payload.decode()
        self.mounts[mount] = payload
        if mount in self.mountToPlay:
            if "started" in payload:
                self.playmount(mount)
                if mount not in self.livestreams:
                    self.livestreams.append(mount)
            elif "stopped" in payload:
                # Only silence the player if it is this stream that ended
                if self.playing == mount:
                    self.stop()
                if mount in self.livestreams:
                    self.livestreams.remove(mount)

    # ---- what is live, and in what order do the skip buttons walk it ----
    def live_mounts(self):
        """Every mount MQTT reports as started, minus the .mp3 transcode twins."""
        live = sorted(m for m, p in self.mounts.items() if "started" in p)
        return [m for m in live if not (m.endswith(".mp3") and m[:-4] in live)]

    def playlist(self):
        """Live streams in skip order for the hardware buttons: your autoplay
        (liked) feeds first, in the order you liked them, then everything else."""
        live = self.live_mounts()
        liked = [m for m in self.mountToPlay if m in live]
        return liked + [m for m in live if m not in liked]

    def step(self, direction):
        """Play the next (+1) or previous (-1) live stream, wrapping around.
        Returns the mount now playing, or None if nothing is live."""
        playlist = self.playlist()
        if not playlist:
            logger.info("Skip pressed but no streams are live")
            return None
        try:
            target = playlist[(playlist.index(self.playing) + direction) % len(playlist)]
        except ValueError:  # nothing playing yet, or the last stream has gone offline
            target = playlist[0] if direction > 0 else playlist[-1]
        self.playmount(target)
        return target

    def toggle(self):
        """Play/pause. A live stream cannot truly pause, so pause = stop, and
        play resumes the last stream (or the first in the playlist) at the live edge."""
        if self.is_playing():
            self.stop()
            return "stopped"
        target = self.playing or (self.playlist() or [None])[0]
        if not target:
            logger.info("Play pressed but no streams are live")
            return None
        self.playmount(target)
        return target

    def is_playing(self):
        return self.process is not None and self.process.poll() is None

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
        if self.process is not None:
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
            self.cfg.update(volume=self.volume)
        except Exception as e:
            logger.error("Could not persist volume: %s", e)
        if self.state.get("status") == "playing" and self.current_url:
            self.playurl(self.current_url)
        return self.volume

    def nudge_volume(self, delta):
        """Change volume instantly in memory, then apply it (relaunch the stream
        and write settings.toml) once the buttons have been quiet for a moment.
        Holding a button fires this many times a second; applying each one would
        restart ffplay constantly and hammer the SD card."""
        with self._vol_lock:
            self.volume = max(0, min(100, self.volume + delta))
            if self._vol_timer is not None:
                self._vol_timer.cancel()
            self._vol_timer = threading.Timer(self.VOLUME_COMMIT_DELAY, self._commit_volume)
            self._vol_timer.daemon = True
            self._vol_timer.start()
            return self.volume

    def _commit_volume(self):
        self.set_volume(self.volume)

    def volup(self):
        return self.set_volume(self.volume + 10)

    def voldown(self):
        return self.set_volume(self.volume - 10)

    def getlivestreams(self):
        return self.livestreams

    def getmounts(self):
        return self.mounts

    def getstate(self):
        # ffplay exits by itself when a stream ends; don't keep claiming "playing"
        if self.state.get("status") == "playing" and not self.is_playing():
            self.state["status"] = "stopped"
            self.state["mount"] = ""
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

# Volume is handled in the player (ffplay -af volume=) via the LivemasjidClient,
# so it works regardless of the DAC's mixer controls or the service user's ALSA
# view. See LivemasjidClient.set_volume / get_volume.

@app.get("/favourites")
def read_mounts():
    return {"favourites": config.get("mounts", [])}

class favourites(BaseModel):
    favourites: List[str]

@app.post("/favourites")
def write_mounts(favourites: favourites):
    config.update(mounts=favourites.favourites)
    livemasjid.set_mounts(favourites.favourites)
    return {"favourites": favourites.favourites}

# Pinned feeds sit at the top of the web UI. Pinning is purely presentation:
# what plays automatically is the favourites ("autoplay") list above.
# Quraan recitation is pinned out of the box;
# any feed can be pinned and the user can unpin all of them, so "never set"
# (use the default) is distinct from "set to empty".
@app.get("/pinned")
def read_pinned():
    return {"pinned": list(config.get("pinned", DEFAULT_PINNED))}

class pinned(BaseModel):
    pinned: List[str]

@app.post("/pinned")
def write_pinned(pinned: pinned):
    # De-duplicate, keep order
    ordered = list(dict.fromkeys(pinned.pinned))
    config.update(pinned=ordered)
    return {"pinned": ordered}

@app.get("/server_url")
def read_server_url():
    return {"server_url": config.get("server_url")}

@app.post("/server_url/")
def write_url(url: str):
    config.update(server_url=url)
    return {"server_url": url}

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

# Same actions as the physical buttons, for scripts and other controllers.
@app.post("/player/toggle")
def player_toggle():
    livemasjid.toggle()
    return livemasjid.getstate()

@app.post("/player/next")
def player_next():
    livemasjid.step(+1)
    return livemasjid.getstate()

@app.post("/player/prev")
def player_prev():
    livemasjid.step(-1)
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

    # Physical buttons + LEDs, if a pHAT BEAT is fitted and enabled in
    # settings.toml. Buttons arrive as kernel key events (see pimoroni.py).
    if livemasjid.pimoroni:
        try:
            from pimoroni import PhatBeatControls
            PhatBeatControls(livemasjid).start()
        except Exception as e:  # never let a hardware problem take the player down
            logger.error("Pimoroni controls disabled: %s", e)

    #Start the API
    # NOTE: reload=True spawns a filesystem watcher that pegs the Pi Zero's
    # single core at ~85% CPU. It is a dev-only feature and must stay off in
    # production. The code below uvicorn.run was unreachable dead code (uvicorn
    # blocks), so it has been removed; config is reloaded via load_config().
    uvicorn.run(app, host='0.0.0.0', port=8000)


if __name__ == "__main__":
    main()
