from machine import Timer, unique_id
import ubinascii
import time
import esp32
import network

from ficharioMQTTClient2 import Fichario, PayloadPkgMaker, TrgCheck, DeviceInfoPkgMaker

## custom methods ##
def get_cpu_temp(self): ## degree celsius
    return int((esp32.raw_temperature() - 32) * (5/9) * 10) /10

## configure wifi ##
WIFI_SSID = '<ssid>'
WIFI_PASSWORD = '<password>'

def do_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        timeout = 10
        count = 0
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)
            if count > timeout: break
            count += 1
    print('network config:', wlan.ifconfig())

# Define your Fichar.io credentials
username = "your_username"
passwd = "your_password"
deviceID = "your_device_id"

fichario = Fichario(
    uniqueId = ubinascii.hexlify(unique_id()).decode(),
    username = username,
    passwd   = passwd,
    deviceID = deviceID,
    timerID  = 1,
    server   = "br1.data.fichar.io",
    KeepOn   = True,
    ssl      = True,
    #led      = ,
    qos      = 0
)

fichario.TIMESTAMP_METHOD = time.time

fichario.add_new_device_info(DeviceInfoPkgMaker(
    name     = "cpu_temp",
    callback = get_cpu_temp
))

fichario.add_new_payload(PayloadPkgMaker(name = "hall", 
    callback = esp32.hall_sensor,
    unit     = "unt",
    min      = 0,
    max      = 6,
    trg      = 0,
    max_auto_range = True,
    min_auto_range = True
))

tim2 = Timer(2)
def main():
    do_connect()
    print("starting main function...")
    fichario.just_do_it() ## First run
    tim2.init(period=60000, mode=Timer.PERIODIC, callback=fichario.just_do_it) ## calls "just do it" periodcaly