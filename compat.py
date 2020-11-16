from plyer.utils import platform
import threading
import time
from collections import deque
from random import random
from statistics import mean

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


    class AccelerometerSensorListener(PythonJavaClass):
        __javainterfaces__ = ['android/hardware/SensorEventListener']

        def __init__(self):
            super().__init__()
            self.SensorManager = cast(
                'android.hardware.SensorManager',
                activity.getSystemService(Context.SENSOR_SERVICE)
            )
            self.sensor = self.SensorManager.getDefaultSensor(
                Sensor.TYPE_ACCELEROMETER
            )
            self.cnt = 0
            self.rate = 0
            self.rate_q = deque([DEFAULT_ACCELEROMETER_RATE], maxlen=10)

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

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            with self.lock:
                self.cnt += 1
                self.q.append(event.values)
                t = time.time()
                if t - self.last_time > 1:
                    self.rate_q.append(self.cnt)
                    self.rate = mean(self.rate_q)
                    self.last_time = t
                    self.cnt = 0


        @java_method('(Landroid/hardware/Sensor;I)V')
        def onAccuracyChanged(self, sensor, accuracy):
            # Maybe, do something in future?
            pass

class AccelerometerDummy:
    def __init__(self):
        self.rate = 0
        pass

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
            time.sleep(1/DEFAULT_ACCELEROMETER_RATE)
            data = [random() - 2 , random(), random() + 2 ]
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
        self.lock = threading.Lock()

    def enable(self):
        if platform == 'android':
            self.acc = AccelerometerSensorListener()
        else:
            self.acc = AccelerometerDummy()
        self.acc.enable(self.q, self.lock)
    def disable(self):
        self.acc.disable()

    @property
    def rate(self):
        return self.acc.rate

accelerometer = Accelerometer()


