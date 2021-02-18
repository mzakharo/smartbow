EVENT_THRESH = 45 #when to detect an event
STD_MAX = 15 #stdev above which we skip the event

POLL_RATE = 0.1 #latency on detection vs cpu/usage

GRAPH_DRAW_EVERY_FRAMES = 1 # skip frames, increase on older/slower devices
GRAPH_FREEZE = 4  #how many seconds to freeze graphs after shot is detected:w
ACCELEROMETER_Y_LIMIT = 150 #acceleromter graph Y-limit

#some defaults, based on Galaxy S10
DEFAULT_ACCELEROMETER_RATE = 500
DEFAULT_ORIENTATION_RATE = 100

#to taste
ACCELEROMETER_BUFFER_LEN = 400 
ORIENTATION_BUFFER_LEN =  200

STD_WINDOW_MS = 250  #window for calculating std

RAW_MAG = False #use raw magnetometer for orientation sensing
SMALLQ_BUFFER_LEN = 10 #how much of accelerometer to buffer


