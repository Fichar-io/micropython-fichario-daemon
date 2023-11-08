from machine import Timer, unique_id, Pin
import ubinascii
import time
import network

from ficharioCAL.ficharioMQTTClient2 import Fichario, PayloadPkgMaker, TrgCheck, DeviceInfoPkgMaker

nic = network.WIZNET5K()
nic.active(True)
nic.ifconfig("dhcp")

# Define your Fichar.io credentials
username = "<USERNAME>"
passwd = "<PASSWORD>"
deviceID = "<DEVICEID>"

fichario = Fichario(
    uniqueId = ubinascii.hexlify(unique_id()).decode(),
    username = username,
    passwd   = passwd,
    deviceID = deviceID,
    timerID  = 1,
    server   = "br1.data.fichar.io",
    KeepOn   = True,
    ssl      = True,
    qos      = 0
)

fichario.TIMESTAMP_METHOD = time.time

