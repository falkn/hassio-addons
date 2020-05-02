#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Hass.io Add-on Serial UART port to MQTT bridge.

Uesful to hook up Arduino to Raspberry Pi.
"""

import json
import logging
import sys
import serial
import time
from urllib.parse import urlparse
import functools

from paho.mqtt import client as mqtt


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

SERIAL_TIMEOUT = 100.0  # seconds?
RECONNECT_TIMEOUT_S = 30.0  # seconds

MAX_LINE_LENGTH = 64*1024
MQTT_SUBSCRIBE_QOS = 1  # At least once delivery.


def init_logger_stdout():
  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.INFO)
  formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  LOG.addHandler(handler)


def remove_suffix(text, suffix):
  if text.endswith(suffix):
    return text[:-len(suffix)]
  return text


def remove_prefix(text, prefix):
  if text.startswith(prefix):
    return text[len(prefix):]
  return text


def on_mqtt_connect(client, userdata, flags, rc):
  LOG.info('MQTT connected')


def on_mqtt_disconnect(client, userdata, rc):
  LOG.info('MQTT disconnected')


def on_mqtt_subscribe(client, userdata, mid, granted_qos, properties=None):
  LOG.info('MQTT subscribed')


def on_mqtt_unsubscribe(client, userdata, mid):
  LOG.info('MQTT unsubscribed')


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

  mqtt_client.on_connect = on_mqtt_connect
  mqtt_client.on_disconnect = on_mqtt_disconnect
  mqtt_client.on_subscribe = on_mqtt_subscribe
  mqtt_client.on_unsubscribe = on_mqtt_unsubscribe

  mqtt_client.connect(mqtt_url.hostname, mqtt_url.port or 1883)
  return mqtt_client


def create_serial_client(options_json):
  return serial.Serial(
      options_json.get('serial_port', '/dev/ttyUSB0'),
      options_json.get('serial_baud', 74880),
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


def process_serial_readline(serial_client, mqtt_client, mqtt_publish_topic, options_json):
  line = serial_client.readline(MAX_LINE_LENGTH)
  if not line:
    return

  qos = options_json.get('mqtt_publish_qos', 0)
  retain = options_json.get('mqtt_publish_retain', False)

  try:
    line = line.decode('utf-8')
    line_json = json.loads(line)
    sub_topic = line_json.get('topic', 'data')
    msg = line_json.get('msg', None)
    qos = line_json.get('qos', qos)
    retain = line_json.get('retain', retain)
  except UnicodeDecodeError as ue:
    LOG.warning('Could not decode as utf-8: "%s", passing on as is, error: %s',
                line, str(ue))
    return
  except json.JSONDecodeError as je:
    # Messages that cannot be parsed, just pass on to the 'log' topic.
    msg = None

  if msg is None:
    sub_topic = 'log'
    msg_str = line
  elif isinstance(msg, dict):
    msg_str = json.dumps(msg)
  elif isinstance(msg, str):
    msg_str = msg
  else:
    msg_str = '%s' % msg

  topic = '%s/%s' % (mqtt_publish_topic, sub_topic)
  mqtt_client.publish(topic, msg_str, qos=qos, retain=retain)
  LOG.info('Published %s: %s', topic, msg_str)


def on_mqtt_message(serial_client, mqtt_subscribe_topic, mqtt_client, userdata, message):
  # This is called from the mqtt network thread
  # seems like it's safe to read and write to PySerial in different
  # threads:
  #   https://stackoverflow.com/questions/8796800/pyserial-possible-to-write-to-serial-port-from-thread-a-do-blocking-reads-fro
  try:
    serial_json = {}

    if isinstance(message.topic, bytes):
      serial_topic = message.topic.decode('utf-8')
    elif isinstance(message.topic, str):
      serial_topic = message.topic
    else:
      LOG.error('Unexpected topic type: %s. Ignoring.', type(message.topic))
      return

    serial_topic = remove_prefix(serial_topic, mqtt_subscribe_topic)
    serial_topic = remove_prefix(serial_topic, '/')
    serial_json['topic'] = serial_topic

    try:
      if isinstance(message.payload, bytes):
        msg_str = message.payload.decode('utf-8')
      elif isinstance(message.payload, str):
        msg_str = message.payload
      else:
        LOG.error(
          'MQTT subscription on mesage, unexpected payload on topic %s '
          'type: %s. Ignoring.',
          serial_topic, type(message.payload))
        return

      msg_json = json.loads(msg_str)
      # msg as a sub-json message
      serial_json['msg'] = msg_json
    except UnicodeDecodeError as ue:
      LOG.error('Message on topic %s Ignoring bytes not convertible to utf-8',
                message.topic)
    except json.JSONDecodeError as je:
      # msg as just a string
      serial_json['msg'] = msg_str

    serial_data = '%s\n' % json.dumps(serial_json)
    if serial_client.is_open:
      serial_client.write(serial_data.encode('utf-8'))
      LOG.info("Sent to serial: %s", serial_data)
    else:
      LOG.warning(
        'Could not send to closed serial. Dropping message on topic: %s',
        message.topic)

  except serial.SerialException:
    # https://stackoverflow.com/questions/46998496/paho-mqtt-python-client-acknowledgement-missing-guaranteed-delivery-for-subsc
    LOG.warning('Serial disconnected while handling a message: %s', message)
    raise  # Try to raise exception for redelivery??
  except Exception as e:
    # Log and ignore any other message (broken message?)
    LOG.error('Exception handling MQTT subscribe message: %s', str(e),
              exc_info=True)


def init_mqtt_subscriber(mqtt_client, serial_client, mqtt_subscribe_topic):
  mqtt_client.on_message = functools.partial(on_mqtt_message, serial_client,
                                             mqtt_subscribe_topic)
  mqtt_client.subscribe('%s/#' % mqtt_subscribe_topic, MQTT_SUBSCRIBE_QOS)


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
  mqtt_publish_topic = options_json.get('mqtt_publish_topic', 'arduino/read')
  mqtt_publish_topic = remove_suffix(mqtt_publish_topic, '/')
  mqtt_subscribe_topic = options_json.get('mqtt_subscribe_topic',
                                          'arduino/write')
  mqtt_subscribe_topic = remove_suffix(mqtt_subscribe_topic, '#')
  mqtt_subscribe_topic = remove_suffix(mqtt_subscribe_topic, '/')

  LOG.info('Subscribe to topic')
  init_mqtt_subscriber(mqtt_client, serial_client, mqtt_subscribe_topic)
  mqtt_client.loop_start()

  while True:
    LOG.info(
      'Start to listen to serial port and mqtt topic. '
      'serial_client.is_open: %s',
      serial_client.is_open)

    try:
      while True:
        process_serial_readline(serial_client, mqtt_client, mqtt_publish_topic, options_json)
    except serial.SerialException as se:
      LOG.warning('Serial disconnected: %s', str(se))
    except serial.Exception as e:
      LOG.warning('Serial disconnected: %s', e)
    finally:
      serial_client.close()

    # Reconnection loop
    LOG.info('Disconnected, will attempt reconnect.')
    reconnect_serial_client(serial_client)


if __name__ == "__main__":
  main()
