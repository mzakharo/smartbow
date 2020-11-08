from plyer.utils import platform
from random import random
import threading
import time
from collections import deque

LEN = 500

if platform == 'android':
    from plyer.platforms.android import activity
    from jnius import autoclass
    #workaround, see https://github.com/kivy/pyjnius/issues/137#issuecomment-248673727
    autoclass('org.jnius.NativeInvocationHandler')
    from android.runnable import run_on_ui_thread
else:
    def run_on_ui_thread(func):
        def wrapper(args):
            return func(args)
        return wrapper


class LockScreen():
    def __init__(self):
        if platform != 'android':
            return
        Context = autoclass('android.content.Context')
        self.params = autoclass('android.view.WindowManager$LayoutParams')
        self.window = activity.getWindow()
        self.live = True

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
            self.last_time = time.time()
            self.cnt = 0

        def enable(self, q, lock):
            self.lock = lock
            self.q = q
            self.SensorManager.registerListener(
                self, self.sensor,
                SensorManager.SENSOR_DELAY_FASTEST
            )

        def disable(self):
            self.SensorManager.unregisterListener(self, self.sensor)

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            self.cnt += 1
            with self.lock:
                self.q.append(event.values)
            if time.time() - self.last_time > 1:
                print(f'rate {self.cnt}/sec')
                self.cnt = 0
                self.last_time = time.time()


        @java_method('(Landroid/hardware/Sensor;I)V')
        def onAccuracyChanged(self, sensor, accuracy):
            # Maybe, do something in future?
            pass

class Accelerometer:
    def __init__(self):
        self.q = deque([[random(), random(), random()] for _ in  range(LEN)]*LEN, maxlen = LEN)
        self.lock = threading.Lock()

    def enable(self):
        if platform == 'android':
            self.acc = AccelerometerSensorListener()
            self.acc.enable(self.q, self.lock)
    def disable(self):
        if platform == 'android':
            self.acc.disable()

acc = Accelerometer()


