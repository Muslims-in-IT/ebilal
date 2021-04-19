# -*- coding: utf-8 -*-
#from gluon import *
import paho.mqtt.client as mqtt
import sys
import time
import argparse
import json
import logging
import logging.config
from importlib import util
import os
import subprocess
import alsaaudio
from dynaconf import LazySettings
import pyinotify


logger = logging.getLogger()
with open('/opt/ebilal/logging.json', 'r') as f:
            config = json.load(f)
            logging.config.dictConfig(config)

class LivemasjidClient:
    """User Object"""
    def __init__(self):
        self.client = mqtt.Client()
        self.livestreams = []
        self.mountToPlay = []
        self.playing = None
        try:
            self.mixer = alsaaudio.Mixer()
        except:
            logger.debug("Default alsa output not there, so trying PCM")
            self.mixer = alsaaudio.Mixer('PCM')
        self.current_vol = self.mixer.getvolume()[0]
        self.load_config()
    
    def load_config(self):
        logger.debug("reloading config file")
        settings = LazySettings(settings_file="settings.toml")
        self.baseURL = settings.default.server_url
        logger.debug("Server URL: "+ self.baseURL)
        self.mountToPlay = settings.default.mounts
    
    def set_mounts(self,mounts):
        self.mountToPlay = mounts

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self,client, userdata, flags, rc):
        logger.info("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("mounts/#")

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self,client, userdata, msg):
        logger.debug(msg.topic+" "+str(msg.payload))
        message = msg.topic.split('/')
        if (message[1] in self.mountToPlay):
            if ("started" in msg.payload.decode()):
                self.playmount(message[1])
                self.livestreams.append(message[1])
            elif "stopped" in msg.payload.decode():
                self.stop()
                if message[1] in self.livestreams: self.livestreams.remove(message[1])

    def playmount(self,mount):
        logger.debug("Playing mount "+mount)
        self.playurl(self.baseURL+mount)
        self.playing = mount

    def playurl(self,url):
        self.stop()
        logger.debug("Starting media player")
        self.process = subprocess.Popen("ffplay -vn -nostats -autoexit "+ url,shell=True)

    def stop(self):
        logger.debug("stopping media player")
        if hasattr(self, 'process'): self.process.kill()

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

def main():
    logger.info("Starting..")
    parser = argparse.ArgumentParser(description='Linux client for Livemasjid.com streams.')
    livemasjid = LivemasjidClient()
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

    #Main
    wm = pyinotify.WatchManager()
    wm.add_watch('settings.toml', pyinotify.IN_MODIFY, livemasjid.load_config())
    notifier = pyinotify.Notifier(wm)
    notifier.loop()
    
"""     while True:
        time.sleep(60)
        logger.debug("reloading config file")
        livemasjid.load_config() """

if __name__ == "__main__":
    main()
