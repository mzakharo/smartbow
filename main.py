from mylog import log, QueueLogHandler, logging
from kivy.uix.label import Label 
from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import MeshLinePlot, LinePlot
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen

from kivymd.uix.snackbar import Snackbar
from kivymd.uix.list import OneLineListItem, MDList
from kivymd.uix.navigationdrawer import NavigationLayout
from kivymd.uix.navigationdrawer import MDNavigationDrawer

from kivymd.uix.label import MDLabel
from kivymd.theming import ThemableBehavior

from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty
from kivymd.app import MDApp


import os
import time
import datetime
import threading
import numpy as np
from compat import sensor_manager, LockScreen, get_application_dir, notification
from plyer import uniqueid

import influxdb_client
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
        self.q = Queue()
        self.id = uniqueid.id
        self.write_api = None
        self.client = None

        self.today_cache = ''
        self.gen_cache()
        try:
            with open(self.today_cache, 'rb') as f:
                cache = pickle.load(f)
            self.event_count = cache['event_count']
        except Exception as e:
            log.debug(f"cache: {e}")

        retries = Retry(connect=5, read=2, redirect=5)
        valid = 'influx_org' in config and 'influx_bucket' in config and 'influx_token' in config and 'influx_url' in config
        if valid:
            log.debug(f"influx: {config['influx_url']}")
            self.client = InfluxDBClient(url=config['influx_url'], token=config['influx_token'], timeout=10, retries=retries, enable_gzip=True)
            self.bucket = config['influx_bucket']
            self.org = config['influx_org']
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS) #ASYNC does not work due to sem_ impoementation missing

            l = QueueLogHandler(self.q, self.id, self.write_api, self.bucket, self.org)
            formatter = logging.Formatter('%(filename)s-%(funcName)s-L%(lineno)d : %(message)s')
            l.setFormatter(formatter)
            l.setLevel(logging.INFO)
            log.addHandler(l)
        else:
            log.info('influx: configuration is invalid')


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
            log.debug(f'{cmd}: time: {time}, data: {d}')
            for field, value in d.items():
                point = Point(cmd).tag('id', self.id).field(field, value).time(time, WritePrecision.NS)
                self.send_buffer.append(point)
        elif cmd in ['orientation', 'acceleration']:
            event_time, event_time_buf, points, time = val
            log.debug(f'{cmd}: time: {event_time}, buffer time: {event_time_buf}')
            time -= event_time_buf #center around event time
            time += event_time  #add epoch
            for i in range(points.shape[1]):
                values = points[:, i]
                for idx, value in enumerate(values):
                    point = Point(cmd).tag('id', self.id).tag('idx', idx).field('value', value).time(time[i], WritePrecision.NS)
                    self.send_buffer.append(point)
        elif cmd == 'flush':
            if self.write_api is not None:
                log.debug(f'{cmd}: {len(self.send_buffer)}')
                self.write_api.write(self.bucket, self.org, self.send_buffer)
            self.send_buffer = []
        elif cmd == 'log':
            point = Point(cmd).tag('id', self.id).time(int(val['created'] * 1e9), WritePrecision.NS).tag('levelno', val['levelno']).field('msg', val['msg'])
            if self.write_api is not None:
                try:
                    self.write_api.write(self.bucket, self.org, point)
                except influxdb_client.rest.ApiException:
                    pass # ignore any write errors, or we will get into crazy loop trying to add errors and log them here
        else:
            raise Exception("unknown cmd", cmd)


    def do(self):
        while True:
            try:
                self.process()
            except Exception as e:
                log.warning(f'do: {e}')
    def stop(self):
        if self.client is not None:
            self.client.close()
            self.client = None


