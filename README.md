#  Project description

* Augment your bow with cybertech from your smartphone
* Daily arrow shot count
* Orientation view for stability/consistency analsysis
* Live and instant feedback while you aim
* Auto-freeze the screen after each shot for post-mortem investigations

<img src="/extra/DSC_0482.JPG"  width="400" height="600"><img src="/extra/DSC_0488.JPG"  width="400" height="600">

* Synchronize with fitbit to display total arrow count
<img src="/extra/fitbit.png"  width="400" height="600">

* Use Android 10+ Digital Well-being app to tally weekly progress goals

* Developed and tested with Galaxy S10
* [Bow Phone Mount](https://www.amazon.ca/Smartphone-Camera-Phone-IPhone-Samsung/dp/B00BVF6V5Q)

## Installation

Download and install the latest APK from the [Release section](https://github.com/mzakharo/smartbow/releases)

##  InfluxDB setup (Optional)

 * Upload raw orientation/accelerometer data for each shot into your private InfluxDB instance, for offline analsys/data science
![InfluxDB](/extra/influx.png?raw=true "Orientation")
 * You can obtain a free [InfluxDB account](https://cloud2.influxdata.com/signup)
 * Edit and add a [smartbow_config.json](/smartbow_config.json) to the root of the internal storage (`/sdcard`)

# APK Build instructions

Tested on Ubuntu 20.04.

## Add to .bashrc
```export PATH=$HOME/.local/bin/:$HOME/.buildozer/android/platform/android-sdk/platform-tools/:$PATH```

## Prep for buildozer
```
#  from https://buildozer.readthedocs.io/en/latest/installation.html#android-on-ubuntu-20-04-64bit
sudo apt install -y git zip unzip openjdk-8-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
sudo apt install ccache
```

## Setup native runtime environment

Download and install [conda](https://docs.conda.io/en/latest/miniconda.html)
```
 conda install -c conda-forge kivy
 conda install cython numpy
 pip install -r  requirements.txt
```

## run the app on the desktop
```python main.py```

## build the mobile .apk
 ```make```
 
## install the .apk
```make install```

## log
```./logcat.sh```

## Linux adb permissions 
```
lsusb  to get vendor/product
cp 51-android.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```
