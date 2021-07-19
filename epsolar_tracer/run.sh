#!/usr/bin/with-contenv bashio

MQTT_HOST=$(bashio::services mqtt "host")
MQTT_PASSWORD=$(bashio::services "mqtt" "password")
MQTT_PORT=$(bashio::services "mqtt" "port")
MQTT_USERNAME=$(bashio::services "mqtt" "username")
echo "mqtt host: $MQTT_HOST $MQTT_PORT $MQTT_USERNAME $MQTT_PASSWORD"

python3 -m epsolar_tracer
