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


logger = logging.getLogger()

def load_config():
    with open('/opt/ebilal/config.json', 'r') as f:
            config = json.load(f)
            logging.config.dictConfig(config)
            server_url = config['DEFAULT']['SERVER_URL'] 
            mounts = config['DEFAULT']['MOUNTS']
    return mounts,server_url

class LivemasjidClient:
    """User Object"""
    def __init__(self, mountToPlay, config_url):
        self.mountToPlay = mountToPlay
        self.client = mqtt.Client()
        self.baseURL = config_url
        self.livestreams = []
        self.playing = None
        self.mixer = alsaaudio.Mixer()
        self.current_vol = self.mixer.getvolume()[0]
    
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
    mounts = ["activestream"]
    load_config()
    mounts,server_url = load_config()
    if len(sys.argv) > 1:
        mounts = sys.argv[1].split(',')
    logger.info("Starting..")
    logger.info("Listeng to "+mounts[0])
    parser = argparse.ArgumentParser(description='Linux client for Livemasjid.com streams.')
    livemasjid = LivemasjidClient(mounts,server_url)
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
    
    #Main loop
    while True:
        time.sleep(60)
        logger.debug("reloading config file")
        load_config()
        livemasjid.set_mounts(mounts)

if __name__ == "__main__":
    main()
