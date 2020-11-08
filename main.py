from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot
from kivy.clock import Clock

import time
from collections import deque
import threading

from compat import acc, LockScreen

class Worker:
    def __init__(self):
        self.xq = deque( maxlen = 500)
        self.yq = deque( maxlen = 500)
        self.zq = deque( maxlen = 500)

        self.lock = threading.Lock()

    def start(self):
        self.run = True
        do_th = threading.Thread(target=self.do, daemon=True)
        do_th.start()

    def stop(self):
        self.run = False

    def do(self):
        cnt = 0
        last_time = time.time()
        acc.enable()
        while self.run:
            time.sleep(0.008) #100hz ish
            x, y, z = acc.get_acceleration()
            if x is not None:
                cnt +=1
                with self.lock:
                    self.xq.append(x)
                    self.yq.append(y)
                    self.zq.append(z)
            if time.time() - last_time > 1:
                print(f'rate {cnt}/sec')
                last_time = time.time()
                cnt = 0
        acc.disable()


class Logic(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__()
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[0, 0, 1, 1])
        self.w = Worker()
        self.first_run = True


    def start(self):
        print('start')
        self.w.start()

        if self.first_run:
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        Clock.schedule_interval(self.get_value, 0.150) #Nexus 6P cant go any faster

    def stop(self):
        print('stop')
        Clock.unschedule(self.get_value)
        self.w.stop()

    def get_value(self, dt):
        with self.w.lock:
            lx = list(enumerate(self.w.xq))
            ly = list(enumerate(self.w.yq))
            lz = list(enumerate(self.w.zq))
        self.px.points = lx
        self.py.points = ly
        self.pz.points = lz


class SmartBow(App): 
    def build(self): 
        self.b  = Builder.load_file("look.kv")
        return self.b

    def on_resume(self):
        self.lockscreen.set()
        return True

    def on_pause(self):
        self.lockscreen.unset()
        self.b.stop()
        return True

    def on_start(self):
        self.lockscreen = LockScreen()
        self.lockscreen.set()

    def on_stop(self):
        self.b.stop()
        return True


if __name__ == "__main__":
    SmartBow().run()     
