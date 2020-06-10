#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Hass.io Add-on Chirp I2C moisture sensor bridge to MQTT.

Chirp Sensor
https://github.com/Miceuz/i2c-moisture-sensor

This polls i2c at regular intervals (default 10 min) and publishes JSON
updates to MQTT.

Example mesage to topic chirp/c01
{
    "temp": 20.2,
    "moist_percent": 76.6,
    "moist_cond": 494
}

Author: falkn@brannered.com
"""

import json
import logging
import sys
import time
from urllib.parse import urlparse

from paho.mqtt import client as mqtt

# Allow depend on chirp.py in another directory.
sys.path.insert(1, 'chirp-rpi')
import chirp

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

MQTT_JSON_TEMPLATE = (
  '{{'
  '  "temp": {:3.1f}, '
  '  "moist_percent": {:4.1f}, '
  '  "moist_cond": {:3.0f}'
  '}}'
)


def init_logger_stdout():
  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.INFO)
  formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  LOG.addHandler(handler)


def init_chirp(options_json):
  moist_min = options_json.get('moist_min', 222)
  moist_max = options_json.get('moist_max', 577)
  if moist_min >= moist_max:
    LOG.fatal('Incorrect options: moist_min (%s) < moist_max (%s)',
              moist_min, moist_max)
    sys.exit(1)
  return chirp.Chirp(address=options_json.get('i2c_addr', 0x20),
                     read_moist=True,
                     read_temp=True,
                     read_light=False,
                     min_moist=moist_min,
                     max_moist=moist_max,
                     temp_scale='celsius',
                     temp_offset=options_json.get('temp_offset', 0))


def init_mqtt_client(options_json):
  mqtt_client = mqtt.Client()
  mqtt_client.username_pw_set(
    options_json.get('mqtt_username', 'mqtt'),
    options_json.get('mqtt_password', ''))

  mqtt_address = options_json.get('mqtt_address', 'mqtt://homeassistant')
  mqtt_url = urlparse(mqtt_address)
  if mqtt_url.scheme != 'mqtt':
    LOG.fatal(
      'Incorrect option mqtt_address, expecting mqtt protocol, got %s. '
      'Example: "mqtt://homeassistant"', mqtt_url.scheme)
    sys.exit(1)

  mqtt_client.connect(mqtt_url.hostname, mqtt_url.port or 1883)
  return mqtt_client


def read_now_ms():
  return int(time.time() * 1000)


def poll_chirp(chrp, mqtt_client, mqtt_topic):
  chrp.trigger()
  mqtt_json = MQTT_JSON_TEMPLATE.format(
    chrp.temp, chrp.moist_percent, chrp.moist)

  mqtt_client.publish(mqtt_topic, mqtt_json)
  LOG.info('Published topic %s message %s', mqtt_topic, mqtt_json)


def main():
  init_logger_stdout()
  LOG.info('Chirp2mqtt starting...')

  LOG.info('Reading options.json')
  with open('/data/options.json') as options_file:
    options_json = json.load(options_file)

  # Initialize the sensor.
  LOG.info('Init Chirp I2C sensor')
  chrp = init_chirp(options_json)

  LOG.info('Init MQTT client')
  mqtt_client = init_mqtt_client(options_json)
  mqtt_topic = options_json.get('mqtt_topic', 'chirp/c01')

  now_ms = read_now_ms()
  next_reading_ms = now_ms
  read_period_ms = options_json.get('read_period_sec', 600) * 1000

  LOG.info('Start polling')

  try:
    while True:
      now_ms = read_now_ms()
      if now_ms > next_reading_ms:
        next_reading_ms = max(now_ms, next_reading_ms + read_period_ms)
        poll_chirp(chrp, mqtt_client, mqtt_topic)

      mqtt_client.loop()
      time.sleep(1)
  finally:
    mqtt_client.disconnect()


if __name__ == "__main__":
  main()
