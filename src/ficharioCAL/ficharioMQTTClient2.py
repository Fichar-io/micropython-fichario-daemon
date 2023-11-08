class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

from umqtt.simple import MQTTClient
from .mqttClient import MQTTClient as CustomMQTTClient
import ujson as json
import gc
from machine import Timer, reset
from time import sleep_ms
import time
import uos
import errno

_VERB = True

def VERB(*args, **kargs):
    if _VERB: 
        print(f"{bcolors.HEADER}[{time.time()}]{bcolors.ENDC}", end=" ")
        print(*args, **kargs)

def zfill(s, width):
	return '{:0>{w}}'.format(s, w=width)

## TRG check const
TRG_GT = 0
TRG_GE = 1
TRG_LT = 2
TRG_LE = 3

class DeviceInfoPkgMaker:
    def __init__(self, name, callback, args=[], kwargs={}) -> None:
        self.name     = name
        self.callback = callback
        self.args     = args
        self.kwargs   = kwargs
    
    def make(self):
        return self.callback(*self.args, **self.kwargs)

class TrgCheck:
    def __init__(self, check_method, threshold, if_true, if_false, trg_callback = None, trg_callback_args = [], trg_callback_kwargs = {}) -> None:
        self._check_method = check_method
        self.threshold = threshold
        self.if_true = if_true
        self.if_false = if_false
        self.trg_callback = trg_callback
        self.trg_callback_args = trg_callback_args
        self.trg_callback_kwargs = trg_callback_kwargs
        
        self._callback = [
            self.gt,
            self.ge,
            self.lt,
            self.le
        ]

    def gt(self, value):
        if value > self.threshold:
            if self.trg_callback is not None: self.trg_callback(*self.trg_callback_args, **self.trg_callback_kwargs)
            VERB(f"{bcolors.WARNING}Trigger...{bcolors.ENDC}", end = " ")
            return self.if_true
        else: return self.if_false
    
    def ge(self, value):
        if value >= self.threshold:
            if self.trg_callback is not None: self.trg_callback(*self.trg_callback_args, **self.trg_callback_kwargs)
            VERB(f"{bcolors.WARNING}Trigger...{bcolors.ENDC}", end = " ")
            return self.if_true
        else: return self.if_false
    
    def lt(self, value):
        if value < self.threshold:
            if self.trg_callback is not None: self.trg_callback(*self.trg_callback_args, **self.trg_callback_kwargs)
            VERB(f"{bcolors.WARNING}Trigger...{bcolors.ENDC}", end = " ")
            return self.if_true
        else: return self.if_false
    
    def le(self, value):
        if value <= self.threshold:
            if self.trg_callback is not None: self.trg_callback(*self.trg_callback_args, **self.trg_callback_kwargs)
            VERB(f"{bcolors.WARNING}Trigger...{bcolors.ENDC}", end = " ")
            return self.if_true
        else: return self.if_false
    
    def check(self, value):
        return self._callback[self._check_method]( value = value )

class PayloadPkgMaker:
    def __init__(self, name, callback, unit, min, max, trg, args=[], kwargs={}, min_auto_range = False, max_auto_range = False, trg_check:TrgCheck = None, except_value = 0) -> None:
        self.name     = name
        self.callback = callback
        self.unit     = unit
        self.min      = min
        self.max      = max
        self.trg      = trg
        self.args     = args
        self.kwargs   = kwargs

        self._min_auto_range   = min_auto_range
        self._max_auto_range   = max_auto_range
        self._trg_check_object = trg_check
        
        self.except_value = except_value

    def make(self):
        try:
            val = self.callback(*self.args, **self.kwargs)
        except:
            val = self.except_value
        if self._trg_check_object is not None:
            trg = self._trg_check_object.check(value=val)
        else:
            trg = self.trg
        if (not self._min_auto_range) and (not self._max_auto_range):
            return {
                "val" : val,
                "unt" : self.unit,
                "min" : self.min,
                "max" : self.max,
                "trg" : trg
            }
        else:
            if self._min_auto_range:
                if val < self.min:
                    self.min = val
            if self._max_auto_range:
                if val > self.max:
                    self.max = val
            return {
                "val" : val,
                "unt" : self.unit,
                "min" : self.min,
                "max" : self.max,
                "trg" : trg
            }

