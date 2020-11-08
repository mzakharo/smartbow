from plyer.utils import platform
from plyer import accelerometer
from random import random

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


class Accelerometer:
    def enable(self):
        if platform == 'android':
            accelerometer.enable()
    def disable(self):
        if platform == 'android':
            accelerometer.disable()
    def get_acceleration(self):
        return accelerometer.acceleration if platform == 'android' else (random(), random(), random())

acc = Accelerometer()


