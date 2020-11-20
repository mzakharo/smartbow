INFLUX_URL = "https://us-central1-1.gcp.cloud2.influxdata.com" 
INFLUX_TOKEN = 'qpoMEOTPwuMHxwlEggRAn8OSRLyAQIpl179uD2jsB0I9bNCgjbNPSbpwt2b_KDRvq-hynAM0ZZcw6t2-1Hevnw=='
ORG = 'd5c111f1b4fc56c1'
BUCKET = 'main'

POLL_RATE = 0.1 #latency on detection vs cpu/usage
GRAPH_RATE = 2 #   # graph update rate as function of POLL_RATE
GRAPH_Y_LIMIT = 1000

DEFAULT_ACCELEROMETER_RATE = 500  #Galaxy S10
DEFAULT_MAGNETOMETER_RATE = 100 # Galaxy S10

ACCELEROMETER_BUFFER_LEN = 400 #point buffer history length
SHOT_THRESH = 60 #when to detect a shot


