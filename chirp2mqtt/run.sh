#!/usr/bin/with-contenv bashio

echo " "

echo "Check if you have enabled I2C and have /dev/i2c-1."
I2C_FILE=/dev/i2c-1
if [ -e "$I2C_FILE" ]; then
    echo "$I2C_FILE exist, i2c is enabled!"
else
    echo "$I2C_FILE does not exist! Please enable, see README.md"
fi
echo "ls /dev/i2c-*"
ls /dev/i2c-*
echo " "

echo "Check if any i2C sensor is connected and their address"
echo "i2cdetect"
/usr/sbin/i2cdetect -y 1
echo " "

echo "Start chirp2mqtt"
python3 -m chirp2mqtt

echo "Finished chirp2mqtt"
