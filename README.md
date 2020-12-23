#  Project description

* A FitBit for your bow
* Count arrows shot
* Orientation sensor for stability/consistency analsysis
* Live and instant feedback while you aim
* Auto-freeze screen after each shot for post-mortem investigations

<img src="/extra/DSC_0482.JPG"  width="400" height="600"><img src="/extra/DSC_0488.JPG"  width="400" height="600"><img src="/extra/DSC_0480.JPG"  width="400" height="600"> <img src="/extra/wellbeing.png"  width="300" height="600">


* Developed and tested on Galaxy S10
* [Bow phone Mount](https://www.amazon.ca/Smartphone-Camera-Phone-IPhone-Samsung/dp/B00BVF6V5Q)
* Use the 'Digital Wellbeing' app on Android 10+ to track total arrows shot over days/weeks

## Installation

Download and install the latest APK from the [Release section](https://github.com/mzakharo/smartbow/releases)

##  InfluxDB setup (Optional)

 * You can upload each shot timestamp + raw orientation sensor data into your private InfluxDB database, for offline analsys/data science
![InfluxDB](/extra/influx.png?raw=true "Orientation")
 * You can obtain a free [InfluxDB account](https://cloud2.influxdata.com/signup)
 * Edit and add a [smartbow_config.json](/smartbow_config.json) to the root of the internal storage (`/sdcard`)

# APK Build instructions

## Add to .bashrc
```export PATH=$HOME/.local/bin/:$HOME/.buildozer/android/platform/android-sdk/platform-tools/:$PATH```

## Prep for buildozer
```
#  from https://buildozer.readthedocs.io/en/latest/installation.html#android-on-ubuntu-20-04-64bit
sudo apt install -y git zip unzip openjdk-8-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
sudo apt install ccache
```

## Conda on Ubuntu 20.04 install
```
 # get conda with python 3.8
 sh ./Miniconda3-py38-Linux-x86_64.sh
 conda install -c conda-forge kivy
 conda install cython numpy
 pip install -r  requirements.txt
```

## run the app
```python main.py```

## build the .apk
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
