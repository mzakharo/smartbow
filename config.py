INFLUX_URL = "https://us-central1-1.gcp.cloud2.influxdata.com" 
INFLUX_TOKEN = 'qpoMEOTPwuMHxwlEggRAn8OSRLyAQIpl179uD2jsB0I9bNCgjbNPSbpwt2b_KDRvq-hynAM0ZZcw6t2-1Hevnw=='
ORG = 'd5c111f1b4fc56c1'
BUCKET = 'main'

POLL_RATE = 0.1 #latency on detection vs cpu/usage
GRAPH_RATE = 5 #   #number of instances of poll rate
GRAPH_LIMIT = 4000  #acceleromter display

DEFAULT_ACCELEROMETER_RATE = 500  #starting guess of acceleromter rate
ACCELEROMETER_BUFFER_LEN = 300 #point buffer length
SHOT_THRESH = 60 #when to detect a shot