class CommonScreen(Screen):
    event_time = 0
    update_cnt = 0
    accuracy_lookup = {3:'High', 2: 'Med', 1:'Low'}
    labels =    ['Azimuth', 'Pitch', 'Roll']
    #each axis has a different resolution
    resolution_adjust = [8, 2, 2]

    def on_press(self):
        if not self.enabled:
            self.start()
            self.ids.toggle.text = 'STOP'
        else:
            self.stop()
            self.ids.toggle.text = 'START'

    def on_enter(self):
        log.debug(f'{self.name}: on enter')
        self.start()

    def on_leave(self):
        log.debug(f'{self.name}: on leave')
        self.stop()

    def stop(self):
        log.debug(f'{self.name}: stop')
        Clock.unschedule(self.get_value)
        self.enabled = False

    def notify(self, dt):
        notification.notify(title='>-------->', message=self.message)           

    def detect_event(self, this_time_ns, points, points_t):
        self.worker.gen_cache()
        pmax_a = np.abs(points).max(axis=0)
        pmax_i = np.argmax(pmax_a)
        pmax = pmax_a[pmax_i]
        if pmax > EVENT_THRESH and (this_time_ns - self.event_time) > GRAPH_FREEZE * 1e9: # 4 sec to handle ringing
            self.event_time = np.int64(this_time_ns)
            self.event_time_idx = pmax_i
            self.event_value = pmax
            detected = True
        else:
            detected = False

        return detected
    
    def send_event(self, points, points_t):
        self.worker.register_event()
        self.message=f'# {self.worker.event_count}'
        Clock.schedule_once(self.notify)
        self.worker.q.put(('event', (self.event_time, dict(value=self.event_value))))
        self.worker.q.put(('acceleration', (self.event_time, points_t[self.event_time_idx], points, points_t)))


    def get_value(self):
        this_time_ns = time.time_ns()

        snsr = sensor_manager.acc
        with snsr.lock:
            acc_points  = np.array(snsr.q).T
            acc_points_t = np.array(snsr.tq, dtype=np.int64)

        snsr = sensor_manager.ori
        with snsr.lock:
            points = np.degrees(np.array(snsr.q).T)
            points_t = np.array(snsr.tq, dtype=np.int64)

        detected = self.detect_event(this_time_ns, acc_points, acc_points_t)

        if detected:
            acc_time = acc_points_t[self.event_time_idx]
            debug = None
            if acc_time > points_t[-1]:
                debug = 'accelerometer in the future'
                event_time_idx = len(points_t) - 1
            else:
                event_time_idx = np.argmax(points_t >= acc_time)
                if event_time_idx == 0:
                    event_time_idx = len(points_t) - 1
                    debug = 'sync failure'
                elif event_time_idx == len(points_t) - 1:
                    debug = 'last match'

            if debug is not None:
                log.warning(f"detect: '{debug}' ori: idx={event_time_idx}/{len(points_t)-1} buf={points_t[-6:]}\nacc_time: {acc_time} acc_idx={self.event_time_idx}/{len(acc_points_t)-1}")

            # remove  a few samples that may have been contaminated with the event TODO: use mcmc or some other method to find transition
            event_time_idx -= 7

            orig_points = points
            orig_points_t = points_t
            points = points[:, :event_time_idx + 1]
            ori_time = points_t[event_time_idx]
            acc_offset = ori_time - acc_time
        
        std_points = max(int(snsr.rate/(1000 / STD_WINDOW_MS)), 10)
        std = np.std(points[:, -std_points:], axis=-1) * 10 # multiply by 10x to help visualize with 1 decimal point float
        std = [std[i] / v for i, v in enumerate(self.resolution_adjust)]

        if detected and all(val <= STD_MAX for val in std):
            self.send_event(acc_points, acc_points_t)
            event = {self.labels[i] : v for i, v in enumerate(points[:, -1])}
            self.worker.q.put(('event', (self.event_time + acc_offset, event)))
            self.worker.q.put(('orientation', (self.event_time, acc_time, orig_points, orig_points_t)))
            event = {self.labels[i] : v for i, v in enumerate(std)}
            self.worker.q.put(('std', (self.event_time + acc_offset, event)))
            self.worker.q.put(('flush', None))

        self.toolbar.title =  f'{self.name} | #{self.worker.event_count} | Data:{snsr.rate:.1f}/sec | {self.accuracy_lookup.get(snsr.accuracy,"?")}'

        self.update_cnt += 1
        if self.update_cnt == GRAPH_DRAW_EVERY_FRAMES or detected: 
            self.update_cnt = 0

            if detected:
                self.update_cnt = -int(GRAPH_FREEZE / POLL_RATE) #freeze graph after event
            return True, acc_points, points, std
        return False, acc_points, points, std


class MainScreen(CommonScreen):
    def __init__(self, **kwargs):
        self.worker = kwargs.pop('worker')
        self.toolbar = kwargs.pop('toolbar')
        super().__init__(**kwargs)

    def start(self):
        log.debug(f'{self.name}: start')
        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.ids.label.text = f'# {self.worker.event_count}'

    def get_value(self, dt):
        draw, _, _, _ = super().get_value()
        if not draw:
            return
        self.ids.label.text = f'# {self.worker.event_count}'


