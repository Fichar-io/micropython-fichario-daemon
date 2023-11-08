from machine import Timer, unique_id, Pin, reset
import ubinascii
import time
import network

from ficharioCAL.ficharioMQTTClient2 import Fichario, PayloadPkgMaker, TrgCheck, DeviceInfoPkgMaker, SubscriptionAction

nic = network.WIZNET5K()
nic.active(True)
nic.ifconfig("dhcp")

def foo1(msg=None):
    print("I am foo number 1", msg)
    
def foo2(msg=None):
    print("I am foo number 2", msg)

MOCK_BTN_STATE = 0
def mock_btn():
    global MOCK_BTN_STATE
    if MOCK_BTN_STATE == 1: MOCK_BTN_STATE = 0
    else: MOCK_BTN_STATE = 1
    return MOCK_BTN_STATE

from credentials import *

fichario = Fichario(
    uniqueId = ubinascii.hexlify(unique_id()).decode(),
    username = username,
    passwd   = passwd,
    deviceID = deviceID,
    timerID  = -1,
    server   = "br1.data.fichar.io",
    KeepOn   = True,
    ssl      = True,
    qos      = 0
)

fichario.TIMESTAMP_METHOD = time.time

fichario.add_new_payload(PayloadPkgMaker(name="btn_state",
    callback = mock_btn,
    unit = "unt",
    min = 0,
    max = 1,
    trg = 0
))

fichario.add_subscription_action(SubscriptionAction(
    subtopic = "foo1",
    callback = foo1,
))

fichario.add_subscription_action(SubscriptionAction(
    subtopic = "foo2",
    callback = foo2,
))

fichario.add_subscription_action(SubscriptionAction(
    subtopic = "order66",
    callback = reset,
    trg_msg = "execute",
    pass_rcv_msg = False
))

tim2 = Timer(-1)
def main():
    print("starting main function...")
    fichario.just_do_it() ## First run
    tim2.init(period=60000, mode=Timer.PERIODIC, callback=fichario.just_do_it) ## calls "just do it" periodcaly