class SubscriptionAction:
    def __init__(self, subtopic:str, callback:callable, trg_msg=None, checktime:int=-1, pass_rcv_msg=True) -> None:
        self._subtopic = subtopic
        self._callback = callback
        self._trg_msg = trg_msg
        self._checktime = checktime ## have no idea how to use it... yet
        self._pass_rcv_msg = pass_rcv_msg
        
        self._topic = ""
    
    def _check_for_trg(self, msg):
        if self._trg_msg is not None:
            if self._trg_msg == msg:
                self._do_proceed(msg=msg)
        else: 
            self._do_proceed(msg=msg)

    def _do_proceed(self, msg):
        try:
            if self._pass_rcv_msg: self._callback(msg)
            else: self._callback()
        except Exception as e:
            print(e)

    def proceed_callback(self, msg):
        self._check_for_trg(msg=msg)

class FicharioRemoteDevice:
    def __init__(self, 
            uniqueId, 
            deviceID,
            gateway_uniqueId,
            gateway_deviceID,
            TIMESTAMP_METHOD = None, 
            DEVICE_INFO=[], 
            PAYLOAD=[],
            PREFLIGHT_ROUTINE:callable=None, 
            PREFLIGHT_ROUTINE_ARGS=[], 
            PREFLIGHT_ROUTINE_KWARGS={}
        ) -> None:
        self.uniqueId = uniqueId
        self.deviceID = deviceID
        self.gateway_uniqueId = gateway_uniqueId
        self.gateway_deviceID = gateway_deviceID
        self.TIMESTAMP_METHOD = TIMESTAMP_METHOD
        self.DEVICE_INFO = {}
        self._DEVICE_INFO:list = DEVICE_INFO
        self.PAYLOAD = {}
        self._PAYLOAD:list = PAYLOAD
        self.message = {
            "timestamp": 0,
            "unique_id": "",
            "format": "fichario",
            "dev_info": {
                "flag": "00"
            },
            "payload": {
            },
            "gateway": {
                "unique_id": self.gateway_uniqueId,
                "deviceID": self.gateway_deviceID
            }
        }
        
        self._preflight_routine = PREFLIGHT_ROUTINE
        self._preflight_args = PREFLIGHT_ROUTINE_ARGS
        self._preflight_kwargs = PREFLIGHT_ROUTINE_KWARGS
    
    def add_new_device_info(self, device_info:DeviceInfoPkgMaker):
        self._DEVICE_INFO.append(device_info)

    def add_new_payload(self, payload:PayloadPkgMaker):
        self._PAYLOAD.append(payload)
    
    def update_device_info(self):
        for device_info in self._DEVICE_INFO:
            VERB("calling [", f"{bcolors.OKCYAN}{device_info.name}{bcolors.ENDC}", "]...", end=" ")
            #print("count")
            try:
                self.message["dev_info"][device_info.name] = device_info.make()
                VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}", self.message["dev_info"][device_info.name])
            except Exception as e:
                VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
                VERB(e)
                return (False, device_info.name)

    def update_payload(self):
        for payload in self._PAYLOAD:
            VERB("calling [", f"{bcolors.OKCYAN}{payload.name}{bcolors.ENDC}", "]...", end=" ")
            try:
                self.message["payload"][payload.name] = payload.make()
                VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}", self.message["payload"][payload.name]["val"])
            except Exception as e:
                VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
                VERB(e)
                return (False, payload.name)
    
    def update_timestamp(self):
        try:
            self.message["timestamp"] = self.TIMESTAMP_METHOD()
        except Exception as e:
            VERB(e)
    
    def set_bit(self, bit:int, value:int):
        try:
            flag_bitarray = zfill(bin(int(self.message["dev_info"]["flag"], 16))[2:], 8)
            if value > 0:
                flag_bitarray = flag_bitarray[:7-(bit)] + "1" + flag_bitarray[7-(bit-1):]
            else:
                flag_bitarray = flag_bitarray[:7-(bit)] + "0" + flag_bitarray[7-(bit-1):]
            self.message["dev_info"]["flag"] = zfill(hex(int(flag_bitarray, 2))[2:], 2)
            return True
        except:
            return False
    
    def make_pkg(self):
        if self._preflight_routine is not None:
            try:
                self._preflight_routine(*self._preflight_args, **self._preflight_kwargs)
            except Exception as e:
                print(f"{bcolors.FAIL}Preflight error...{bcolors.ENDC}")
                print(e)

        if callable(self.uniqueId): self.message["unique_id"] = self.uniqueId()
        else: self.message["unique_id"] = self.uniqueId

        try:
            VERB("get timestamp...", end=" ")
            self.update_timestamp()
            VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
        
        try:
            VERB(f"{bcolors.BOLD}make device info!{bcolors.ENDC}")
            self.update_device_info()
        except Exception as e:
            print(e)
        
        try:
            VERB(f"{bcolors.BOLD}make payload!{bcolors.ENDC}")
            self.update_payload()
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
        
        if callable(self.deviceID): _deviceID = self.deviceID()
        else: _deviceID = self.deviceID
        
        return self.message, _deviceID

    def set_preflight_routine(self, callback:callable, args=[], kwargs={}):
        self._preflight_routine = callback
        self._preflight_args = args
        self._preflight_kwargs = kwargs

