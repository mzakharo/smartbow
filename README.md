#  Project description

* This is an Android app to attach a smartphone to a compound bow, and use smartphone's sensors to count arrows shot, as well as review shot stability.
* A FitBit for a bow
* Tested with Galaxy S10

#  InfluxDB 2.0 setup (Optional)

If you want to upload arrow count/orientation sensor info into InfluxDB database, then either obtain free InfluxDB instance from https://cloud2.influxdata.com/signup, edit and add a smartbow_config.json to /sdcard


# Setup android adb
```
lsusb  to get vendor/product
cp 51-android.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

# Add to .bashrc
export PATH=$HOME/.local/bin/:$HOME/.buildozer/android/platform/android-sdk/platform-tools/:$PATH

# Prep for buildozer
```
#  from https://buildozer.readthedocs.io/en/latest/installation.html#android-on-ubuntu-20-04-64bit
sudo apt install -y git zip unzip openjdk-8-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
sudo apt install ccache
```

# Conda on Ubuntu 20.04 install
```
 # get conda with python 3.8
 sh ./Miniconda3-py38-Linux-x86_64.sh
 conda install -c conda-forge kivy
 conda install cython numpy
 pip install -r  requirements.txt
```

# run the app
```python main.py```

## build the .apk
 ```make```

## log
```./logcat.sh```

