# -*- coding: utf-8 -*-
#from gluon import *
import paho.mqtt.client as mqtt
import time
import argparse
import json
import logging
import logging.config
from logging.handlers import RotatingFileHandler
from importlib import util
import os
import subprocess
import alsaaudio
import threading
from dynaconf import LazySettings
from dynaconf.loaders.toml_loader import write
import pyinotify
from cysystemd.journal import JournaldLogHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
        self.client = mqtt.Client()
        self.livestreams = []
        self.mounts = {}
        self.state = {"status":"starting"}
        self.mountToPlay = []
        self.audio_device = ""
        self.playing = ""
        self.load_config()
        if self.audio_device == "":
            try:
                self.mixer = alsaaudio.Mixer()
            except:
                self.mixer = alsaaudio.Mixer(alsaaudio.mixers()[0])
        else:
            self.mixer = alsaaudio.Mixer(self.audio_device)
        self.current_vol = self.mixer.getvolume()[0]
    
    def load_config(self, reload = False):
        logger.debug("reloading config file")
        settings = LazySettings(settings_file="settings.toml")
        self.baseURL = settings.default.server_url
        logger.debug("Server URL: "+ self.baseURL)
        self.mountToPlay = settings.default.mounts
        self.audio_device = settings.default.audio_device
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
        logger.debug("Starting media player")
        self.process = subprocess.Popen(["ffplay", "-vn", "-nostats", "-autoexit", url], shell=False)

    def stop(self):
        logger.debug("stopping media player")
        if hasattr(self, 'process'): self.process.kill()
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
    
    def volup(self):
        self.current_vol = self.mixer.getvolume()[0] + 10
        self.mixer.setvolume((self.current_vol))
    
    def voldown(self):
        self.current_vol =  self.mixer.getvolume()[0] - 10
        self.mixer.setvolume(self.current_vol)

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

if settings.default.audio_device == "":
    try:
        mixer = alsaaudio.Mixer()
    except:
        mixer = alsaaudio.Mixer(alsaaudio.mixers()[0])
else:
    mixer = alsaaudio.Mixer(settings.default.audio_device)
current_vol = mixer.getvolume()[0]

@app.get("/favourites")
def read_mounts():
    return {"favourites": settings.default.mounts}

@app.post("/favourites")
def write_mounts(favourites: List[str]):
    settings.default.mounts = favourites
    write('settings.toml', settings.to_dict() , merge=False)
    return {"favourites": settings.default.mounts}

@app.get("/server_url")
def read_mounts():
    return {"server_url": settings.default.server_url}

@app.post("/server_url/")
def write_url(url: str):
    settings.default.server_url = url
    write('settings.toml', settings.to_dict(), merge=True)
    return {"server_url": settings.default.server_url}

@app.get("/volume")
def read_root():
    return {"volume": mixer.getvolume()[0]}

@app.post("/volume")
def volset(vol:int):
    mixer.setvolume(vol)
    return {"volume": mixer.getvolume()}

@app.post("/volume/up")
def volup():
    if (mixer.getvolume()[0] <= 90):
        current_vol = mixer.getvolume()[0] + 10
        mixer.setvolume(current_vol)
    return {"volume": mixer.getvolume()}

@app.post("/volume/down")
def volup():
    if (mixer.getvolume()[0] >= 10):
        current_vol = mixer.getvolume()[0] - 10
        mixer.setvolume(current_vol)
    return {"volume": mixer.getvolume()}

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

    #Setup the Pimoroni module if present
    phat_spec = util.find_spec("phatbeat")
    found = phat_spec is not None
    if found:
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
    uvicorn.run("ebilal:app",host='0.0.0.0', port=8000, reload=True, debug=True)

    # Watch for changes in the settings file
    wm = pyinotify.WatchManager()
    wm.add_watch('settings.toml', pyinotify.IN_MODIFY, livemasjid.load_config(reload=True))
    notifier = pyinotify.Notifier(wm)
    notifier.loop()

if __name__ == "__main__":
    main()
