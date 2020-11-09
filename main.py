from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot
from kivy.clock import Clock

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

#accelerometer threshold detecting shot being fired
SHOT_THRESH = 99
POLL_RATE = 0.1 #latency on detection vs cpu/usage

INFLUX_URL = "https://us-central1-1.gcp.cloud2.influxdata.com" 
INFLUX_TOKEN = 'qpoMEOTPwuMHxwlEggRAn8OSRLyAQIpl179uD2jsB0I9bNCgjbNPSbpwt2b_KDRvq-hynAM0ZZcw6t2-1Hevnw=='
ORG = 'd5c111f1b4fc56c1'
BUCKET = 'main'


class Worker:
    def __init__(self):
        self.client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN)
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


class Logic(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__()
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[0, 0, 1, 1])
        self.first_run = True
        self.shot_count = 0
        self.worker = Worker()

    def start(self):
        print('start')
        accelerometer.enable()

        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        self.update_cnt = 0
        self.half_point = None
        self.shot_time = 0
        Clock.schedule_interval(self.get_value, POLL_RATE)

    def stop(self):
        print('stop')
        Clock.unschedule(self.get_value)
        accelerometer.disable()

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.q).T
        this_time = time.time()
        pmax = np.abs(points).max()
        if pmax > SHOT_THRESH and (this_time- self.shot_time) > 4:
            self.shot_count += 1
            self.shot = pmax
            self.shot_time = this_time
            notification.notify(title='>-------->', message=f'{datetime.datetime.now()}: shot # {self.shot_count}')
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
        if self.update_cnt == 4 or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(5 / POLL_RATE) #freeze graph after shot
            gr = self.ids.graph
            gr.ymax = max(1, int(points.max() + 1))
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
        self.b.start()
        return True

    def on_pause(self):
        self.lockscreen.unset()
        self.b.stop()
        return True

    def on_start(self):
        self.lockscreen = LockScreen()
        self.lockscreen.set()
        self.b.start()

    def on_stop(self):
        self.b.stop()
        return True

if __name__ == "__main__":
    SmartBow().run()     
