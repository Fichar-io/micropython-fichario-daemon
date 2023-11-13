# Fichario MQTT Client Library

## Overview

The Fichario MQTT Client Library is a MicroPython library that allows you to easily set up an MQTT sending messages service to Fichar.io MQTT broker. It simplifies the process of connecting to an MQTT broker, managing payloads, and publishing messages.

This is NOT an Async client. This service uses Timer capabilities to manage publishing retries once a publish fails.

This README provides an example of how to use the `Fichario` class to set up an MQTT client for sending data to an MQTT broker.

## Prerequisites

Before using the Fichario MQTT Client Library, make sure you have the Fichar.io credentials:

MQTT broker settings:
   - MQTT broker server address
   - MQTT username and password
   - Device ID

## Instalation

```python
# For micropython v1.20.0 or newer
import mip
mip.install('https://raw.githubusercontent.com/Fichar-io/micropython-fichario-daemon/main/package.json')
```

## Instalation From Source

```python
# For micropython v1.20.0 or newer
import mip
mip.install('https://raw.githubusercontent.com/Fichar-io/micropython-fichario-daemon/main/src/ficharioCAL/package.json')
```

## Example Usage

```python
# Import necessary modules
from Fichario import Fichario, PayloadPkgMaker, FicharioRemoteDevice, SubscriptionAction

# Define your MQTT broker settings
uniqueId = "your_unique_id"
username = "your_username"
passwd = "your_password"
deviceID = "your_device_id"

# Create an instance of the Fichario class
fichario = Fichario(
    uniqueId=uniqueId,
    username=username,
    passwd=passwd,
    deviceID=deviceID,
    timerID=0,  # Replace with your desired Timer ID
    timeout=60,  # Adjust the timeout as needed
    server="your_mqtt_server",  # Replace with your MQTT broker server
    KeepOn=True,  # Set to True to keep the connection alive
    ssl=False,  # Set to True if your broker uses SSL
    qos=0  # Adjust the Quality of Service as needed
)

# Define a timestamp method (replace with your actual timestamp function)
def get_timestamp():
    # Implement your timestamp retrieval logic here
    return 0  # Replace with the actual timestamp value

# Set the timestamp method for the Fichario instance
fichario.TIMESTAMP_METHOD = get_timestamp

# Create and add a PayloadPkgMaker instance for sending a payload
fichario.add_new_payload(PayloadPkgMaker(name="your_payload_name",
    callback=lambda: 42,  # Replace with your data retrieval logic
    unit="unit",
    min=0,
    max=100,
    trg=1
))

# Create and add new SubscriptionAction instance for subscribing a topic
fichario.add_subscription_action(SubscriptionAction(
    subtopic = "foo",
    callback = foo,
    trg_msg = "100",
    pass_rcv_msg = False
))

# Connect to the MQTT broker
mqtt_client.connect()

# Publish a message (this will trigger the update of device info and payload)
mqtt_client.just_do_it()

# Optionally, you can add more payloads, remote devices, and publish additional messages.

# When you're done, disconnect from the MQTT broker
mqtt_client.disconnect()
```

In this example, we set up an MQTT client using the `Fichario` class, define MQTT broker settings, create payload data, and publish a message to the MQTT broker. You can customize this example to meet your specific requirements.

## Documentation

For detailed documentation and more information on the `Fichario` class and its methods, refer to the official [Fichario documentation](https://fichar.io/documentation#/MQTTBroker).