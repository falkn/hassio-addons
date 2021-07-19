#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Hass.io Add-on EP-Solar MPPT Tracer MT-5 to MQTT bridge.

This will read a UART serial port connected to a solar charger from EP-Solar,
and pass the values to mqtt.

Author: Christian Falk <falkn@brannered.com>
"""

import json
import logging
import sys
import serial
import time
from urllib.parse import urlparse

from paho.mqtt import client as mqtt

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

SERIAL_TIMEOUT = 100.0  # seconds?
RECONNECT_TIMEOUT_S = 30.0  # seconds
SYNC_HEADER = bytes([0xEB, 0x90, 0xEB, 0x90, 0xEB, 0x90])
QUERY_COMMAND = bytes([0x16, 0xA0, 0x00, 0x00, 0x00, 0x7F])

MAX_READ_LENGTH = 1024


def init_logger_stdout():
  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.INFO)
  formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  LOG.addHandler(handler)


def init_mqtt_client(options_json):
  mqtt_client = mqtt.Client()
  mqtt_client.username_pw_set(
    options_json.get('mqtt_username', 'mqtt'),
    options_json.get('mqtt_password', ''))

  mqtt_address = options_json.get('mqtt_address', 'mqtt://homeassistant.local')
  LOG.info('Parsing MQTT URL %s', mqtt_address)

  mqtt_url = urlparse(mqtt_address)
  if mqtt_url.scheme != 'mqtt':
    LOG.fatal(
      'Incorrect option mqtt_address, expecting mqtt protocol, got %s. '
      'Example: "mqtt://homeassistant"', mqtt_url.scheme)
    sys.exit(1)

  LOG.info('Connecting to MQTT %s', mqtt_address)

  mqtt_client.connect(mqtt_url.hostname, mqtt_url.port or 1883)

  LOG.info('Connected to MQTT %s', mqtt_address)

  return mqtt_client


def create_serial_client(options_json):
  return serial.Serial(
      options_json.get('serial_port', '/dev/ttyUSB0'),
      options_json.get('serial_baud', 9600),
      timeout=SERIAL_TIMEOUT,
      write_timeout=SERIAL_TIMEOUT)


def init_serial_client(options_json):
  try:
    return create_serial_client(options_json)
  except ValueError as ve:
    LOG.fatal(
      'Could not initiate serial port, is baud rate not supported? Try to set '
      '"serial_baud" option, currently set to: %s. Exception: %s',
      options_json.get('serial_baud', None), str(ve))
    sys.exit(1)
  except serial.SerialException as se:
    LOG.fatal(
      'Could not initiate serial port, is port incorrect or not accessible? '
      'Try to set "serial_port" option, currently set to: %s. Make sure this '
      'port is enabled. Exception: %s',
      options_json.get('serial_port', None), str(se))
    sys.exit(1)


def reconnect_serial_client(serial_client):
  while not serial_client.is_open:
    try:
      serial_client.open()
    except serial.SerialException as se:
      LOG.info('Reconnection attempt failed, waiting %d s: %s',
               RECONNECT_TIMEOUT_S, str(se))
      time.sleep(RECONNECT_TIMEOUT_S)
      continue
  LOG.info('Reconnection to serial successful!')


class TracerMsg(object):

  def __init__(self):
    # Header
    self.controller_id = None
    self.command = None
    self.data_length = None
    self.crc = None

    # Data

  def __str__(self):
    return 'TrackerMsg%s' % self.to_json()

  def to_json(self):
    return json.dumps(self.__dict__)


def read_serial_message(serial_client, max_bytes=MAX_READ_LENGTH):
  msg = TracerMsg()

  # Wait for sync
  sync_offset = 0
  while True:
    last_bytes = serial_client.read(size=1)
    if not last_bytes:
      LOG.info('Read timeout')
      return None  # Read timeout

    max_bytes -= 1
    if max_bytes <= 0:
      LOG.info('No sync found')
      return None  # No sync found

    last_byte = last_bytes[0]
    if last_byte == SYNC_HEADER[sync_offset]:
      sync_offset += 1
    elif last_byte == SYNC_HEADER[0]:
      sync_offset = 1
    else:
      sync_offset = 0
    LOG.info('Sync byte read. sync_offset: %s', sync_offset)

    if sync_offset >= len(SYNC_HEADER):
      break

  LOG.info('Sync header recieved. sync_offset: %s', sync_offset)

  # Read header
  last_bytes = serial_client.read(size=3)
  if len(last_bytes) < 3:
    return None  # Read timeout

  msg.controller_id = int.from_bytes(last_bytes[0:1], byteorder='little')
  msg.command = int.from_bytes(last_bytes[1:2], byteorder='little')
  msg.data_length = int.from_bytes(last_bytes[2:3], byteorder='little')
  LOG.info('Header received. msg: %s', msg)

  # Read Data
  data = serial_client.read(size=msg.data_length)
  if len(data) < msg.data_length:
    LOG.info('Too short message (%d), or read timeout.', len(data))
    return None  # Read timeout
  if msg.command == 0xA0:
    parse_sensor_data(data, msg)
  LOG.info('Data read. msg: %s',  msg)

  # Footer
  footer = serial_client.read(size=3)
  if len(footer) < 3:
    LOG.info('Too short footer (%d), or read timeout.', len(footer))
    return None  # Read timeout
  msg.crc = int.from_bytes(footer[0:2], byteorder='little')
  if int.from_bytes(footer[2:3], byteorder='little') != 0x7F:
    LOG.info('Incorrect footer: %d', footer[2:3])
    return None  # Incorrect footer
  LOG.info('Footer read. msg: %s', msg)

  return msg


def parse_sensor_data(data, msg):
  if len(data) < 23:
    return

  msg.batt_volt = parse_float(data, 0)
  msg.pv_volt = parse_float(data, 2)
  msg.load_current = parse_float(data, 6)
  msg.batt_overdischarge_volt = parse_float(data, 8)
  msg.batt_full_volt = parse_float(data, 10)
  msg.load_on = parse_bool(data, 12)
  msg.load_overload = parse_bool(data, 13)
  msg.load_short = parse_bool(data, 14)
  msg.batt_overload = parse_bool(data, 16)
  msg.batt_overdischarge = parse_bool(data, 17)
  msg.batt_full = parse_bool(data, 18)
  msg.batt_temp = parse_temp(data, 20)
  msg.charge_current = parse_float(data, 21)

  msg.load_power = msg.batt_volt * msg.load_current
  msg.charge_power = msg.batt_volt * msg.charge_current


def parse_float(data, offset):
  return parse_int(data, offset) / 100.0


def parse_int(data, offset):
  return int.from_bytes(data[offset: offset+2], byteorder='little')


def parse_bool(data, offset):
  return data[offset] > 0


def parse_temp(data, offset):
  return int.from_bytes(data[offset: offset + 1], byteorder='little') - 30


def read_now_ms():
  return int(time.time() * 1000)


def send_query_command(serial_client):
  serial_client.send(SYNC_HEADER)
  serial_client.send(QUERY_COMMAND)

def main():
  init_logger_stdout()

  LOG.info('Serial2Mqtt starting...')

  LOG.info('Reading options.json')
  with open('/data/options.json') as options_file:
    options_json = json.load(options_file)

  LOG.info('Init Serial port')
  serial_client = init_serial_client(options_json)

  LOG.info('Init MQTT client')
  mqtt_client = init_mqtt_client(options_json)
  mqtt_topic = options_json.get('mqtt_topic', 'epsolar_tracer/')
  mqtt_topic_msg = '%s/read' % mqtt_topic.removesuffix('/')
  mqtt_topic_online = '%s/online' % mqtt_topic.removesuffix('/')
  mqtt_qos = options_json.get('mqtt_publish_qos', 0)
  mqtt_retain = options_json.get('mqtt_publish_retain', True)
  mqtt_client.publish(
    mqtt_topic_online, "{\"online\": true}", qos=mqtt_qos, retain=mqtt_retain)
  LOG.info('MQTT Published init messsage to: %s', mqtt_topic_online)

  query_period_ms = options_json.get('query_period_sec', 600) * 1000
  next_query_ms = read_now_ms()

  while True:
    LOG.info(
      'Start to listen to serial port %s and mqtt topic. '
      'serial_client.is_open: %s',
      options_json.get('serial_port', '/dev/ttyUSB0'), serial_client.is_open)

    try:
      while True:
        LOG.info('Main loop')

        # Send query request periodically
        now_ms = read_now_ms()
        if query_period_ms > 0 and next_query_ms > now_ms:
          next_query_ms = max(now_ms, next_query_ms + query_period_ms)
          send_query_command(serial_client)

        # Listen to new messages the rest of the time
        LOG.info('Listening for next message.')
        msg = read_serial_message(serial_client)
        LOG.info('Message: %s', msg.to_json() if msg is not None else 'None')

        if msg and msg.command == 0xA0:
          mqtt_client.publish(
            mqtt_topic_msg, msg.to_json(), qos=mqtt_qos, retain=mqtt_retain)
          LOG.info('Published to MQTT topic %s', mqtt_topic)

    except serial.SerialException as se:
      LOG.warning('Serial disconnected: %s', str(se))
    except Exception as e:
      LOG.warning('Exception: %s', e)
    finally:
      serial_client.close()

    # Reconnection loop
    LOG.info('Disconnected, will attempt reconnect.')
    reconnect_serial_client(serial_client)

  mqtt_client.publish(
    mqtt_topic_online, "{\"online\": false}", qos=mqtt_qos, retain=mqtt_retain)


if __name__ == "__main__":
  main()
