from plyer.utils import platform
from plyer import storagepath
import threading
import time
from collections import deque
from random import random
from statistics import mean
import numpy as np
import pandas as pd
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
            self.rate = default_rate
            self.values = [0.0, 0.0, 0.0]

        def enable(self, q, tq, lock):
            self.lock = lock
            self.q = q
            self.tq = tq
            self.last_time = time.time()
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
            print('onAccuracyChanged', sensor, accuracy)

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            with self.lock:
                self.q.append(event.values)
                self.tq.append(event.timestamp)
                self.calc_rate(event.timestamp)



    class AccelerometerSensorListener(SensorListener):
        def __init__(self):
            super().__init__(default_rate=DEFAULT_ACCELEROMETER_RATE)
            self.name = 'acc'
            self.SensorManager = cast(
                'android.hardware.SensorManager',
                activity.getSystemService(Context.SENSOR_SERVICE)
            )
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_ACCELEROMETER
            )

    class MagnetometerSensorListener(SensorListener):
        def __init__(self, acc):
            super().__init__(default_rate=DEFAULT_MAGNETOMETER_RATE)
            self.name = 'mag'
            service = activity.getSystemService(Context.SENSOR_SERVICE)
            self.SensorManager = cast('android.hardware.SensorManager', service)
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_MAGNETIC_FIELD)

        '''
        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            with self.lock:
                print('acc', n)
                self.last_acc_values = acc_values
                geomagnetic = event.values
                rotation = [0] * 9
                ff_state = self.SensorManager.getRotationMatrix(rotation, None, gravity, geomagnetic)
                if ff_state:
                    values = [0, 0, 0]
                    values = self.SensorManager.getOrientation(rotation, values)
                    self.q.append(values)
                    self.tq.append(event.timestamp)
                    self.calc_rate(event.timestamp)
        '''


class Dummy:
    def __init__(self, _rate, type='acc'):
        self.rate = 0
        self._rate = _rate
        self.type = type
        self.last_time = time.monotonic_ns()
        self.cnt = 0

    def enable(self, q, tq, lock):
        self.lock = lock
        self.q = q
        self.tq = tq
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
            data = np.array([random() - 2 , random(), random() + 2 ])
            data = list(data)
            with self.lock:
                self.q.append(data)
                self.tq.append(tstamp)
                self.calc_rate(tstamp)

class Accelerometer:
    def __init__(self):
        def iq(x, m):
            return deque([x] * m, maxlen=m) 
        self.q = iq((0.0, 0.0, 0.0), ACCELEROMETER_BUFFER_LEN)
        self.tq = iq(0, ACCELEROMETER_BUFFER_LEN)
        self.mag_q = iq((0.0, 0.0, 0.0), ORIENTATION_BUFFER_LEN)
        self.mag_tq = iq(0, ORIENTATION_BUFFER_LEN)
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

        self.acc.enable(self.q, self.tq, self.lock)
        self.mag.enable(self.mag_q, self.mag_tq, self.mag_lock)
        self.started = True

    def disable(self):
        if not self.started:
            return
        self.acc.disable()
        self.mag.disable()
        self.started = False

    

accelerometer = Accelerometer()

def get_application_dir():
    if platform == 'android':
        return activity.getFilesDir().getPath()
    else:
        return storagepath.get_application_dir()

def getRotationMatrix(rotation,b,gravity,geomagnetic):
    if platform == 'android':
        return SensorManager.getRotationMatrix(rotation, None, gravity, geomagnetic)
    return True

def getOrientation(rotation, values):
    if platform == 'android':
        return SensorManager.getOrientation(rotation, values)
    return values

def get_orientation(acc, acc_t, mag, mag_t):
    if mag_t[0] == 0:
        log.warning('buffer not ready')
        return None
    mag_rate = int((mag_t[-1] - mag_t[0]) / len(mag_t))
    #print(mag_rate)
    a = pd.DataFrame(index=pd.to_datetime(acc_t), data={f'acc{i}': v for i, v  in enumerate(acc)})
    m = pd.DataFrame(index=pd.to_datetime(mag_t), data={f'mag{i}': v for i, v  in enumerate(mag)})
    df = pd.concat([a, m], sort=True)
    df = df.resample(f'{mag_rate}N').mean().dropna()
    #with pd.option_context("display.max_rows", 40):
    #    print('df', df)
    points = []
    for _, row in df.iterrows():
        gravity = [row.acc0, row.acc1, row.acc2]
        geomagnetic = [row.mag0, row.mag1, row.mag2]
        rotation = [0.0] * 9
        ff_state = getRotationMatrix(rotation, None, gravity, geomagnetic)
        #assert ff_state == True
        values = [0.0, 0.0, 0.0]
        values = getOrientation(rotation, values)
        points.append(values)
    points = np.array(points).T
    points_t = df.index.astype(np.int64)
    print(points_t[-1], points.shape)
    return points, points_t
