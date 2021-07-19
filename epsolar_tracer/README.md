# EP-Solar Tracer
This Hassio addon reads collected real time data from EP-Solar tracer MPPT MT-5
Solar charge controller. It passes the data on to MQTT.

TODO: Image

## Installation
TODO: Cable creation


## Setup
TOOD: Options
Testing


## TODO

Fix warnings and deprecations
```
21-07-04 17:00:30 WARNING (MainThread) [supervisor.addons.validate] Add-on config 'startup' with 'before' is deprecated. Please report this to the maintainer of EPSolar Tracer MT-5
21-07-04 17:00:30 WARNING (MainThread) [supervisor.addons.validate] Add-on config 'auto_uart' is deprecated, use 'uart'. Please report this to the maintainer of EPSolar Tracer MT-5
21-07-04 17:00:30 WARNING (MainThread) [supervisor.addons.validate] Add-on have full device access, and selective device access in the configuration. Please report this to the maintainer of EPSolar Tracer MT-5
21-07-04 17:00:30 WARNING (MainThread) [supervisor.store.data] Can't read /data/addons/git/fc962596/frpc/config.json: required key not provided @ data['arch']. Got None
```



Add to config
```
  "arch": ["armhf", "armv7", "aarch64", "amd64", "i386"],
  "full_access": "yes"

```