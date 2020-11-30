import os
os.environ["KIVY_NO_FILELOG"] = "1"

from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot, LinePlot
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.logger import Logger as log

import time
import datetime
import threading
import numpy as np
from plyer import notification
from compat import accelerometer, LockScreen, get_application_dir
from plyer import uniqueid

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from queue import Queue

from urllib3 import Retry
from config import *
import json, pickle

from plyer import storagepath
from plyer.utils import platform

def moving_average(a, n=6):
    ret = np.cumsum(a, dtype=a.dtype)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n

class Worker:
    def __init__(self, config):
        self.today_cache = ''
        self.gen_cache()
        try:
            with open(self.today_cache, 'rb') as f:
                cache = pickle.load(f)
            self.event_count = cache['event_count']
        except Exception as e:
            log.info(f"cache: {e}")

        retries = Retry(connect=5, read=2, redirect=5)
        valid = 'influx_org' in config and 'influx_bucket' in config and 'influx_token' in config and 'influx_url' in config
        if valid:
            log.info(f"influx: {config['influx_url']}")
            self.client = InfluxDBClient(url=config['influx_url'], token=config['influx_token'], timeout=10, retries=retries, enable_gzip=True)
            self.bucket = config['influx_bucket']
            self.org = config['influx_org']
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS) #ASYNC does not work due to sem_ impoementation missing
        else:
            log.info('influx: configuration is invalid')
            self.write_api = None
        self.id = uniqueid.id
        self.q = Queue()
        do_th = threading.Thread(target=self.do, daemon=True)
        do_th.start()

    def gen_cache(self):
        today = str(datetime.date.today())
        #reset event count at 0 on new day
        if today not in self.today_cache:
            self.event_count = 0
            self.today_cache = os.path.join(get_application_dir(), f'cache-{datetime.date.today()}.pickle')

    def register_event(self):
        self.event_count += 1
        with open(self.today_cache, 'wb') as f:
            pickle.dump(dict(event_count=self.event_count), f)

    def process(self):
        cmd, val = self.q.get()
        if cmd == 'event':
            time, magnitude = val
            log.info(f"upload: {cmd} {time} {magnitude}")
            point = Point("event").tag('id', self.id).field('value', magnitude).time(int(time*10**9), WritePrecision.NS)
            if self.write_api is not None:
                self.write_api.write(self.bucket, self.org, point)
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
            log.info(f'upload: {cmd},  {len(send_buffer)}')
            if self.write_api is not None:
                self.write_api.write(self.bucket, self.org, send_buffer)


        else:
            raise Exception("unknown cmd", cmd)

    def do(self):
        while True:
            try:
                self.process()
            except Exception as e:
                log.warning(f'do: {e}')

class CommonScreen(Screen):
    freeze_point = None
    event_time = 0

    def on_press(self):
        if not self.enabled:
            self.start()
            self.ids.toggle.text = 'STOP'
        else:
            self.stop()
            self.ids.toggle.text = 'START'

    def on_enter(self):
        log.info(f'{self.name}: on enter')
        self.start()

    def on_leave(self):
        log.info(f'{self.name}: on leave')
        self.stop()

    def stop(self):
        log.info(f'{self.name}: stop')
        Clock.unschedule(self.get_value)
        self.enabled = False

    def notify(self, dt):
        notification.notify(title='>-------->', message=self.message)           

    def detect_event(self, points, rate):
        self.worker.gen_cache()
        this_time = time.time()
        pmax = np.abs(points).max()
        detected = False
        if pmax > EVENT_THRESH and (this_time - self.event_time) > 4: # 4 sec to handle ringing
            self.worker.register_event()
            self.event = pmax
            self.event_time = this_time
            self.message=f'{datetime.datetime.now().strftime("%a, %H:%M:%S")}: Count # {self.worker.event_count}'
            Clock.schedule_once(self.notify)
            self.worker.q.put(('event', (self.event_time, self.event)))
            self.freeze_point = this_time + (points.shape[1] / rate * POST_EVENT_CAPTURE)
            detected = True

        if self.freeze_point is not None and this_time > self.freeze_point:
            force_update = True
            self.freeze_point = None
        else:
            force_update = False
        return detected, force_update


