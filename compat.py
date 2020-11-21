from plyer.utils import platform
import threading
import time
from collections import deque
from random import random
from statistics import mean
import numpy as np

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


if platform == 'android':
    from jnius import PythonJavaClass, java_method, autoclass, cast
    from plyer.platforms.android import activity

    Context = autoclass('android.content.Context')
    Sensor = autoclass('android.hardware.Sensor')
    SensorManager = autoclass('android.hardware.SensorManager')


    class SensorListener(PythonJavaClass):
        __javainterfaces__ = ['android/hardware/SensorEventListener']

        def __init__(self, default_rate):
            super().__init__()
            self.cnt = 0
            self.rate = 0
            self.rate_q = deque([default_rate], maxlen=10)
            self.values = [0.0, 0.0, 0.0]

        def enable(self, q, lock):
            self.lock = lock
            self.q = q
            self.last_time = time.time()
            self.SensorManager.registerListener(
                self, self.sensor,
                SensorManager.SENSOR_DELAY_FASTEST
            )

        def disable(self):
            self.SensorManager.unregisterListener(self, self.sensor)

        @java_method('(Landroid/hardware/Sensor;I)V')
        def onAccuracyChanged(self, sensor, accuracy):
            # Maybe, do something in future?
            pass

    class AccelerometerSensorListener(SensorListener):
        def __init__(self):
            super().__init__(default_rate=DEFAULT_ACCELEROMETER_RATE)
            self.name = 'acc'
            self.small_q = deque(maxlen=30)
            self.SensorManager = cast(
                'android.hardware.SensorManager',
                activity.getSystemService(Context.SENSOR_SERVICE)
            )
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_ACCELEROMETER
            )

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            with self.lock:
                self.cnt += 1
                self.small_q.append(event.values)
                self.q.append(event.values)
                t = time.time()
                if t - self.last_time > 1:
                    self.rate_q.append(self.cnt)
                    self.rate = mean(self.rate_q)
                    self.last_time = t
                    self.cnt = 0



    class MagnetometerSensorListener(SensorListener):
        def __init__(self, acc):
            super().__init__(default_rate=DEFAULT_MAGNETOMETER_RATE)
            self.name = 'spat'
            self.acc = acc
            service = activity.getSystemService(Context.SENSOR_SERVICE)
            self.SensorManager = cast('android.hardware.SensorManager', service)
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_MAGNETIC_FIELD)

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            with self.lock:
                self.cnt += 1
                self.values = event.values
                t = time.time()

                rotation = [0] * 9
                inclination = [0] * 9
                gravity = []
                geomagnetic = []

                aq = self.acc.small_q
                n = len(aq)
                if n == 0:
                    return
                acc_values = np.array([aq.popleft() for _ in range(n)])
                gravity = list(np.median(acc_values, axis=0))
                #gravity = self.acc.values
                geomagnetic = event.values
                ff_state = self.SensorManager.getRotationMatrix(rotation, inclination, gravity, geomagnetic )
                if ff_state:
                    values = [0, 0, 0]
                    values = self.SensorManager.getOrientation(rotation, values)
                    self.q.append(values)
                    if t - self.last_time > 1:
                        self.rate_q.append(self.cnt)
                        self.rate = mean(self.rate_q)
                        self.last_time = t
                        self.cnt = 0


class Dummy:
    def __init__(self, _rate, type='acc'):
        self.rate = 0
        self._rate = _rate
        self.type = type

    def enable(self, q, lock):
        self.lock = lock
        self.q = q
        self.run = True
        do_th = threading.Thread(target=self.do, daemon=True)
        do_th.start()

    def disable(self):
        self.run = False

    def do(self):
        cnt = 0
        last_time = time.time()
        while self.run:
            time.sleep(1/self._rate)
            if self.type == 'mag':
                azimuth = np.random.uniform(-np.pi, np.pi)
                pitch = np.random.uniform(-np.pi/4, np.pi/4)
                roll = np.random.uniform(-np.pi, 0)
                data = np.array([azimuth, pitch, roll])
            else:
                data = np.array([random() - 2 , random(), random() + 2 ])
            with self.lock:
                self.q.append(data)
                cnt +=1
                t = time.time()
                if t - last_time > 1:
                    self.rate = cnt
                    last_time = t
                    cnt = 0

class Accelerometer:
    def __init__(self):
        self.q = deque([(0, 0, 0)] * ACCELEROMETER_BUFFER_LEN, maxlen = ACCELEROMETER_BUFFER_LEN)
        self.mag_q = deque([(0, 0, 0)] * ACCELEROMETER_BUFFER_LEN, maxlen = ACCELEROMETER_BUFFER_LEN)
        self.lock = threading.Lock()
        self.mag_lock = threading.Lock()
        self.started = False

    def enable(self):
        if self.started:
            return
        if platform == 'android':
            self.acc = AccelerometerSensorListener()
            self.mag = MagnetometerSensorListener(self.acc)
        else:
            self.acc = Dummy(DEFAULT_ACCELEROMETER_RATE)
            self.mag = Dummy(DEFAULT_MAGNETOMETER_RATE, type='mag')

        self.acc.enable(self.q, self.lock)
        self.mag.enable(self.mag_q, self.mag_lock)
        self.started = True

    def disable(self):
        if not self.started:
            return
        self.acc.disable()
        self.mag.disable()
        self.started = False

    @property
    def rate(self):
        return self.acc.rate
    @property
    def mag_rate(self):
        return self.mag.rate


accelerometer = Accelerometer()


