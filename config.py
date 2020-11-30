POLL_RATE = 0.05 #latency on detection vs cpu/usage
GRAPH_RATE = 1 #   # graph update rate as function of POLL_RATE
GRAPH_Y_LIMIT = 150 #acceleromter graph Y-limit

DEFAULT_ACCELEROMETER_RATE = 500  #Galaxy S10
DEFAULT_MAGNETOMETER_RATE = 100 # Galaxy S10

ACCELEROMETER_BUFFER_LEN = 500 #point buffer history length
SHOT_THRESH = 60 #when to detect a shot

POST_SHOT_CAPTURE = 0.3 #percentage of points that will be displayed after shot is detected
GRAPH_FREEZE = 8  #how many seconds to freeze graphs after shot is detected:w


