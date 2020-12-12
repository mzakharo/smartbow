from plyer.utils import platform
from plyer import storagepath
import threading
import time
from collections import deque
from random import random
from statistics import mean
import numpy as np
from kivy.logger import Logger as log

from config import *


if platform == 'android':
    from plyer.platforms.android import activity
    from jnius import autoclass
    from android.runnable import run_on_ui_thread

    #workaround, see https://github.com/kivy/pyjnius/issues/137#issuecomment-248673727
    autoclass('org.jnius.NativeInvocationHandler')
else:
    def run_on_ui_thread(func):
        def wrapper(args):
            return func(args)
        return wrapper


class LockScreen():
    def __init__(self):
        if platform != 'android':
            return
        self.params = autoclass('android.view.WindowManager$LayoutParams')
        self.window = activity.getWindow()

    @run_on_ui_thread
    def set(self):
        if platform != 'android':
            return
        self.window.addFlags(self.params.FLAG_KEEP_SCREEN_ON)

    @run_on_ui_thread
    def unset(self):
        if platform != 'android':
            return
        self.window.clearFlags(self.params.FLAG_KEEP_SCREEN_ON)

iq = lambda x, m: deque([x] * m, maxlen=m)

if platform == 'android':
    from jnius import PythonJavaClass, java_method, autoclass, cast
    from plyer.platforms.android import activity

    Context = autoclass('android.content.Context')
    Sensor = autoclass('android.hardware.Sensor')
    SensorManager = autoclass('android.hardware.SensorManager')


    class SensorListener(PythonJavaClass):
        __javainterfaces__ = ['android/hardware/SensorEventListener']
        accuracy = 3

        def __init__(self, default_rate, buffer_len):
            super().__init__()
            self.cnt = 0
            self.lock = threading.Lock()
            self.rate = default_rate
            self.q = iq((0.0, 0.0, 0.0), buffer_len)
            self.tq = iq(0, buffer_len)
            self.last_time = 0

        def enable(self):
            self.SensorManager.registerListener(
                self, self.sensor,
                SensorManager.SENSOR_DELAY_FASTEST
            )

        def disable(self):
            self.SensorManager.unregisterListener(self, self.sensor)

        def calc_rate(self, tstamp):
            self.cnt += 1
            diff = tstamp - self.last_time 
            if diff >= 1e9:
                self.rate = self.cnt / diff * 1e9
                self.last_time = tstamp
                self.cnt = 0

        @java_method('(Landroid/hardware/Sensor;I)V')
        def onAccuracyChanged(self, sensor, accuracy):
            log.info(f"onAccuracyChanged {sensor} {accuracy}")

    class AccelerometerSensorListener(SensorListener):
        def __init__(self):
            super().__init__(default_rate=DEFAULT_ACCELEROMETER_RATE, buffer_len = ACCELEROMETER_BUFFER_LEN)
            self.name = 'acc'
            self.SensorManager = cast(
                'android.hardware.SensorManager',
                activity.getSystemService(Context.SENSOR_SERVICE)
            )
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_ACCELEROMETER
            )

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            self.accuracy = event.accuracy
            with self.lock:
                self.q.append(event.values)
                self.tq.append(event.timestamp)
            self.calc_rate(event.timestamp)



    class OrientationSensorListener(SensorListener):
        def __init__(self):
            super().__init__(default_rate=DEFAULT_ORIENTATION_RATE, buffer_len = ORIENTATION_BUFFER_LEN)
            self.name = 'ori'
            service = activity.getSystemService(Context.SENSOR_SERVICE)
            self.SensorManager = cast('android.hardware.SensorManager', service)
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_ROTATION_VECTOR)
        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            #log.info(f'accuracy: {event.accuracy} values: {event.values}')
            self.accuracy = event.accuracy
            rotation = [0] * 9
            self.SensorManager.getRotationMatrixFromVector(rotation, event.values);
            values = [0] * 3
            values = self.SensorManager.getOrientation(rotation, values)
            with self.lock:
                self.q.append(values)
                self.tq.append(event.timestamp)
            self.calc_rate(event.timestamp)

class Dummy:
    def __init__(self, _rate, type='acc', buffer_len=1):
        self.rate = _rate
        self._rate = _rate
        self.type = type
        self.last_time = time.monotonic_ns()
        self.q = iq((0.0, 0.0, 0.0), buffer_len)
        self.tq = iq(0, buffer_len)
        self.cnt = 0
        self.lock = threading.Lock()

    def enable(self):
        self.run = True
        do_th = threading.Thread(target=self.do, daemon=True, name=self.type)
        do_th.start()

    def disable(self):
        self.run = False

    def calc_rate(self, tstamp):
        self.cnt += 1
        diff = tstamp - self.last_time 
        if diff >= 1e9:
            self.last_time = tstamp
            self.rate = self.cnt / diff * 1e9
            self.cnt = 0

    def do(self):
        while self.run:
            time.sleep(1/self._rate)
            tstamp = time.monotonic_ns()
            if self.type == 'ori':
                azimuth = np.random.uniform(-np.pi, np.pi)
                pitch = np.random.uniform(-np.pi/4, np.pi/4)
                roll = np.random.uniform(-np.pi, 0)
                data = np.array([azimuth, pitch, roll])
            else:
                data = np.array([random() - 2 , random(), random() + 2 ])
            data = list(data)
            with self.lock:
                self.q.append(data)
                self.tq.append(tstamp)
            self.calc_rate(tstamp)

class Accelerometer:
    def __init__(self):
        self.started = False

    def enable(self):
        if self.started:
            return
        if platform == 'android':
            self.acc = AccelerometerSensorListener()
            self.ori = OrientationSensorListener()
        else:
            self.acc = Dummy(DEFAULT_ACCELEROMETER_RATE, buffer_len = ACCELEROMETER_BUFFER_LEN)
            self.ori= Dummy(DEFAULT_ORIENTATION_RATE, type='ori', buffer_len=ORIENTATION_BUFFER_LEN)

        self.acc.enable()
        self.ori.enable()
        self.started = True

    def disable(self):
        if not self.started:
            return
        self.acc.disable()
        self.ori.disable()
        self.started = False

    

sensor_manager = Accelerometer()

def get_application_dir():
    if platform == 'android':
        return activity.getFilesDir().getPath()
    else:
        return storagepath.get_application_dir()

