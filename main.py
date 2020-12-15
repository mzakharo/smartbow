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
from compat import sensor_manager, LockScreen, get_application_dir
from plyer import uniqueid

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from queue import Queue

from urllib3 import Retry
from config import *
import json, pickle
import traceback

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
        self.send_buffer = []
        do_th = threading.Thread(target=self.do, daemon=True)
        do_th.start()

    def gen_cache(self):
        today = str(datetime.date.today())
        #reset event count at 0 on new day
        if today not in self.today_cache:
            self.event_count = 0
            self.today_cache = os.path.join(get_application_dir(), f'cache-{today}.pickle')

    def register_event(self):
        self.event_count += 1
        with open(self.today_cache, 'wb') as f:
            pickle.dump(dict(event_count=self.event_count), f)

    def process(self):
        cmd, val = self.q.get()
        if cmd in ['event', 'std']:
            time, d = val
            log.info(f'{cmd}: time: {time}, data: {d}')
            for field, value in d.items():
                point = Point(cmd).tag('id', self.id).field(field, value).time(time, WritePrecision.NS)
                self.send_buffer.append(point)
        elif cmd in ['orientation', 'acceleration']:
            event_time, event_time_idx, buf, time = val
            points = buf[:3]
            log.info(f'{cmd}: time: {event_time}, buffer time: {time[event_time_idx]}, idx: {event_time_idx}')
            time -= time[event_time_idx] #center around event time
            time += event_time  #add epoch
            num_points = points.shape[1]
            for i in range(num_points):
                values = points[:, i]
                for idx, value in enumerate(values):
                    point = Point(cmd).tag('id', self.id).tag('idx', idx).field('value', value).time(time[i], WritePrecision.NS)
                    self.send_buffer.append(point)
        elif cmd == 'flush':
            if self.write_api is not None:
                log.info(f'{cmd}: {len(self.send_buffer)}')
                self.write_api.write(self.bucket, self.org, self.send_buffer)
            self.send_buffer = []
        else:
            raise Exception("unknown cmd", cmd)


    def do(self):
        while True:
            try:
                self.process()
            except Exception as e:
                log.warning(f'do: {e}')
                traceback.print_exc() 


