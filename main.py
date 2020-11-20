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
        elif cmd in ['orientation', 'acceleration']:
            start_time, rate, points = val
            num_points = points.shape[1]
            send_buffer = []
            for i in range(num_points):
                values = points[:, i]
                for idx, value in enumerate(values):
                    point = Point(cmd).tag('id', self.id).tag('idx', idx).field('value', value)
                    point.time(int((start_time + (i / rate ))*10**9), WritePrecision.NS)
                    send_buffer.append(point)
            print('send_buffer')
            self.write_api.write(BUCKET, ORG, send_buffer)


        else:
            raise Exception("unknown cmd", cmd)

    def do(self):
        while True:
            try:
                self.process()
            except Exception as e:
                print(e)

class CommonScreen(Screen):
    shot_count = 0
    update_cnt = 0
    freeze_point = None
    shot_time = 0

    def detect_shot(self, points, rate):
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
            self.freeze_point = this_time + (points.shape[1] / rate * 0.7)

        if self.freeze_point is not None and this_time > self.freeze_point:
            force_update = True
            self.freeze_point = None
        else:
            force_update = False

    def on_press(self):
        if not self.enabled:
            self.start()
            self.ids.toggle.text = 'STOP'
        else:
            self.stop()
            self.ids.toggle.text = 'START'

    def on_enter(self):
        print(self.name, 'on enter')
        self.start()

    def on_exit(self):
        print(self.name, 'on exit')
        self.stop()

    def stop(self):
        print(self.name, 'stop')
        Clock.unschedule(self.get_value)
        self.enabled = False



    def notify(self, dt):
        notification.notify(title='>-------->', message=self.message)           

class MainScreen(CommonScreen):
    def __init__(self, **kwargs):
        self.worker = kwargs.pop('worker')
        super().__init__(**kwargs)
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[0, 0, 1, 1])
        self.first_run = True
        self.enabled = False

    def start(self):
        print(self.name, 'start')
        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.q).T
            rate = accelerometer.rate
        force_update = self.detect_shot(points, rate)
        self.update_cnt += 1
        if self.update_cnt == GRAPH_RATE or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(10 / POLL_RATE) #freeze graph after shot
                self.worker.q.put(('acceleration', (self.shot_time, rate, points)))
            gr = self.ids.graph
            gr.ymax = min(GRAPH_Y_LIMIT, max(1, int(points.max() + 1)))
            gr.ymin = max(-GRAPH_Y_LIMIT, min(int(points.min()-1), gr.ymax-1))
            gr.xmax = points.shape[1]
            gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)
            gr.xlabel = f'Accelerometer {int(rate)} /sec'
            self.px.points = enumerate(points[0])
            self.py.points = enumerate(points[1])
            self.pz.points = enumerate(points[2])


class OrientationScreen(CommonScreen):

    def __init__(self, **kwargs):
        self.worker = kwargs.pop('worker')
        super().__init__(**kwargs)
        self.plots = [  MeshLinePlot(color=[1, 0, 0, 1]),
                        MeshLinePlot(color=[0, 1, 0, 1]),
                        MeshLinePlot(color=[0, 0, 1, 1]),
                        ]
        self.first_run = True
        self.enabled = False

    def start(self):
        print(self.name, 'start')
        if self.first_run:
            self.first_run = False
            for i, plot in enumerate(self.plots):
                getattr(self.ids, f'graph{i}').add_plot(plot)
        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.mag_q).T
            rate = accelerometer.mag_rate
            acc_points  = np.array(accelerometer.q).T

        force_update = self.detect_shot(acc_points, rate)

        self.update_cnt += 1
        #slow down graph update to lower cpu usage
        if self.update_cnt == GRAPH_RATE or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(10 / POLL_RATE) #freeze graph after shot
                self.worker.q.put(('orientation', (self.shot_time, rate, points)))
            labels = ['x', 'y', 'z']
            for i, plot in enumerate(self.plots):
                gr = getattr(self.ids, f'graph{i}')
                values = points[i] * 100
                gr.ymax = int(min(GRAPH_Y_LIMIT, values.max()))
                gr.ymin = int(max(-GRAPH_Y_LIMIT, min(values.min(), gr.ymax-1)))
                gr.xmax = len(values)
                gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)
                gr.xlabel = f'{labels[i]} : {int(rate)} /sec'
                plot.points = enumerate(values)

class SmartBow(App): 
    def build(self): 
        Builder.load_file("look.kv")
        self.screen = Builder.load_file('look.kv')
        sm = self.screen.ids.sm
        worker = Worker()
        self.main = MainScreen(name='main', worker=worker)
        sm.add_widget(self.main)
        self.screen2 = OrientationScreen(name='orientation_screen', worker=worker)
        sm.add_widget(self.screen2)
        sm.current = 'orientation_screen'
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