class AccelerometerScreen(CommonScreen):
    def __init__(self, **kwargs):
        self.worker = kwargs.pop('worker')
        self.toolbar = kwargs.pop('toolbar')
        super().__init__(**kwargs)
        self.px = MeshLinePlot(color=[1, 0, 0, 1])
        self.py = MeshLinePlot(color=[0, 1, 0, 1])
        self.pz = MeshLinePlot(color=[1, 1, 0, 1])
        self.first_run = True
        self.enabled = False

    def start(self):
        log.debug(f'{self.name}: start')
        if self.first_run:
            self.first_run = False
            self.ids.graph.add_plot(self.px)
            self.ids.graph.add_plot(self.py)
            self.ids.graph.add_plot(self.pz)

        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True
        self.update_cnt = 0

    def get_value(self, dt):
        draw, points, _, _ = super().get_value()
        if draw:
            gr = self.ids.graph
            gr.ymax = min(ACCELEROMETER_Y_LIMIT, max(1, int(points.max() + 1)))
            gr.ymin = max(-ACCELEROMETER_Y_LIMIT, min(int(points.min()-1), gr.ymax-1))
            gr.xmax = points.shape[1]
            gr.y_ticks_major = max(1 , (gr.ymax - gr.ymin) / 5)
            self.px.points = enumerate(points[0])
            self.py.points = enumerate(points[1])
            self.pz.points = enumerate(points[2])


class OrientationScreen(CommonScreen):

    def __init__(self, **kwargs):
        self.worker = kwargs.pop('worker')
        self.toolbar = kwargs.pop('toolbar')
        super().__init__(**kwargs)
        lw = 2
        self.plots = [  LinePlot(color=[1, 1, 0, 1], line_width=lw),
                        LinePlot(color=[0, 1, 0, 1], line_width=lw),
                        LinePlot(color=[1, 1, 0, 1], line_width=lw),
                        ]
        self.first_run = True
        self.enabled = False

    def start(self):
        log.debug(f'{self.name}: start')
        if self.first_run:
            self.first_run = False
            for i, plot in enumerate(self.plots):
                getattr(self.ids, f'graph{i}').add_plot(plot)
        Clock.schedule_interval(self.get_value, POLL_RATE)
        self.enabled = True
        self.update_cnt = 0

    def get_value(self, dt):
        draw, _, points, std = super().get_value()

        if draw:
            for i, plot in enumerate(self.plots):
                gr = getattr(self.ids, f'graph{i}')
                values = points[i]

                #kivy graph ymax/ymin have to be integers :(
                high = int(np.ceil(np.max(values)))
                low = int(np.floor(np.min(values)))

                #we ensure that graph resolution does not fall beyond limits
                span = abs(high - low)
                res = self.resolution_adjust[i] * 20
                if span  < res:
                    extra = (res - span) // 2
                    if extra == 0:
                        high += 1
                    else:
                        high += extra
                        low -= extra
                #update graph attributes
                gr.ymax = high
                gr.ymin = low
                gr.y_ticks_major = (gr.ymax - gr.ymin) / 5
                gr.xlabel = f'{self.labels[i]} @ {values[-1]:.1f} | std: {std[i]:.1f}'
                gr.xmax = len(values)
                plot.points = enumerate(values)

class ContentNavigationDrawer(BoxLayout):
    screen_manager = ObjectProperty()
    nav_drawer = ObjectProperty()


class SmartBow(MDApp): 
    def build(self): 
        self.worker = None
        self.screen = Builder.load_file('look.kv')
        sm = self.screen.ids.screen_manager
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.theme_style = "Dark"

        #get config
        config = {}
        path = storagepath.get_external_storage_dir() if platform == 'android' else os.path.join(get_application_dir())#, 'config')
        config_file = os.path.join(path, 'smartbow_config.json')
        log.debug(f'config: {config_file}')
        try:
            if os.path.isfile(config_file):
                with open(config_file, 'r') as f:
                    config = json.loads(f.read())
        except PermissionError:
            log.warning(f'build: no permissions to access {config_file}')

        self.worker = Worker(config=config)

        toolbar = self.screen.ids.toolbar
        screen = MainScreen(name='Main', worker=self.worker, toolbar=toolbar)
        sm.add_widget(screen)
        screen = OrientationScreen(name='Ori', worker=self.worker, toolbar=toolbar)
        sm.add_widget(screen)
        screen = AccelerometerScreen(name='Force', worker=self.worker, toolbar=toolbar)
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
        print(self.worker)
        self.lockscreen = LockScreen()
        self.lockscreen.set()
        sensor_manager.enable()

    def on_stop(self):
        sensor_manager.disable()
        if self.worker is not None:
            self.worker.stop()
        return True

if __name__ == "__main__":
    log.setLevel(logging.DEBUG)

    if platform == 'android':
        done = 0 
        def callback(a, b):
            global done
            done += 1
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.READ_EXTERNAL_STORAGE], callback=callback)
        while not done:
            time.sleep(0.05)

    app = SmartBow()
    try:
        app.run()
    except KeyboardInterrupt:
        print('kbhit')
    finally:
        app.on_stop()

