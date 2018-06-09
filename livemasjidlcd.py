#!/usr/bin/env python
# -*- coding: utf-8 -*-
#from gluon import *
import time
import Adafruit_CharLCD as LCD
import urllib, json
import re
import subprocess
import os
import schedule
from livemasjidclient import LivemasjidClient
import threading

class livemasjidlcd():
    """User Object"""
    def __init__(self):
        # Initialize the LCD using the pins
        self.lcd = LCD.Adafruit_CharLCDPlate()
        self.currentMount=0
        self.url = "http://livemasjid.com/api/get_mountdetail.php"
        self.mountList = []
        self.livemasjid = LivemasjidClient()
                # create some custom characters
        self.lcd.create_char(1, [31, 31, 31, 31, 31, 31, 31, 31]) #Full block symbol
        self.lcd.create_char(2, [0, 4, 10, 17, 4, 10, 0, 4]) #WiFi Symbol
        self.lcd.create_char(3, [4, 6, 21, 14, 14, 21, 6, 4]) #BlueTooth Symbol
        self.lcd.create_char(4, [31, 17, 10, 4, 10, 17, 31, 0])

        # Show some basic colors.
        self.lcd.set_color(0.0, 0.0, 0.0)
        self.lcd.clear()
        self.lcd.message('Loading...')

        # Make list of button value, text, and backlight color.
        self.buttons = ( (LCD.SELECT, 'Select', (1,1,1)),
                    (LCD.LEFT,   'Left'  , (1,0,0)),
                    (LCD.UP,     'Up'    , (0,0,1)),
                    (LCD.DOWN,   'Down'  , (0,1,0)),
                    (LCD.RIGHT,  'Right' , (1,0,1)) )

        self.menu0 = "LiveMasjid.com"
        self.line1 = self.menu0
        self.line2 = ""


    def getWiFiStatus(self):
        proc = subprocess.Popen(["iwconfig"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        (out, err) = proc.communicate()
        wifi = out
        AP = ''
        matchObj = re.match( r'.*?ESSID:"(.*?)".*', wifi, re.M|re.I)
        if matchObj:
           #print "matchObj.group() : ", matchObj.group()
           #print "matchObj.group(1) : ", matchObj.group(1)
           AP = matchObj.group(1)
        else:
           #print "No match!!"
           AP = 'WiFi Disconnected'
        line1 = "\x02 " + "WiFi"
        line2 = AP
        lcd.clear();
        lcd.message(line1+'\n'+line2)
        return AP

    def getBluetoothStatus(self):
        BT = ''
        BT = "No Speaker"
        line1 = "\x03 " + "Bluetooth"
        line2 = BT
        lcd.clear();
        lcd.message(line1+'\n'+line2)
        return BT
    
    def getMounts(self):
        response = urllib.urlopen(self.url)
        data = json.loads(response.read())
        for mount in data['mounts']:
            self.mountList.append(mount['mount-name'][1:])
        return self.mountList

    def run(self):
        self.lcd.clear()
        self.line1 = "Loading..."
        self.line2 = "Channels"
        self.lcd.message(self.line1+'\n'+self.line2)
        #schedule.every(10).seconds.do(self.getWiFiStatus)
        #schedule.every(15).seconds.do(self.getBluetoothStatus)

        #Initialize MQTT Client
        self.livemasjid.connect()
        self.lcd.clear()
        self.line1 = self.menu0
        self.line2 = ""
        self.lcd.message(self.line1+'\n'+self.line2)
        while True:
            #schedule.run_pending()
            if self.lcd.is_pressed(LCD.RIGHT):
                self.line1 = "Volume:"
                self.line2 = self.line2 + "\x01"
                self.lcd.clear()
                self.lcd.message(self.line1+'\n'+self.line2)
                time.sleep(0.1)
            if self.lcd.is_pressed(LCD.LEFT):
                self.line1 = "Volume:"
                self.line2 = self.line2[:-1]
                self.lcd.clear()
                self.lcd.message(self.line1+'\n'+self.line2)
                time.sleep(0.1)
            if self.lcd.is_pressed(LCD.UP):
                self.currentMount = self.currentMount + 1
                self.line1 = format(self.currentMount, '02d') + " " +  self.mountList[self.currentMount]
                self.lcd.clear()
                self.lcd.message(self.line1+'\n'+self.line2)
                self.livemasjid.tunein(self.mountList[self.currentMount])
                time.sleep(0.1)
            if self.lcd.is_pressed(LCD.DOWN):
                self.currentMount = self.currentMount - 1
                self.line1 = format(self.currentMount, '02d') + " " +  self.mountList[self.currentMount]
                self.lcd.clear()
                self.lcd.message(self.line1+'\n'+self.line2)
                self.livemasjid.tunein(self.mountList[self.currentMount])
                time.sleep(0.1)
            if self.lcd.is_pressed(LCD.SELECT):
                #Play selected channel
                self.livemasjid.playmount(self.currentMount)

def main():
    livelcd=livemasjidlcd()
    thread = threading.Thread(target=livelcd.run(), daemon=True)
    thread.start()

if __name__ == "__main__":
    main()
