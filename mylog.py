import sys, os
#os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ["KIVY_NO_FILELOG"] = "1"
from kivy.logger import Logger as log
from kivy.logger import LogFile
import logging
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
    def __init__(self, q):
        super().__init__(self)
        self.q = q
    def emit(self, record):
        msg = self.format(record)
        log = dict(created=record.created,msg=msg,levelno=record.levelno)
        self.q.put(('log', log))
    def flush(self):
        pass

_logger = logging.getLogger(__name__)
_logger.disabled = True
