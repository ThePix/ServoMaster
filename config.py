ON_LINE = False                 # Set to False to test without connecting to I2C
QUIT_WITHOUT_CONFIRM = True     # Set to True to skip the confirmation when quitting
REPORT_SERVO_SWITCHING = True   # If True requests to change servos is logged to console
TIME_FACTOR = 10.0              # Globally control servo speed
NUMBER_OF_ROWS = 26             # Show this number of rows in the GUI
INCREMENT = 10                  # Jump this number of rows in the GUI
DESC_WIDTH = 24                 # The description for servos can be this long
ANGLE_ADJUST = 5                # Up/down buttons change the angle this much
SHUTDOWN_AT = 30                # Turn off RPi when battery drops below this
SLEEP = 0.001                   # Sleep for this many seconds at the end of each loop
START_CENTRED = False           # Servos go to the off position at turn on unless this is true
TITLE = 'My Example Layout'     # Appears on the main window

# The rest are all for track plan
SHOW_TRACKPLAN = True
SHOW_GRID = True
LINE_WIDTH = 4
WIDTH = 800
HEIGHT = 200
X_SCALE = 50
Y_SCALE = 10
X_OFFSET = 150
Y_OFFSET = 50
X_MIRROR = True
Y_MIRROR = True
POINT_COLOUR = 'green'
LINE_COLOUR = 'blue'