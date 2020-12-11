
EVENT_THRESH = 60 #when to detect an event
POLL_RATE = 0.10 #latency on detection vs cpu/usage

GRAPH_DRAW_EVERY_FRAMES = 3 # skip frames, increase on older/slower devices
GRAPH_FREEZE = 8  #how many seconds to freeze graphs after shot is detected:w
ACCELEROMETER_Y_LIMIT = 150 #acceleromter graph Y-limit

SENSOR_RATIO = 5 #Galaxy S10
DEFAULT_MAGNETOMETER_RATE = 100 # Galaxy S10
DEFAULT_ACCELEROMETER_RATE =  int(100 * SENSOR_RATIO)
ORIENTATION_BUFFER_LEN = 200 #point buffer history length
ACCELEROMETER_BUFFER_LEN = int(ORIENTATION_BUFFER_LEN* SENSOR_RATIO)