class Fichario:
    def __init__(self, uniqueId, username, passwd, deviceID, timerID:int, timeout:int = 60, sleep_timeout:int = 100,server=None, KeepOn = True, ssl = False,led = None,qos = 0, mqtt_client_class=CustomMQTTClient) -> None:
        self.led = led
        if self.led is not None:
            self.led(0)
        self.SERVER = "br1.data.fichar.io"
        self.SSL_SERVER = "br1.data.fichar.io"
        if server is not None:
            self.SERVER = server
            self.SSL_SERVER = server
        self.PORT = 1883
        self._ssl = ssl
        self.SSL_PORT = 8883
        self.deviceID = deviceID
        self._TIMEOUT = timeout
        self.USER = username
        self.PASSWORD = passwd
        self.TOPIC = username + '/' + deviceID
        self.CLIENT_ID = uniqueId + '-fichario_0.1.0'
        self._SUBSCRIBE_FLAG = False
        self._SLEEPTIMEOUT = sleep_timeout
        self.qos_value = qos
        self._IDLE_COUNT = 0
        self._RECONNECT_ATEMPT_COUNT = 0
        self._MQTT_SOCK_TIMEOUT = 3
        
        self.RECONNECT_MAX_ATEMPTS = 100

        self.TIMESTAMP_METHOD = None
        self.DEVICE_INFO = {}
        self._DEVICE_INFO = []
        self.PAYLOAD = {}
        self._PAYLOAD = []
        self.message = {
            "timestamp": 0,
            "unique_id": uniqueId,
            "format": "fichario",
            "dev_info": {
                #"wall_voltage" : round(12.0 + random() - 0.5, 2),
                #"pw_voltage": round(5.0 + random() - 0.5, 2),
                #"bat_voltage": round(4.5 + random() - 0.5, 2),
                #"cpu_temp": 0,
                #"pw_status": "CHARGING",
                #"cpu_usage": 0,
                #"men_usage": 0,
                #"uptime": 0,
                #"latitude": -21.751528,
                #"longitute": -41.351329,
                #"orientation": 126.56,
                #"altitude": 2.6,
                #"timezone": -3,
                #"ip": "192.168.100.106",
                #"subcribed": "<USER>/<DEV_KEY>/bolinha/amarelinha",
                "flag": "00"
            },
            "payload": {
                #"val_A": {
                #    "val": 0,
                #    "unt": 0,
                #    "min": 0,
                #    "max": 0,
                #    "trg": 0,
                #},
                #"val_B": {
                #    "val": 0,
                #    "unt": 0,
                #    "min": 0,
                #    "max": 0,
                #    "trg": 0,
                #},
            }
        }

        self._BUFFER = [] ## format [message, topic]
        self._TIMER = Timer(timerID)

        self._CONSUMING_BUFFER_FLAG = False
        self._TRYING_CONNECT_FLAG = False
        self._TRYING_PUB_FLAG = False
        self._PREVENT_REBOOT_FLAG = False
        
        self.MQTT_CONNECTION_STATE = False
        self.KEEPON = KeepOn
        self.busy = False ## other sections of the emb code must check for this flag and prevent certain actions Ex. reboot MCU
        
        self.CURRENT_STATE = "STOPPED"
        self._STATE_CALLBACK = {
            "IDLEING" : self._idle_loop,
            "RECONNECTING" : self._reconnect_loop,
            "CONSUMING BUFFER" : self._buffer_consumer_loop
        }
        
        self._look_for_backup()
        
        self.mqtt_client_class = mqtt_client_class
        
        self._remote_device = {}
        
        self._subscription_actions = {}

    ##################################################################
    
    def _look_for_backup(self):
        VERB("looking for backup...", end=" ")
        try:
            with open("message.backup", "r") as backup_file:
                raw_backup_data = backup_file.readlines()
                backup_file.close()
            self._BUFFER = []
            for line in raw_backup_data:
                msg , topic = line.split(";")
                self._BUFFER.append([msg, topic[:-1]])
            if self.get_buffer_len() > 0:
                VERB(self.get_buffer_len(), "message(s) in backup wainting to be sent!")
            else:
                VERB("no message retrieved!")
            uos.remove("message.backup")
        except OSError as exc:
            if exc.errno == errno.ENOENT: VERB("No backup found!")
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
            self._BUFFER = []
        finally:
            return

    def _stop_all_loop(self):
        VERB("stopping all loops!")
        self._TIMER.deinit()
        self.CURRENT_STATE = "STOPPED"
        return

    ## idle loop to keep connection alive
    def _start_idle_loop(self):
        if self.KEEPON: 
            self._TIMER.init(period = 1000, mode = Timer.PERIODIC, callback = self._idle_loop) # idle each one second
            self.CURRENT_STATE = "IDLEING"
        else: 
            self.disconnect()
        return
    
    def _idle_loop(self, timerID):
        VERB("idle...", end=" ")
        if not self.MQTT_CONNECTION_STATE:
            if self.KEEPON:
                VERB("try to idle but is not connected!")
                self._start_reconnect_loop()
            return
        if (self._IDLE_COUNT + 2000) >= (self._TIMEOUT*1000): ## ping to server 2 seconds before timeout
            try:
                VERB("ping...", end=" ")
                self.broker.ping() ## raise error if fails for some reason
                VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
            except Exception as e:
                VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
                print(e)
                self.MQTT_CONNECTION_STATE = False
                self._turn_led_off()
                self._start_reconnect_loop()
            finally:
                self.broker.check_msg()
                self._IDLE_COUNT = 0
                return
        else:
            VERB("!") ## just to break line
            self._IDLE_COUNT = self._IDLE_COUNT + 1000
            self.broker.check_msg()
            return
    
    ## keep trying to reconnect
    def _start_reconnect_loop(self):
        self._TIMER.init(period = 10000, mode = Timer.PERIODIC, callback = self._reconnect_loop)
        self.CURRENT_STATE = "RECONNECTING"
        return
    
    def _reconnect_loop(self, timerID):
        VERB("reconnection attempt...", end=" ")
        if self.MQTT_CONNECTION_STATE: ## fo some reason this function was called with mqtt alredy connect. Just go to idle state
            VERB("trying to reconnect but alredy connected!")
            self._RECONNECT_ATEMPT_COUNT = 0
            if self.get_buffer_len == 0:
                self._start_idle_loop()
            else:
                self._start_buffer_consumer_loop()
            return
        if self._TRYING_CONNECT_FLAG: ## do nothing if alredy trying to reconnect
            VERB("attempt already in progress!")
            return
        else:
            if self._RECONNECT_ATEMPT_COUNT >= self.RECONNECT_MAX_ATEMPTS: self._backup_and_reset() ## TODO: find a better way to fix this "OSError: 23" bug
            self._RECONNECT_ATEMPT_COUNT += 1
            self._TIMER.deinit()
            self.connect()
            self._TIMER.init(period = 10000, mode = Timer.PERIODIC, callback = self._reconnect_loop)
            return
            
    ## the is values in buffer, consume untin buffer len is zero
    def _start_buffer_consumer_loop(self):
        VERB("starting buffer consumer!")
        self._TIMER.init(period = 1000, mode = Timer.PERIODIC, callback = self._buffer_consumer_loop)
        self.CURRENT_STATE = "CONSUMING BUFFER"
        return
    
    def _buffer_consumer_loop(self, timerID):
        if self.MQTT_CONNECTION_STATE:
            if self.get_buffer_len() == 0:
                VERB("empty buffer!")
                self._start_idle_loop()
                return
            else:
                # self._TIMER.deinit()
                if self._publish(self._BUFFER[0][0],self._BUFFER[0][1]):
                    del self._BUFFER[0]
                    gc.collect()
                    if self.get_buffer_len() == 0:
                        VERB("empty buffer!")
                        self._start_idle_loop()
                    return
                # else:
                #     self._TIMER.init(period = 1000, mode = Timer.PERIODIC, callback = self._buffer_consumer_loop)
                #     return
        else:
            VERB("mqtt not connected!")
            self._RECONNECT_ATEMPT_COUNT += 1
            self.connect()
            self._start_reconnect_loop()
            return
    
    def _backup_and_reset(self):
        try:
            VERB("making buffer backup...", end=" ")
            with open("message.backup", "w") as backup_file:
                for line in self._BUFFER:
                    backup_file.write(line[0] + ";" + line[1] + "\n")
            VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
        if not self._PREVENT_REBOOT_FLAG:
            VERB("Rebooting!")
            reset()
        else:
            VERB("Reboot prevented!")
            self._stop_all_loop()
    
    ##################################################################
    
    def _publish(self, msg, topic=None):
        if topic is None: topic = self.TOPIC
        if self.MQTT_CONNECTION_STATE:
            try:
                VERB("publishing data... TOPIC:", f"{bcolors.OKCYAN}{topic}{bcolors.ENDC}", end=" ")
                sleep_ms(self._SLEEPTIMEOUT)
                self.broker.publish(topic, msg, qos = self.qos_value)
                self._IDLE_COUNT = 0
                VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
                return True
            except Exception as e:
                VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
                print(e)
                self.MQTT_CONNECTION_STATE = False
                self._turn_led_off()
                self._start_reconnect_loop()
                return False
    
    def _stack_if_fits(self, msg, topic=None):
        VERB("saving msg in buffer...", end=" ")
        if topic is None: topic = self.TOPIC
        data = [msg , topic]
        if(gc.mem_free() >= 2000):
            self._BUFFER.append(data)
            VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
            self._start_buffer_consumer_loop()
            return
        else:
            print('not enougth memory available... overwriting data!', gc.mem_free())
            if self.get_buffer_len() == 0: 
                print("buffer error!")
                self.disconnect()
                return
            del self._BUFFER[0]
            gc.collect()
            self._stack_if_fits(msg, topic)
            self._start_buffer_consumer_loop()
            return
    
    def _turn_led_on(self):
        if self.led is not None: self.led(1)
    
    def _turn_led_off(self):
        if self.led is not None: self.led(0)
    
    def _check_for_subscription_action(self, topic, msg):
        #print(topic, msg)
        subscription_action = self._subscription_actions.get(topic.decode(), None)
        if subscription_action is not None:
            subscription_action.proceed_callback(msg.decode())

    ##################################################################
    
    def connect(self):
        if self._ssl:
            print ('connecting to', self.SERVER, 'MQTT server with SSL ...')
            ssl_params = {"server_hostname": self.SSL_SERVER}
            self.broker = self.mqtt_client_class(self.CLIENT_ID, self.SSL_SERVER, self.SSL_PORT, self.USER, self.PASSWORD, self._TIMEOUT, ssl=self._ssl, ssl_params=ssl_params)
        else:
            print ('connecting to', self.SERVER, 'MQTT server...')
            self.broker = self.mqtt_client_class(self.CLIENT_ID, self.SERVER, self.PORT, self.USER, self.PASSWORD, self._TIMEOUT)
        
        self.broker.set_callback(self._check_for_subscription_action)
        
        try:
            VERB("trying to connect...", end=" ")
            self._TRYING_CONNECT_FLAG = True
            self.broker.connect() ## raise an error if it fails for some reason
            self._TRYING_CONNECT_FLAG = False
            print("Connected!")
            self.MQTT_CONNECTION_STATE = True
            self._RECONNECT_ATEMPT_COUNT = 0
            self._turn_led_on()
            
            if len(self._subscription_actions) > 0:
                self.broker.subscribe(self.TOPIC + "/#")
            
            if self.get_buffer_len() > 0: self._start_buffer_consumer_loop()
            else: self._start_idle_loop()
            
            return True
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
            self._TRYING_CONNECT_FLAG = False
            self.MQTT_CONNECTION_STATE = False
            self._turn_led_off()
            return False
    
    def publish(self, msg, topic=None): ## blind publish 
        try:
            self.broker.publish(topic, msg, qos = self.qos_value)
            return True
        except:
            return False
            
    # def subscribe(self, TOPIC, CALLBACK):
    #     pass
    
    # def check_for_msg(self):
    #     pass
    
    def disconnect(self):
        self._stop_all_loop()
        try:
            VERB("trying to disconnect...", end=" ")
            self.broker.disconnect()
            VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
        except:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
        finally:
            self.busy = False
            return
    
    def pubish_or_stack(self, msg, topic=None):
        if topic is None: topic = self.TOPIC
        
        if not isinstance(msg, str): msg_str = json.dumps(msg)
        else: msg_str = msg
        
        if self.get_buffer_len() > 0:
            self._stack_if_fits(msg_str, topic)
        elif self.MQTT_CONNECTION_STATE:
            if self._publish(msg_str, topic):
                if not self.KEEPON: self.disconnect()
                else: self._start_idle_loop()
            else:
                self._stack_if_fits(msg_str, topic)
        else:
            VERB("trying publish but not connected!")
            self._stack_if_fits(msg_str, topic)
        return
    
    def add_new_device_info(self, device_info:DeviceInfoPkgMaker):
        self._DEVICE_INFO.append(device_info)

    def add_new_payload(self, payload:PayloadPkgMaker):
        self._PAYLOAD.append(payload)

    def add_subscription_action(self, subaction:SubscriptionAction):
        subaction._topic = self.TOPIC + "/" + subaction._subtopic
        self._subscription_actions[subaction._topic] = subaction

    ##################################################################
    def get_buffer_len(self):
        return len(self._BUFFER)

    def update_device_info(self):
        for device_info in self._DEVICE_INFO:
            VERB("calling [", f"{bcolors.OKCYAN}{device_info.name}{bcolors.ENDC}", "]...", end=" ")
            #print("count")
            try:
                self.message["dev_info"][device_info.name] = device_info.make()
                VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}", self.message["dev_info"][device_info.name])
            except Exception as e:
                VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
                VERB(e)
                return (False, device_info.name)

    def update_payload(self):
        for payload in self._PAYLOAD:
            VERB("calling [", f"{bcolors.OKCYAN}{payload.name}{bcolors.ENDC}", "]...", end=" ")
            try:
                self.message["payload"][payload.name] = payload.make()
                VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}", self.message["payload"][payload.name]["val"])
            except Exception as e:
                VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
                VERB(e)
                return (False, payload.name)
    
    def update_timestamp(self):
        try:
            self.message["timestamp"] = self.TIMESTAMP_METHOD()
        except Exception as e:
            VERB(e)
    
    def set_bit(self, bit:int, value:int):
        try:
            flag_bitarray = zfill(bin(int(self.message["dev_info"]["flag"], 16))[2:], 8)
            if value > 0:
                flag_bitarray = flag_bitarray[:7-(bit)] + "1" + flag_bitarray[7-(bit-1):]
            else:
                flag_bitarray = flag_bitarray[:7-(bit)] + "0" + flag_bitarray[7-(bit-1):]
            self.message["dev_info"]["flag"] = zfill(hex(int(flag_bitarray, 2))[2:], 2)
            return True
        except:
            return False

    def just_update(self, src=None):
        VERB(f"{bcolors.OKBLUE}## Local attributes ##{bcolors.ENDC}")
        try:
            VERB("get timestamp...", end=" ")
            self.update_timestamp()
            VERB(f"{bcolors.OKGREEN}ok!{bcolors.ENDC}")
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
        
        try:
            VERB(f"{bcolors.BOLD}make device info!{bcolors.ENDC}")
            self.update_device_info()
        except Exception as e:
            print(e)
        
        try:
            VERB(f"{bcolors.BOLD}make payload!{bcolors.ENDC}")
            self.update_payload()
        except Exception as e:
            VERB(f"{bcolors.FAIL}fail!{bcolors.ENDC}")
            print(e)
        
        try:
            if len(self._remote_device) > 0:
                VERB(f"{bcolors.OKBLUE}## Remote Device attributes ##{bcolors.ENDC}")
                for remote_device in self._remote_device:
                    VERB(f"{bcolors.OKBLUE}## Remote Device: {remote_device} ##{bcolors.ENDC}")
                    if isinstance(self._remote_device[remote_device], FicharioRemoteDevice):
                        pkg, deviceId = self._remote_device[remote_device].make_pkg()
        except Exception as e:
            print(e)
    
    def just_do_it(self, timerId = None, topic = None):
        self._TIMER.deinit()
        self.busy = True
        if topic is None: topic = self.TOPIC
        
        self.just_update()
        
        self.pubish_or_stack(self.message, topic)
        
        if len(self._remote_device) > 0:
            for remote_device in self._remote_device:
                if isinstance(self._remote_device[remote_device], FicharioRemoteDevice):
                    _msg = self._remote_device[remote_device].message
                    if callable(self._remote_device[remote_device].deviceID):_deviceid = self._remote_device[remote_device].deviceID()
                    else: _deviceid = self._remote_device[remote_device].deviceID

                    if len(_deviceid) < 24: print(f"{bcolors.FAIL}deviceID too small..., skipping message{bcolors.ENDC}")
                    else: self.pubish_or_stack(_msg, self.USER + '/' + _deviceid)

    ##################################################################

    def add_remote_device(self, name,  remote_device:FicharioRemoteDevice):
        self._remote_device[name] = remote_device