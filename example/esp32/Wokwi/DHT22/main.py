from machine import Timer, unique_id, Pin
import ubinascii
import network
import time
import dht
import esp32
import gc

sensor = dht.DHT22(Pin(15))

def get_cpu_temp(): ## degree celsius
    return int((esp32.raw_temperature() - 32) * (5/9) * 10) /10

print("Connecting to WiFi", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')
while not sta_if.isconnected():
  print(".", end="")
  time.sleep(0.1)
print(" Connected!")

import mip

mip.install('https://raw.githubusercontent.com/Fichar-io/micropython-fichario-daemon/development/package.json')
mip.install('ntplib')
gc.collect()

import ntptime
ntptime.settime()

#################################################################
## REMEMBER TO RENAME EXAMPLE.CREDENTIALS.PY TO CREDENTIALS.PY ##
##        AND PROVIDE YOUR OWN FICHAR.IO CREDENTIALS           ##
#################################################################
from credentials import *

from lib.lib.ficharioCAL.ficharioMQTTClient2 import (
    Fichario, 
    PayloadPkgMaker, 
    DeviceInfoPkgMaker, 
    SubscriptionAction
)

fichario = Fichario(
    uniqueId = ubinascii.hexlify(unique_id()).decode(),
    username = username,
    passwd   = passwd,
    deviceID = deviceID,
    timerID  = 1,
    server   = "br1.data.fichar.io",
    KeepOn   = True,
    ssl      = False,
    qos      = 0
)

fichario.TIMESTAMP_METHOD = time.time

fichario.add_new_device_info(DeviceInfoPkgMaker(name="cpu_temp",
    callback = get_cpu_temp
))

fichario.add_new_payload(PayloadPkgMaker(name="humidity", 
    callback = sensor.humidity,
    unit     = "%",
    min      = 0,
    max      = 6,
    trg      = 0,
    max_auto_range = True,
    min_auto_range = True
))

fichario.add_new_payload(PayloadPkgMaker(name="temperature", 
    callback = sensor.temperature,
    unit     = "c",
    min      = 0,
    max      = 6,
    trg      = 0,
    max_auto_range = True,
    min_auto_range = True
))

def do(foo=None):
    sensor.measure()
    fichario.just_do_it()

tim2 = Timer(2)
def main():
    print("starting main function...")
    do() ## First run
    tim2.init(period=60000, mode=Timer.PERIODIC, callback=do) ## calls "just do it" periodcaly