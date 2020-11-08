from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot
from kivy.clock import Clock

import time
import threading
import numpy as np

from compat import accelerometer, LockScreen

class Logic(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__()
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[0, 0, 1, 1])
        self.first_run = True


    def start(self):
        print('start')
        accelerometer.enable()

        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        Clock.schedule_interval(self.get_value, 0.5)

    def stop(self):
        print('stop')
        Clock.unschedule(self.get_value)
        accelerometer.disable()

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.q).T
        gr = self.ids.graph
        gr.ymax = max(1, int(points.max())+1)
        gr.ymin = min(int(points.min()-1), gr.ymax-1)
        gr.xmax = points.shape[1]
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
