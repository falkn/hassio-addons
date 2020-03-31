# Release instructions

# Build locally
Just copy the addon directory to the Raspaberry Pi's addon folder using Samba share.

# Relase to dockerhub
1.  Clone git repository and/or sync to head. [[github](https://github.com/falkn/hassio-addons)]

        git clone https://github.com/falkn/hassio-addons.git 
        git pull

1.  Install build engines [[ref](https://github.com/home-assistant/hassio-builder)]

        docker pull homeassistant/amd64-builder
        docker pull homeassistant/armv7-builder
        docker pull homeassistant/aarch64-builder
   
1.   Build and upload image to Docker Hub.

         docker run --rm --privileged -v \
           ~/.docker:/root/.docker homeassistant/amd64-builder \
           --all \
           -t chirp2mqtt \
           -r https://github.com/falkn/hassio-addons \
           -b build

[Instructions](https://developers.home-assistant.io/docs/hassio_addon_publishing)