class CommonScreen(Screen):
    event_time = 0
    accuracy_lookup = {3:'H', 2: 'M', 1:'L'}

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

    def detect_event(self, this_time_ns, points, points_t):
        self.worker.gen_cache()
        pmax_a = np.abs(points).max(axis=0)
        pmax_i = np.argmax(pmax_a)
        pmax = pmax_a[pmax_i]
        if pmax > EVENT_THRESH and (this_time_ns - self.event_time) > 4 * 1e9: # 4 sec to handle ringing
            self.worker.register_event()
            self.event_time = np.int64(this_time_ns)
            self.event_time_idx = pmax_i
            self.message=f'{datetime.datetime.fromtimestamp(this_time_ns / 1e9).strftime("%a, %H:%M:%S")}: Count # {self.worker.event_count}'
            Clock.schedule_once(self.notify)
            self.worker.q.put(('event', (self.event_time, dict(value=pmax))))
            self.worker.q.put(('acceleration', (self.event_time, self.event_time_idx, points, points_t)))
            detected = True
        else:
            detected = False

        return detected


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
        this_time_ns = time.time_ns()

        snsr = sensor_manager.acc
        with snsr.lock:
            points = np.array(snsr.q).T
            points_t = np.array(snsr.tq, dtype=np.int64)
        detected = self.detect_event(this_time_ns, points, points_t)
        if detected:
            self.worker.q.put(('flush',None))

        self.update_cnt += 1
        if self.update_cnt == GRAPH_DRAW_EVERY_FRAMES or detected:
            self.update_cnt = 0
            if detected:
                self.update_cnt = -int(GRAPH_FREEZE / POLL_RATE) #freeze graph after event
            gr = self.ids.graph
            gr.ymax = min(ACCELEROMETER_Y_LIMIT, max(1, int(points.max() + 1)))
            gr.ymin = max(-ACCELEROMETER_Y_LIMIT, min(int(points.min()-1), gr.ymax-1))
            gr.xmax = points.shape[1]
            gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)
            gr.xlabel = f'Accelerometer {int(snsr.rate)}/sec. Accuracy: {self.accuracy_lookup.get(snsr.accuracy,"?")}'
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
        self.labels = ['Azimuth', 'Pitch', 'Roll']

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
        this_time_ns = time.time_ns()

        snsr = sensor_manager.acc
        with snsr.lock:
            acc_points  = np.array(snsr.q).T
            acc_points_t = np.array(snsr.tq, dtype=np.int64)

        detected = self.detect_event(this_time_ns, acc_points, acc_points_t)

        snsr = sensor_manager.ori
        with snsr.lock:
            points = np.degrees(np.array(snsr.q).T)
            points_t = np.array(snsr.tq, dtype=np.int64)


        if detected:
            event_time_idx = np.argmax(points_t >= acc_points_t[self.event_time_idx])

            # remove  a few samples that may have been contaminated when the arrow fired
            point_extra = 3
            if event_time_idx == 0: #if we cant match
                event_time_idx = len(points_t) - 1 - point_extra
            else:
                event_time_idx -= point_extra
            event = {self.labels[i] : v for i, v in enumerate(points[:, event_time_idx])}
            self.worker.q.put(('event', (self.event_time, event)))
            self.worker.q.put(('orientation', (self.event_time, event_time_idx, points, points_t)))
            points = points[:, :event_time_idx + 1] #trim for graph freeze

        std_points = max(int(snsr.rate/2), 10) #get about 500ms worth of points to determine stability

        std = np.std(points[:, -std_points:], axis=-1) * 10 #multiply by 10x to help visualize

        # azimuth has larger std
        azimuth_mult = 4
        std[0] /=  azimuth_mult

        if detected:
            event = {self.labels[i] : v for i, v in enumerate(std)}
            self.worker.q.put(('std', (self.event_time, event)))
            self.worker.q.put(('flush', None))

        self.update_cnt += 1
        self.ids.label.text =  f'#{self.worker.event_count} | rate:{snsr.rate:.1f}@{self.accuracy_lookup.get(snsr.accuracy,"?")}'

        if self.update_cnt == GRAPH_DRAW_EVERY_FRAMES or detected: 
            self.update_cnt = 0

            if detected:
                self.update_cnt = -int(GRAPH_FREEZE / POLL_RATE) #freeze graph after event

            x = 1
            mins = [int(x * azimuth_mult), x, x]
            for i, plot in enumerate(self.plots):
                gr = getattr(self.ids, f'graph{i}')
                values = points[i]
                midpoint = values[-1]

                high = np.max(values)
                low = np.min(values)

                #make sure we can fit the smallest and largest value on the graph
                span = max(max((high - midpoint), (midpoint - low)), mins[i])
                #ymax candidate
                cand = int(np.ceil(midpoint + span))
                #dont resize down unless we reach a threshold
                if cand > gr.ymax or abs(gr.ymax - cand) > mins[i]:
                    gr.ymax = cand
                #ymin candidate
                cand =  int(np.floor(midpoint - span))
                #dont resize down unless we reach a threshold
                if cand < gr.ymin or abs(gr.ymin - cand) > mins[i]:
                   gr.ymin =  cand

                gr.y_ticks_major = (gr.ymax - gr.ymin) / 5
                gr.xlabel = f'{self.labels[i]} @ {midpoint:.1f} | std: {std[i]:.1f}'

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
        sensor_manager.enable()
        return True

    def on_pause(self):
        self.lockscreen.unset()
        sensor_manager.disable()
        return True

    def on_start(self):
        self.lockscreen = LockScreen()
        self.lockscreen.set()
        sensor_manager.enable()

    def on_stop(self):
        sensor_manager.disable()
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
