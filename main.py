from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import datetime
import threading
import numpy as np
from plyer import notification
from compat import accelerometer, LockScreen
from plyer import uniqueid

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from queue import Queue

from urllib3 import Retry
from config import *

class Worker:
    def __init__(self):
        retries = Retry(connect=5, read=2, redirect=5)
        self.client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, timeout=10, retries=retries)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS) #ASYNC does not work due to sem_ impoementation missing
        self.id = uniqueid.id
        self.q = Queue()
        do_th = threading.Thread(target=self.do, daemon=True)
        do_th.start()

    def process(self):
        cmd, val = self.q.get()
        if cmd == 'point':
            self.write_api.write(BUCKET, ORG, val)
        else:
            raise Exception("unknown cmd", cmd)

    def do(self):
        while True:
            try:
                self.process()
            except Exception as e:
                print(e)


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[0, 0, 1, 1])
        self.first_run = True
        self.shot_count = 0
        self.worker = Worker()
        self.enabled = False

    def on_enter(self):
        print('on enter')
        self.start()

    def on_exit(self):
        print('on exit')
        self.stop()

    def start(self):
        print('start')

        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        self.update_cnt = 0
        self.half_point = None
        self.shot_time = 0
        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True

    def stop(self):
        print('stop')
        Clock.unschedule(self.get_value)
        self.enabled = False

    def on_press(self):
        if not self.enabled:
            self.start()
            self.ids.toggle.text = 'STOP'
        else:
            self.stop()
            self.ids.toggle.text = 'START'

    def notify(self, dt):
        notification.notify(title='>-------->', message=self.message)           

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.q).T
        this_time = time.time()
        pmax = np.abs(points).max()
        if pmax > SHOT_THRESH and (this_time- self.shot_time) > 4:
            self.shot_count += 1
            self.shot = pmax
            self.shot_time = this_time
            self.message=f'{datetime.datetime.now()}: shot # {self.shot_count}'
            Clock.schedule_once(self.notify)
            point = Point("arrow").tag('id', self.worker.id).field('shot', self.shot).time(int(self.shot_time*10**9), WritePrecision.NS)
            self.worker.q.put(('point', point))
            self.half_point = this_time + (points.shape[1] / accelerometer.rate * 0.5)

        #delay upload unitl half_point in buffer is reached
        force_update = False
        if self.half_point is not None and this_time > self.half_point:
            force_update = True
            self.half_point = None

        self.update_cnt += 1
        #slow down graph update to lower cpu usage
        if self.update_cnt == GRAPH_RATE or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(5 / POLL_RATE) #freeze graph after shot
            gr = self.ids.graph
            gr.ymax = min(GRAPH_LIMIT, max(1, int(points.max() + 1)))
            gr.ymin = max(-GRAPH_LIMIT, min(int(points.min()-1), gr.ymax-1))
            gr.xmax = points.shape[1]
            gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)
            gr.xlabel = f'Accelerometer {int(accelerometer.rate)} /sec'

            self.px.points = enumerate(points[0])
            self.py.points = enumerate(points[1])
            self.pz.points = enumerate(points[2])

class SecondScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[0, 0, 1, 1])
        self.first_run = True
        self.shot_count = 0
        self.worker = Worker()
        #self.message = 'started'
        #Clock.schedule_once(self.notify)
        self.enabled = False

    def on_enter(self):
        print('on enter')
        self.start()

    def on_exit(self):
        print('on exit')
        self.stop()

    def start(self):
        print('start')
        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        self.update_cnt = 0
        self.half_point = None
        self.shot_time = 0
        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True

    def stop(self):
        print('stop')
        Clock.unschedule(self.get_value)
        self.enabled = False

    def on_press(self):
        if not self.enabled:
            self.start()
            self.ids.toggle.text = 'STOP'
        else:
            self.stop()
            self.ids.toggle.text = 'START'

    def notify(self, dt):
        notification.notify(title='>-------->', message=self.message)           

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.mag_q).T
            acc_points  = np.array(accelerometer.q).T
        this_time = time.time()
        pmax = np.abs(acc_points).max()
        if pmax > SHOT_THRESH and (this_time- self.shot_time) > 4:
            self.shot_count += 1
            self.shot = pmax
            self.shot_time = this_time
            self.message=f'{datetime.datetime.now()}: shot # {self.shot_count}'
            Clock.schedule_once(self.notify)
            point = Point("arrow").tag('id', self.worker.id).field('shot', self.shot).time(int(self.shot_time*10**9), WritePrecision.NS)
            self.worker.q.put(('point', point))
            self.half_point = this_time + (points.shape[1] / accelerometer.rate * 0.5)

        #delay upload unitl half_point in buffer is reached
        force_update = False
        if self.half_point is not None and this_time > self.half_point:
            force_update = True
            self.half_point = None

        self.update_cnt += 1
        #slow down graph update to lower cpu usage
        if self.update_cnt == GRAPH_RATE or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(5 / POLL_RATE) #freeze graph after shot
            gr = self.ids.graph
            gr.ymax = min(GRAPH_LIMIT, max(1, int(points.max() + 1)))
            gr.ymin = max(-GRAPH_LIMIT, min(int(points.min()-1), gr.ymax-1))
            gr.xmax = points.shape[1]
            gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)
            gr.xlabel = f'Orientation {int(accelerometer.mag_rate)} /sec'

            self.px.points = enumerate(points[0])
            self.py.points = enumerate(points[1])
            self.pz.points = enumerate(points[2])


class SmartBow(App): 
    def build(self): 
        Builder.load_file("look.kv")
        self.screen = Builder.load_file('look.kv')
        sm = self.screen.ids.sm
        self.main = MainScreen(name='main')
        sm.add_widget(self.main)
        self.screen2 = SecondScreen(name='secondscreen')
        sm.add_widget(self.screen2)
        #sm.current = 'main'
        return self.screen

    def on_resume(self):
        self.lockscreen.set()
        accelerometer.enable()
        return True

    def on_pause(self):
        self.lockscreen.unset()
        accelerometer.disable()
        return True

    def on_start(self):
        self.lockscreen = LockScreen()
        self.lockscreen.set()
        accelerometer.enable()

    def on_stop(self):
        accelerometer.disable()
        return True

if __name__ == "__main__":
    SmartBow().run()     
