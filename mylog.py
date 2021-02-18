import sys, os
#os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ["KIVY_NO_FILELOG"] = "1"
from kivy.logger import Logger as log
from kivy.logger import LogFile
import logging
from influxdb_client import Point, WritePrecision, rest
import urllib3
class MyLogFile(LogFile):
    def init(self, channel, func):
        self.buffer = ''
        self.func = func
        self.channel = channel
    def write(self, s):
        if s == '\n':
            self.flush()
        else:
            self.buffer += s
    def flush(self):
        if len(self.buffer):
            self.func(self.buffer)
            self.buffer = ''
sys.stderr = MyLogFile('stderr', log.error)


class QueueLogHandler(logging.StreamHandler):
    def __init__(self, q, _id=0, write_api=None, bucket=None, org=None):
        super().__init__(self)
        self.q = q
        self.id = _id
        self.write_api = write_api
        self.bucket = bucket
        self.org = org
    def emit(self, record):
        msg = self.format(record)
        point = Point('log').tag('id', self.id).time(int(record.created * 1e9), WritePrecision.NS).tag('levelno', record.levelno).field('msg', msg)
        if self.write_api is not None:
            try:
                self.write_api.write(self.bucket, self.org, point)
            except (rest.ApiException, urllib3.exceptions.MaxRetryError):
                pass
    def flush(self):
        pass

