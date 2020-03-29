ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy data for add-on
COPY run.sh /
COPY requirements.txt /
COPY *.py /
RUN chmod a+x /run.sh

# Depend on chirp python library by copy
# RUN git clone https://github.com/ageir/chirp-rpi.git
COPY chirp-rpi/* chirp-rpi/

# Install package dependencies
RUN apk add --no-cache python3
RUN apk add --no-cache i2c-tools
RUN apk add --no-cache py3-smbus
RUN apk add --no-cache mosquitto-clients

# Install python requirements
RUN pip3 install -r requirements.txt

# Start
CMD [ "/run.sh" ]
