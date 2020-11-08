from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot
from kivy.clock import Clock

import time
import threading
import numpy as np

from compat import acc, LockScreen, LEN

class Worker:
    def __init__(self):
        pass

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
            time.sleep(1)
            '''
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
            '''
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
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        Clock.schedule_interval(self.get_value, 0.5)

    def stop(self):
        print('stop')
        Clock.unschedule(self.get_value)
        self.w.stop()

    def get_value(self, dt):
        with acc.lock:
            points  = np.array([acc.q]).T
        gr = self.ids.graph

        gr.ymin = int(points.min())
        gr.ymax = max( 1, int(points.max()))
        gr.xmax = LEN
        gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)

        self.px.points = enumerate(points[0])
        self.py.points = enumerate(points[1])
        self.pz.points = enumerate(points[2])


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
