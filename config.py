ON_LINE = False                  # Set to False to test without connecting to I2C
QUIT_WITHOUT_CONFIRM = True     # Set to True to skip the confirmation when quitting
REPORT_SERVO_SWITCHING = True   # If True requests to change servos is logged to console
TIME_FACTOR = 4.0               # Globally control servo speed; if a servo has a speed of 1000, this is the number of seconds it will take
NUMBER_OF_ROWS = 28             # Show this number of rows in the GUI
INCREMENT = 20                  # Jump this number of rows in the GUI
START_CENTRED = False           # Servos go to the off position at turn on unless this is true
TITLE = 'Conderbridge'          # Appears on the main window
SUPPRESS_WARNINGS = True        # Do not warn if a serno has no LED or button
DESC_WIDTH = 24                 # The description for servos can be this long
ANGLE_ADJUST = 5                # Up/down buttons change the angle this much
SLEEP = 0.001                   # Sleep for this many seconds at the end of each loop

ON_BATTERY = -200               # When shunt current, in mA, is below this, the RPi is assumed to be on battery
CHARGING = 200                  # When shunt current, in mA, is above this, the RPi is assumed to be charging
SHUTDOWN_VOLTAGE = 8.2          # When voltage drops below this, shut down the RPi
SHUTDOWN_FILE = '/home/f2andy/servo_shutdown.sh'


# The rest are all for track plan
SHOW_TRACKPLAN = True
SHOW_GRID = True
LINE_WIDTH = 4
WIDTH = 850
HEIGHT = 480
X_SCALE = 50
Y_SCALE = 10
X_OFFSET = 0
Y_OFFSET = 0
X_MIRROR = False
Y_MIRROR = False
POINT_COLOUR = 'green'
LINE_COLOUR = 'blue'
LEFT_CLICK_ONLY = True