class AccelerometerScreen(CommonScreen):
    def __init__(self, **kwargs):
        self.worker = kwargs.pop('worker')
        super().__init__(**kwargs)
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[1, 1, 0, 1])
        self.first_run = True
        self.enabled = False

    def start(self):
        log.info(f'{self.name}: start')
        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True
        self.update_cnt = 0

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.q).T
            rate = accelerometer.rate
        detected, force_update = self.detect_event(points, rate)
        self.update_cnt += 1
        if self.update_cnt == GRAPH_RATE or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(GRAPH_FREEZE / POLL_RATE) #freeze graph after event
                self.worker.q.put(('acceleration', (self.event_time, rate, points)))
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
        lw = 2
        self.plots = [  LinePlot(color=[1, 1, 0, 1], line_width=lw),
                        LinePlot(color=[0, 1, 0, 1], line_width=lw),
                        LinePlot(color=[1, 1, 0, 1], line_width=lw),
                        ]
        self.first_run = True
        self.enabled = False
        self.gr_cache = {}

    def start(self):
        log.info(f'{self.name}: start')
        if self.first_run:
            self.first_run = False
            for i, plot in enumerate(self.plots):
                getattr(self.ids, f'graph{i}').add_plot(plot)
        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True
        self.update_cnt = 0

    def get_value(self, dt):
        with accelerometer.lock:
            points  = np.array(accelerometer.mag_q).T * 180 / np.pi
            rate = accelerometer.mag_rate
            acc_rate = accelerometer.rate
            acc_points  = np.array(accelerometer.q).T

        detected, force_update = self.detect_event(acc_points, rate)
        if detected:
            #assume at least 1 second buffer
            fro = -int(accelerometer.mag_rate)
            to =  -int(accelerometer.mag_rate/4)
            self.midpoint = np.median(points[:, fro:to], axis=-1)

        self.update_cnt += 1
        self.ids.label.text =  f'Count #{self.worker.event_count} | Mag {rate:.1f} | Acc {acc_rate:.1f}'
        #slow down graph update to lower cpu usage
        if self.update_cnt == GRAPH_RATE or force_update: 
            self.update_cnt = 0
            if force_update:
                self.update_cnt = -int(GRAPH_FREEZE / POLL_RATE) #freeze graph after event
                self.worker.q.put(('orientation', (self.event_time, rate, points)))
                #self.worker.q.put(('acceleration', (self.event_time, rate, acc_points)))

            for i, plot in enumerate(self.plots):
                gr = getattr(self.ids, f'graph{i}')
                values = points[i]
                if force_update:
                    self.gr_cache[gr] = (gr.ymax, gr.ymin, gr.y_ticks_major)
                    midpoint = int(np.round(self.midpoint[i]))
                    ZOOM_DEGREES = 20
                    if i == 0:  #Azimuth has more noise?
                        ZOOM_DEGREES += ZOOM_DEGREES 
                    gr.ymax = midpoint + ZOOM_DEGREES
                    gr.ymin = midpoint - ZOOM_DEGREES
                    gr.y_ticks_major = int((gr.ymax - gr.ymin) / 10)
                else:
                    cache = self.gr_cache.pop(gr, None)
                    if cache is not None:
                        gr.ymax, gr.ymin, gr.y_ticks_major = cache

                gr.xmax = len(values)
                plot.points = enumerate(values)

class SmartBow(App): 
    def build(self): 
        self.screen = Builder.load_file('look.kv')
        sm = self.screen.ids.sm

        #get config
        config = {}
        path = storagepath.get_external_storage_dir() if platform == 'android' else '.'
        config_file = os.path.join(path, 'smartbow_config.json')
        try:
            if os.path.isfile(config_file):
                with open(config_file, 'r') as f:
                    config = json.loads(f.read())
        except PermissionError:
            log.warning(f'build: no permissions to access {config_file}')

        worker = Worker(config=config)
        screen = OrientationScreen(name='orientation_screen', worker=worker)
        sm.add_widget(screen)
        screen = AccelerometerScreen(name='accelerometer_screen', worker=worker)
        sm.add_widget(screen)


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

    if platform == 'android':
        done = 0 
        def callback(a, b):
            global done
            done += 1
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.READ_EXTERNAL_STORAGE], callback=callback)
        while not done:
            time.sleep(0.05)

    SmartBow().run()     
