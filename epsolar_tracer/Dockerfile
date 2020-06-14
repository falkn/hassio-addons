ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy data for add-on
COPY run.sh /
COPY requirements.txt /
COPY *.py /
RUN chmod a+x /run.sh

# Install python
RUN apk add --no-cache python3

# Install python requirements
RUN pip3 install -r requirements.txt

# Start
CMD [ "/run.sh" ]
