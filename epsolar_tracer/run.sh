#!/usr/bin/with-contenv bashio

MQTT_HOST=$(bashio::services mqtt "host")
MQTT_PASSWORD=$(bashio::services "mqtt" "password")
MQTT_PORT=$(bashio::services "mqtt" "port")
MQTT_USERNAME=$(bashio::services "mqtt" "username")
MQTT_URL="mqtt://${MQTT_USERNAME}:${MQTT_PASSWORD}@${MQTT_HOST}:${MQTT_PORT}"
echo "mqtt URL: ${MQTT_URL}"

python3 -m epsolar_tracer "${MQTT_URL}"
