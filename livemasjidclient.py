# -*- coding: utf-8 -*-
#from gluon import *
import vlc
import paho.mqtt.client as mqtt
import sys
import time
import argparse
import json

with open('/opt/livemasjid/eBilal/config.json', 'r') as f:
        config = json.load(f)
        server_url = config['DEFAULT']['SERVER_URL'] 
        mounts = config['DEFAULT']['MOUNTS']

class LivemasjidClient:
    """User Object"""
    def __init__(self, mountToPlay, config_url):
        self.mountToPlay = mountToPlay
        self.Instance = vlc.Instance()
        self.player = self.Instance.media_player_new()
        self.client = mqtt.Client()
        self.baseURL = config_url

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self,client, userdata, flags, rc):
        print("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("mounts/#")

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self,client, userdata, msg):
        print(msg.topic+" "+str(msg.payload))
        message = msg.topic.split('/')
        if ((message[1] in self.mountToPlay) and (len(message)>2)):
            if ("start" in message[2]):
                self.playmount(message[1])
            elif "stop" in message[2]:
                self.stop()
    def playmount(self,mount):
        self.playurl(self.baseURL+mount)

    def playurl(self,url):
        Media = self.Instance.media_new(url)
        Media.get_mrl()
        self.player.set_media(Media)
        self.player.play()

    def stop(self):
        self.player.stop()

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
        #client.loop_forever()

    def disconnect(self):
        self.client.loop_stop()


def main():
    parser = argparse.ArgumentParser(description='Linux client for Livemasjid.com streams.')
    #parser.add_argument('-m', '--mount', dest='mount')
    #args = parser.parse_args()
    #mount = args.mount
    #if mount == None: mount="activestream" 
    livemasjid = LivemasjidClient(mounts,server_url)
    livemasjid.connect()
    #livemasjid.tunein(mount,start=True)
    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
