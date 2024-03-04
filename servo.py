"""
ServoMaster
Copyright 2024 Andy joel and Preston&District MRS

See here:
https://github.com/ThePix/ServoMaster/wiki
"""


#################################################################################
# CONFIGURATION CONSTANTS

ON_LINE = False                 # Set to False to test without connecting to I2C
QUIT_WITHOUT_CONFIRM = True     # Set to True to skip the confirmation when quitting
REPORT_SERVO_SWITCHING = True   # If True requests to change servos is logged to console
TIME_FACTOR = 10.0              # Globally control servo speed
NUMBER_OF_ROWS = 10             # Show this number of rows in the GUI
INCREMENT = 5                   # Jump this number of rows in the GUI
DESC_WIDTH = 24                 # The description for servos can be this long
ANGLE_ADJUST = 10               # Up/down buttons change the angle this much
SHUTDOWN_AT = 30                # Turn off RPi when battery drops below this
SLEEP = 0.001                   # Sleep for this many seconds at the end of each loop

#################################################################################
# PYTHON IMPORTS

import time
import re
import sys
import random
import math
from threading import Thread

if ON_LINE:
    # Imports for I2C
    import board
    import digitalio
    import adafruit_pcf8575
    import I2C_LCD_driver
    from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C
    from adafruit_servokit import ServoKit
    import INA219

# Imorts for GUI
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import font, Menu, messagebox, PhotoImage, Toplevel, Scrollbar, TclError
from PIL import Image, ImageTk



#################################################################################

class Servo:
    """
    Represents a servo
    Works in hundredths of degrees internally
    The real servo is identified by board and number
    Has an "on" angle and an "off" angle, which can be either way around
    """

    count = 0  # used to give eaxh one an index number

    def create(lst, s):
        """
        Adds a servo object, given a string.
        The string should consist of an "s" to identify it as a servo
        followed by (all separated with spaces):
           the address - the board number, a dot and the pin number
           the speed
           the off angle
           the on angle
           the descriptor
        """
        md = re.match('s (\\d+)\\.(\\d+),? (\\d+),? (\\d+),? (\\d+),? ?(.*)', s)
        if md:
            servo = Servo(int(md.group(1)), int(md.group(2)), int(md.group(3)), int(md.group(4)), int(md.group(5)), md.group(6))
            lst.append(servo)
            return servo
        else:
            print('ERROR: Badly formatted line for servo: ' + s)
            return None
   
    def __init__(self, _board_no, _pin_no, _speed, _off_angle, _on_angle, _desc=None):
        """
        Constructor. As well as setting the given values, also creates a servo object from the I2C
        board.        
        """
        self.board_no = _board_no
        self.pin_no = _pin_no
        self.speed = _speed
        self.off_angle = _off_angle * 100
        self.target_angle = _off_angle * 100
        self.current_angle = _off_angle * 100
        self.on_angle = _on_angle * 100
        self.desc = _desc
        self.moving = False
        self.on_leds = []
        self.off_leds = []
        self.on_buttons = []
        self.off_buttons = []
        if ON_LINE:
            self.servo = servo_boards[self.board_no].servo[self.pin_no]
            self.servo.angle = _off_angle
        self.turn_on = False
        self.index = Servo.count
        Servo.count += 1
       
    def id(self):
        """ The ID is the 'board.pin'. """
        return f'{self.board_no}.{self.pin_no}'

    def write_to_file(self, f):
        """ Writes not just this servo, but also connected buttons and LEDs. """
        f.write(f'\ns {self.board_no}.{self.pin_no}, {self.speed}, {round(self.off_angle / 100)}, {round(self.on_angle / 100)}, {self.desc}\n')
        for led in self.on_leds:
            f.write(f'l on {led.board_no}.{led.pin_no}\n')
        for led in self.off_leds:
            f.write(f'l off {led.board_no}.{led.pin_no}\n')
        for b in self.on_buttons:
            f.write(f'b on {b.board_no}.{b.pin_no}\n')
        for b in self.off_buttons:
            f.write(f'b off {b.board_no}.{b.pin_no}\n')
       
    def set_widget(self, _widget):
        """
        Set a Label widget that the servo can report its angle to.
        Or set to None to stop it.
        """
        self.widget = _widget
        
    def sanity_check(self):
        """ Check for matching numbers of buttons and LEDS. """
        if len(self.on_leds) == 0:
            print(f'WARNING: Not found any "on" LEDs for servo {self.id()} ({self.desc}).')
        elif len(self.off_leds) != len(self.on_leds):
            print(f'WARNING: Mismatch in the number of "on" and "off" LEDs for servo {self.id()} ({self.desc}).')
        if len(self.on_buttons) == 0:
            print(f'WARNING: Not found any "on" buttons for servo {self.id()} ({self.desc}).')
        elif len(self.off_buttons) != len(self.on_buttons):
            print(f'WARNING: Mismatch in the number of "on" and "off" buttons for servo {self.id()} ({self.desc}).')
       

    def set_led(self, led, turn_on):
        """ Add the given LED to the list of "on" or "off" LEDs. """
        if turn_on:
            self.on_leds.append(led)
        else:
            self.off_leds.append(led)

    def set_button(self, button, turn_on):
        """ Add the given button to the list of "on" or "off" buttons. """
        if turn_on:
            self.on_buttons.append(button)
        else:
            self.off_buttons.append(button)

    def set(self, _turn_on):
        """"
        Set the target angle to the on or off angle, which will cause the servo
        to move to that angle over a few seconds.
        """
        self.target_angle = self.on_angle if _turn_on else self.off_angle
        self.turn_on = _turn_on
        if REPORT_SERVO_SWITCHING:
            state = 'ON' if _turn_on else 'OFF'
            print(f'INFO: Setting servo {self.board_no}.{self.pin_no} ({self.desc}) to {state}')
        
    def set_angle(self, angle):
        """"
        Set the target angle, which will cause the servo
        to move to that angle over a few seconds. Not used in normal running
        but can be accessed from the command line.
        """
        self.target_angle = angle * 100

    def get_target_angle(self):
        """ Gets the angle as a nicely formatted string. """
        return str(round(self.target_angle / 100)) + '°'

    def get_current_angle(self):
        """ Gets the angle as a nicely formatted string. """
        return str(round(self.current_angle / 100)) + '°'

    def get_on_angle(self):
        """ Gets the angle as a nicely formatted string. """
        return str(round(self.on_angle / 100)) + '°'

    def get_off_angle(self):
        """ Gets the angle as a nicely formatted string. """
        return str(round(self.off_angle / 100)) + '°'

    def adjust(self, elapsed):
        """
        Updates the current angle given the elasped time.
        Also decides if LEDs should be changed, and
        updates the current angle on the GUI if widget is set.
        """
        diff = self.current_angle - self.target_angle
        if diff == 0:
            if self.moving:
                self.moving = False
                self.set_leds()
            return False

        if not self.moving:
            # Could do this in set, but prefer here as set can be done repeatedly
            self.moving = True
            self.reset_leds()
        increment = elapsed * self.speed;
        # diff is then capped at that
        if diff > 0:
            if diff > increment:
                diff = increment
            self.current_angle -= diff
        else:
            if diff < increment:
                diff = increment
            self.current_angle += diff
       
        if ON_LINE:
            self.servo.angle = self.current_angle / 100
       
        if self.widget:
            self.widget.config(text=self.get_current_angle())
        return True

    def reset_leds(self):
        """ Turns off all associated LEDs. """
        for led in self.on_leds:
            led.set(False)
        for led in self.off_leds:
            led.set(False)
        
    def set_leds(self):
        """ Turns on correct LEDs. """
        if self.target_angle == self.on_angle:
            for led in self.on_leds:
                led.set(True)
        else:
            for led in self.off_leds:
                led.set(True)



#################################################################################
 
class IOPin:
    """
    Represents an I/O pin, superclass for buttons and LEDs.
    """

    def create(klass, lst, not_lst, letter, s, servos):
        """
        Adds an I/O pin object, given a string
        The string should consist of a "l" (for LED) or "b" (for button) to identify it as such
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        """
        md = re.match(letter + ' (on|off) (\\d+)\\.(\\d+)', s)
        if not md:
            raise Exception('ERROR: Badly formatted line for IOPin: ' + s)
        # get the data from the regex match
        turn_on = md.group(1) == 'on'
        board_no = int(md.group(2))
        pin_no = int(md.group(3))
        # is there already an item of the wrong sort assigned there? if so, that is an error
        item = IOPin.find_in_list(not_lst, board_no, pin_no)
        if item:
            raise Exception(f'ERROR: Trying to set board/pin to something when already something else: {board_no}.{pin_no}')
        # is there already an LED assigned there? if not, we create one
        item = IOPin.find_in_list(lst, board_no, pin_no)
        if not item:
            item = klass(board_no, pin_no)
            lst.append(item)
        # now create links to and from the servo
        item.set_servo(servo, turn_on)
        return item, turn_on

    def servo_list(lst):
        """ Gets a string list, separated by slashes, of servos in the given list. """
        lst2 = []
        for servo in lst:
            lst2.append(servo.id())
        return '/'.join(lst2)

    def find_in_list(lst, board_no, pin_no):
        """
        Gets the first element in the list that matchesboth board and pin,
        or None if none found.
        """
        for el in lst:
            if el.board_no == board_no and el.pin_no == pin_no:
                return el
        return None
        

    def __init__(self, _board_no, _pin_no):
        """ Constructor. """
        self.board_no = _board_no
        self.pin_no = _pin_no
        self.on_servos = []
        self.off_servos = []
       

    def id(self):
        """ The ID is the 'board.pin'. """
        return f'{self.board_no}.{self.pin_no}'

    def list_servos(self, turn_on):
        """ Gets a string list, separated by slashes, of "off" or "on" servos. """
        lst = self.on_servos if turn_on else self.off_servos
        return IOPin.servo_list(lst)

    def set_servo(self, servo, turn_on):
        """ Add the given servo to the "on" or "off" list. """
        if turn_on:
            self.on_servos.append(servo)
        else:
            self.off_servos.append(servo)
            


#################################################################################

class Led(IOPin):
    """
    Represents an LED
    """
    count = 0

    def create(s, servos):
        """
        Adds an Led object, given a string.
        The string should consist of a "l" to identify it
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        Uses IOPin.create to do most of the work
        """
        led, turn_on = IOPin.create(Led, leds, buttons, 'l', s, servos)
        servo.set_led(led, turn_on)


    def __init__(self, _board_no, _pin_no):
        """
        Constructor. Uses the super contructor, but also connects to the I/O board.
        """
        super().__init__(_board_no, _pin_no)
        if ON_LINE:
            self.led = io_boards[self.board_no].get_pin(self.pin_no)
            self.led.switch_to_output(value=True)
        self.index = Led.count
        Led.count += 1
       
    def set(self, value):
        """ Sets the LED on or off. """
        #print(value)
        #print(self.index)
        if ON_LINE:
            self.led.value = not value



#################################################################################

class PButton(IOPin):
    """
    Represents a button.
    """
    count = 0

    def create(s, servos):
        """
        Adds a button object, given a string.
        The string should consist of a "b" to identify it
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        Uses IOPin.create to do most of the work
        """
        button, turn_on = IOPin.create(PButton, buttons, leds, 'b', s, servos)
        servo.set_button(button, turn_on)

    def __init__(self, _board_no, _pin_no):
        """
        Constructor. Uses the super contructor, but also connects to the I/O board.
        """
        super().__init__(_board_no, _pin_no)
        if ON_LINE:
            self.button = io_boards[self.board_no].get_pin(self.pin_no)
            self.button.switch_to_input(pull=digitalio.Pull.UP)
        self.widget = None
        self.index = PButton.count
        PButton.count += 1
 
    def get(self):
        """
        Gets the button state.
        Only access the button state through this as it has exception handling
        to deal with issues (hopefully) and for testing with no I2C connected.
        """
        if not ON_LINE:
            return False
        
        try:
            return not self.button.value
        except OSError:
            print('ERROR: Got an OSError, possibly because I am trying to read a board that does not exist or is faulty?')
            print(f'board={self.board} pin={self.pin}')

    def set_widget(self, widget):
        """
        Set a Label widget that the servo can report its angle to.
        Or set to None.
        """
        self.widget = widget

    def check_state(self):
        """
        Call this every loop to have the button check its state and act appropriately.        
        """
        if self.get():
            for servo in self.on_servos:
                servo.set(True)
            for servo in self.off_servos:
                servo.set(False)
        
        # This seems not to work reliably because widget can get set to None after is is checked
        # The exception handling deals with it... by ignoring it
        if not self.widget:
            return
        try:
            if self.get():
                self.widget.config(text='ON!', foreground='white', background='black')
            else:
                self.widget.config(text='off', background='', foreground='black')
        except (AttributeError, tk.TclError):
            # seems to happen when closing the button window
            print('*')



#################################################################################

class Flasher:
    """
    Represents a flashing LED. The flashing is defined by an initial delay, an on time and an off time. The length of the cycle is on+off.
    Times are in tenths of a second.
    """
    count = 0

    def create(s):
        """
        Adds an I/O pin object, given a string
        The string should consist of a "l" (for LED) or "b" (for button) to identify it as such
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        """
        md = re.match('(f|r) (\\d+)\\.(\\d+),? (\\d+),? (\\d+),? (\\d+)', s)
        if not md:
            raise Exception('ERROR: Badly formatted line for IOPin: ' + s)
        # get the data from the regex match
        board_no = int(md.group(2))
        pin_no = int(md.group(3))
        start = int(md.group(4))
        on = int(md.group(5))
        off = int(md.group(6))
        # is there already an item of the wrong sort assigned there? if so, that is an error
        if IOPin.find_in_list(leds, board_no, pin_no):
            raise Exception(f'ERROR: Trying to set board/pin for flasher, but an indicator LED is already assigned: {board_no}.{pin_no}')
        if IOPin.find_in_list(buttons, board_no, pin_no):
            raise Exception(f'ERROR: Trying to set board/pin for flasher, but a button is already assigned: {board_no}.{pin_no}')
        if IOPin.find_in_list(flashers, board_no, pin_no):
            raise Exception(f'ERROR: Trying to set board/pin for flasher, but another flashing LED is already assigned: {board_no}.{pin_no}')
        if md.group(1) == 'f':
            flashers.append(Flasher(board_no, pin_no, start, on, off))
        else:
            flashers.append(RandomFlasher(board_no, pin_no, start, on, off))


    def __init__(self, _board_no, _pin_no, _start, _on, _off):
        """
        Constructor.
        """
        self.board_no = _board_no
        self.pin_no = _pin_no
        self.start = _start
        self.on = _on
        self.off = _off
        self.state = False
        if ON_LINE:
            self.led = io_boards[self.board_no].get_pin(self.pin_no)
            self.led.switch_to_output(value=True)
        self.index = Flasher.count
        Flasher.count += 1
       
    def id(self):
        """ The ID is the 'board.pin'. """
        return f'{self.board_no}.{self.pin_no}'

    def type_letter(self):
        return 'f'

    def set(self, value):
        """ Sets the LED on or off. """
        #print(f'Flasher {self.id()} setting to {value}')
        self.state = value
        if ON_LINE:
            self.led.value = not value

    def check(self, t):
        """
        Method to run every cycle. T is expected to be a float,
        the number of tenths of a second since the program started.
        """
        #print(t)
        if t < self.start:
            # should be start anyway
            #print('start')
            return
        t2 = (t - self.start) % (self.on + self.off)
        #print(t2)
        if t2 < self.on:
            if not self.state:
                self.set(True)
        else:
            if self.state:
                self.set(False)

    def write_to_file(self, f):
        """ Writes the flasher to file. """
        f.write(f'\n{self.type_letter()} {self.board_no}.{self.pin_no}, {self.start}, {self.on}, {self.off}')
       


#################################################################################

class RandomFlasher(Flasher):
    """
    Sub-class of Flashes that gives random flashing, i.e., both on and
    off are randomly determined each cycle, but will average out to the give values
    more or less.
    """


    def __init__(self, _board_no, _pin_no, _start, _on, _off):
        super().__init__(_board_no, _pin_no, _start, _on, _off)
        self.loop_on = _on
        self.loop_off = _off

    def check(self, t):
        if t < self.start:
            # should be start anyway
            return
        if not self.loop_on:
           # is this used?
           self.loop_on = self.vary(self.on)
           self.cycle_count = 0
        t2 = (t - self.start) % (self.loop_on + self.loop_off)
        #print(t2)
        if t2 < self.loop_on:
            if not self.state:
                self.set(True)
                self.loop_off = self.vary(self.off)
        else:
            if self.state:
                self.set(False)
                self.loop_on = self.vary(self.on)


    def vary(self, n):
        m = round(n/2)
        return m + random.randint(0, m) + random.randint(0, m)

    def type_letter(self):
        return 'r'




#################################################################################

class PatternFlasher(Flasher):
    """
    Sub-class of Flashes that gives a complex flasdhing pattern.
    """
    def create(s):
        """
        Adds an I/O pin object, given a string
        The string should consist of a "l" (for LED) or "b" (for button) to identify it as such
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        """
        md = re.match('p (\\d+)\\.(\\d+),? (\\d+),? ([\\.\\*]+)', s)
        if not md:
            raise Exception('ERROR: Badly formatted line for IOPin: ' + s)
        # get the data from the regex match
        board_no = int(md.group(1))
        pin_no = int(md.group(2))
        start = int(md.group(3))
        pattern = md.group(4)
        # is there already an item of the wrong sort assigned there? if so, that is an error
        if IOPin.find_in_list(leds, board_no, pin_no):
            raise Exception(f'ERROR: Trying to set board/pin for flasher, but an indicator LED is already assigned: {board_no}.{pin_no}')
        if IOPin.find_in_list(buttons, board_no, pin_no):
            raise Exception(f'ERROR: Trying to set board/pin for flasher, but a button is already assigned: {board_no}.{pin_no}')
        if IOPin.find_in_list(flashers, board_no, pin_no):
            raise Exception(f'ERROR: Trying to set board/pin for flasher, but another flashing LED is already assigned: {board_no}.{pin_no}')
        flashers.append(PatternFlasher(board_no, pin_no, start, pattern))


    def __init__(self, _board_no, _pin_no, _start, _pattern):
        super().__init__(_board_no, _pin_no, _start, 0, 0)
        self.pattern = []
        for c in _pattern:
            self.pattern.append(c == '*')

    def check(self, t):
        # to do!!!
        #print(t)
        if t < self.start:
            # should be start anyway
            #print('start')
            return
        t2 = math.floor((t - self.start) % len(self.pattern))
        desired = self.pattern[t2]
        if self.state != desired:
            self.set(desired)


    def vary(self, n):
        m = round(n/2)
        return m + random.randint(0, m) + random.randint(0, m)

    def type_letter(self):
        return 'r'

    def write_to_file(self, f):
        """ Writes the flasher to file. """
        pattern = ''
        for flag in self.pattern:
            pattern += ('*' if flag else '.')
        f.write(f'\np {self.board_no}.{self.pin_no}, {self.start}, {pattern}')



#################################################################################
# INITIALISING

start_time = time.time()
previous_time = start_time

if ON_LINE:
    i2c = board.I2C()  # uses board.SCL and board.SDA
io_boards = []
servo_boards = []
lcd_boards = []
ups_boards = []
def print_lcd(n, s):
    if ON_LINE:
        for i in range(len(lcd_boards)):
            lcd_boards[i].lcd_display_string(s, n)


servos = []
leds = []
buttons = []
flashers = []

request = { 'action':False, 'testing':True}  # User input is done by changing this to request a change
loop_count = 0

window = None

servo_grid_rows = []
button_grid_rows = []
led_grid_rows = []



#################################################################################
# SAVING AND LOADING

def save():
    """
    Saves the configuration to file.
    """
    try:
        with open('servo.txt', 'w', encoding="utf-8") as f:
            # Save the boards
            if ON_LINE:
                for servo_board in servo_boards:
                    f.write(f'S{hex(servo_board._pca.i2c_device.device_address)}\n')
                for io_board in io_boards:
                    f.write(f'IO{hex(io_board.i2c_device.device_address)}\n')
                for lcd_board in lcd_boards:
                    f.write(f'LCD{hex(lcd_board.lcd_device.addr)}\n')
                for usp_board in ups_boards:
                    f.write(f'UPS{hex(usp_board.addr)}\n')
            else:
                for servo_board in servo_boards:
                    f.write(f'S{hex(servo_board.addr)}\n')
                for io_board in io_boards:
                    f.write(f'IO{hex(io_board.addr)}\n')
                for lcd_board in lcd_boards:
                    f.write(f'LCD{hex(lcd_board.addr)}\n')
                for usp_board in ups_boards:
                    f.write(f'UPS{hex(usp_board.addr)}\n')

            # Now save the servos and related data
            for servo in servos:
                servo.write_to_file(f)

            # Now save the servos and related data
            for flasher in flashers:
                flasher.write_to_file(f)
                
        print("INFO: Save successful")
    except Exception as err:
        print('ERROR: Failed to save the configuration file, servo.txt.')
        print(f"Reported: Unexpected {err=}, {type(err)=}")



# We can check devices are connected as they are loaded from file
# so first get a list of addresses on the I2C bus
if ON_LINE:
    i2c_devices = i2c.scan()
    print("INFO: Found I2C devices:", [hex(device_address) for device_address in i2c_devices])
else:
    print("WARNING: Running in off-line mode, not connecting to I2C bus.")


class fake_board:
    def __init__(self, addr):
        self.addr = addr

class fake_usp_board:
    def __init__(self, addr):
        self.addr = addr
    def getBusVoltage_V(self):
        return 7.368
    def getCurrent_mA(self):
        return -327.7

def load_device(line):
    """
    Adds an I2C board, given a string.
    The string should consist of the board type identifier - one or more letters in upper case
    followed directly by the addess in hexadecimal (use lower case letters if required!).
    
    This is in a function of its own so we can readily exit it it a problem is encountered.
    """
    md = re.match('([A-Z]+)(?:0x|)([0-9a-f]+)', line)
    if not md:
        print('ERROR: Badly formatted line: ' + line)
        return
   
    address = int(md.group(2), 16)
    if ON_LINE and not address in i2c_devices:
        print('ERROR: Device not found: ' + line)
        return False                
    if ON_LINE:
        match md.group(1):
            case 'S':
                servo_boards.append(ServoKit(channels=16, address=address))
            case 'IO':
                io_boards.append(adafruit_pcf8575.PCF8575(i2c, address))
            case 'LCD':
                lcd_boards.append(I2C_LCD_driver.lcd())
            case 'UPS':
                ups_boards.append(INA219(addr=address))
            case _:
                print('ERROR: Device code not recognised: ' + line)
    else:
        match md.group(1):
            case 'S':
                servo_boards.append(fake_board(address))
            case 'IO':
                io_boards.append(fake_board(address))
            case 'LCD':
                lcd_boards.append(fake_board(address))
            case 'UPS':
                ups_boards.append(fake_usp_board(address))
            case _:
                print('ERROR: Device code not recognised: ' + line)

try:
    """
    File access can be problematic, so wrap in a try/except block
    """
    with open('servo.txt', encoding="utf-8") as f:
        servo = None
        for line in f:
            if line.isspace():
                continue
            if line[0:1] == 's':
                servo = Servo.create(servos, line)
            elif line[0:1] == 'b':
                PButton.create(line, servo)
            elif line[0:1] == 'l':
                Led.create(line, servo)
            elif line[0:1] == 'f' or line[0:1] == 'r':
                Flasher.create(line)
            elif line[0:1] == 'p':
                PatternFlasher.create(line)
            else:
                load_device(line)
except FileNotFoundError:
    print('ERROR: Failed to open the configuration file, servo.txt.')
    print('Should be a text file in the same directory as this program.')
    print('Not much I can do with it, so giving up...')
    exit()
               
# report how it went for diagostics
print(f"INFO: Found {len(servo_boards)} servo board(s).")
print(f"INFO: Found {len(io_boards)} I/O board(s).")

print(f"INFO: Found {len(lcd_boards)} LCD board(s); sending welcome message.")
print_lcd(1, "Hello P&D MRS!")
print(f"INFO: Found {len(ups_boards)} UPS board(s).")

print(f"INFO: Found {len(servos)} servo(s).")
print(f"INFO: Found {len(buttons)} button(s).")
print(f"INFO: Found {len(leds)} indicator LED(s).")
print(f"INFO: Found {len(flashers)} flashing LED(s).")
for servo in servos:
    servo.sanity_check()


       

#################################################################################
# COMMAND LINE

# For testing it is good to be able to type requests to set the servo, and this function handles that
# It runs in its own thread, and sets the global variable "request" when a request is made
patterns = [
    re.compile("^(exit|quit|x)$", re.IGNORECASE),
    re.compile("^(\\d+) (\\d+)$"),
    re.compile("^(\\d+) on$", re.IGNORECASE),
    re.compile("^(\\d+) off$", re.IGNORECASE),
    re.compile("^l(\\d+) on$", re.IGNORECASE),
    re.compile("^l(\\d+) off$", re.IGNORECASE),
]

def input_loop():
    """
    Gets input from the command line, sets the request object
    for mail loop to deal with.
    """
    while not request['action'] == 'terminate':
        s = input()
        print("Got: " + s)
        mds = []
        for pattern in patterns:
            mds.append(pattern.match(s))
        if mds[0]:
            request['action'] = 'terminate'
        elif mds[1]:
            request['action'] = 'angle'
            request['servo'] = int(mds[1].group(1))
            request['angle'] = int(mds[1].group(2))
        elif mds[2]:
            print('servo on')
            request['action'] = 'on'
            request['servo'] = int(mds[2].group(1))
        elif mds[3]:
            print('servo off')
            request['action'] = 'off'
            request['servo'] = int(mds[3].group(1))
        elif mds[4]:
            print('LED on')
            request['action'] = 'LED on'
            request['servo'] = int(mds[4].group(1))
        elif mds[5]:
            print('LED off')
            request['action'] = 'LED off'
            request['servo'] = int(mds[5].group(1))
        else:
            print("Input commands in the form x y")
   



#################################################################################
# MAIN LOOP

def main_loop():
    """
    Handles time,
    checks if buttons have been pressed,
    responds to requests from the command line/GUI,
    moves servo...
    But most of the work is done elsewhere.
    """
    global previous_time, loop_count
    print('INFO: Starting the main loop.')
    while not request['action'] == 'terminate':
        # HANDLE TIME
        now_time = time.time()
        elapsed = now_time - previous_time
        previous_time = now_time
        increment = TIME_FACTOR * elapsed
        
        # If the GUI is up, then count_label is a Label object
        # and can be updated with the loop count to show it is going
        # and indicate how fast. Cap at a million so no chance of overflow.
        if window and window.count_label:
            try:
                window.count_label.config(text=str(loop_count))
            except tk.TclError:
                # Seems to happen when quiting, I guess if the label is destroyed after the test
                # but part way through the tkinter stuff.
                print('*')
            loop_count += 1
            if loop_count > 999999:
                loop_count = 0
        #else:
        #    print('.', end='')

        #print('one')
        
        # HANDLE UPS
        # Only do this every 100 loops; it is not going to change much
        # Get values from device
        # If below SHUTDOWN_AT% and draining, shutdown
        # Otherwise report to GUI
        if loop_count % 100 == 0 and len(ups_boards) > 0:
            bus_voltage = ups_boards[0].getBusVoltage_V()             # voltage on V- (load side)
            # shunt_voltage = ups_boards[0].getShuntVoltage_mV() / 1000 # voltage between V+ and V- across the shunt
            current = ups_boards[0].getCurrent_mA()                   # current in mA
            # power = ups_boards[0].getPower_W()                        # power in W
            percent_remaining = (bus_voltage - 6)/2.4*100
            if percent_remaining < SHUTDOWN_AT and current < 0:
                print("Battery supply about to expire - shutting down.")
                os.system("sudo shutdown -h now")
            if window and window.power_label:
                try:
                    if current < 0:
                        window.power_label.config(text=f'On batteries, {round(percent_remaining, 2)}% remaining')
                    else:
                        window.power_label.config(text=f'Good; batteries at {round(percent_remaining, 2)}%.')
                except tk.TclError:
                    print('*')
        #print('two')

        # HANDLE INPUTS
        for button in buttons:
            button.check_state()
        #print('three')
           
        # HANDLE INPUT REQUESTS
        if request['action'] == 'angle':
            if request['servo'] >= len(servos):
                print("WARNING: Servo out of range (0-" + str(len(servos)) + ")")
            else:
                servos[request['servo']].set_angle(request['angle'])
            request['action'] = False

        if request['action'] == 'on':
            if request['servo'] >= len(servos):
                print("WARNING: Servo out of range (0-" + str(len(servos)) + ")")
            else:
                servos[request['servo']].set(True)
            request['action'] = False

        if request['action'] == 'off':
            if request['servo'] >= len(servos):
                print("WARNING: Servo out of range (0-" + str(len(servos)) + ")")
            else:
                servos[request['servo']].set(False)
            request['action'] = False

        if request['action'] == 'LED on':
            if request['servo'] >= len(leds):
                print("WARNING: LED out of range (0-" + str(len(leds)) + ")")
            else:
                leds[request['servo']].set(True)
                if REPORT_SERVO_SWITCHING:
                    ident = leds[request['servo']].id()
                    print(f'INFO: LED on {ident}')
            request['action'] = False
        if request['action'] == 'LED off':
            if request['servo'] >= len(leds):
                print("WARNING: LED out of range (0-" + str(len(leds)) + ")")
            else:
                leds[request['servo']].set(False)
                if REPORT_SERVO_SWITCHING:
                    ident = leds[request['servo']].id()
                    print(f'INFO: LED off {ident}')
            request['action'] = False
        if request['action'] == 'all LED on':
            for led in leds:
                led.set(True)
            request['action'] = False
        if request['action'] == 'all LED off':
            for led in leds:
                led.set(False)
            request['action'] = False
        #print('four')


        # HANDLE FLASHERS
        if loop_count % 100 == 10:
            t = (time.time() - start_time) * 10
            for flasher in flashers:
                flasher.check(t)

        #print('five')


        # HANDLE SERVOS
        moving_flag = False;
        for servo in servos:
            if servo.adjust(increment):
                moving_flag = True
        #print('six')

        time.sleep(SLEEP)
        
        #print('seven')
        
        # HANDLE HARD BREAK
        # Connect pins 39 and 40 (Ground and GPIO21) to exit if all else fails

    print("INFO: Main loop terminated.")



#################################################################################
# THREADING
 
# We have three threads, one that does the work, for for the GUI,
# one for the command line.

# The command line is a daemon thread - no need to shutdown gracefully
input_thread = Thread(target = input_loop)
input_thread.daemon = True
input_thread.start()

# The main loop is not a daemon thread, it might be in the middle of doing stuff.
# Not sure if this is an issue, but just in case!
# It has to be stopped by setting request['action'] = 'terminate'
Thread(target = main_loop).start()  #!!!!!

# The GUI is done in the defaut thread; no need to define a new one







######################################################################
# GUI CLASSES


class ButtonsWindow(tk.Toplevel):
    """ 
    Define a special child window that stops buttons trying to update labels in it when it is destroyed.
    More specifically, it sets the widget in the buttons to None, and then tells each row to
    destroy the label. Hopefully the program will then exit gracefully.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def destroy(self):
        for i in range(len(buttons)):
            buttons[i].set_widget(None)        
        for row in button_grid_rows:
            row.destroy_button()
        return super().destroy()


class ServoGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one servo,
    and buttons and labels on the row will change and reflect its state, but
    which servo that is can vary depending on what self.offset is.
    """
    
    """
    def up_button_pressed(self, event):
        ServoGridRow.find_row(event.widget).up_button()
    
    def find_row(widget):
        for row in servo_grid_rows:
            if row.btn_up == widget or row.btn_down == widget or row.btn_on_off == widget:
                return row
    """

    offset = 0

    def offset_plus_10():
        if ServoGridRow.offset > len(servos) - INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        ServoGridRow.offset += INCREMENT
        ServoGridRow.set_offset()

    def offset_minus_10():
        if ServoGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        ServoGridRow.offset -= INCREMENT
        ServoGridRow.set_offset()

    def set_offset():
        for servo in servos:
            servo.set_widget(None)
        for row in servo_grid_rows:
            row.update()

    def headers(img, font):
        """ Set the first row. """
        if img:
            ttk.Label(width=5, font=font, image=img).grid(column=0, row=0)
        ttk.Label(text='ID', width=7, font=font).grid(column=1, row=0)
        ttk.Label(text='Description', width=DESC_WIDTH, font=font).grid(column=2, row=0)
        ttk.Label(text='Switch', font=font).grid(column=3, row=0)
        ttk.Label(text='State', width=10, font=font).grid(column=4, row=0)
        ttk.Label(text='Target', width=10, font=font).grid(column=7, row=0)
        ttk.Label(text='Current', width=10, font=font).grid(column=8, row=0)

    def __init__(self, row, font):
        # When creating, the first servo is 0
        self.row = row             # The row in the table in the GUI
        #self.servo = servos[row]   # The current servo - but can change
        self.lbl_index = ttk.Label(text=str(row), font=font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_id = ttk.Label(text='---', width=7, font=font)
        self.lbl_id.grid(column=1, row=1 + row)

        self.lbl_desc = ttk.Label(text='---', width=DESC_WIDTH, font=font)
        self.lbl_desc.grid(column=2, row=1 + row)

        self.btn_on_off = ttk.Button(text="On/Off")
        self.btn_on_off.grid(column=3, row=1 + row)
        self.btn_on_off.bind("<Button-1>", self.on_off_button)
       
        self.lbl_state = ttk.Label(text='OFF', width=10, font=font)    
        self.lbl_state.grid(column=4, row=1 + row)
       
        self.btn_up = ttk.Button(text="Up")
        self.btn_up.grid(column=5, row=1 + row)
        self.btn_up.bind("<Button-1>", self.up_button)
        self.btn_up.index = row
       
        self.btn_down = ttk.Button(text="Down")
        self.btn_down.grid(column=6, row=1 + row)
        self.btn_down.bind("<Button-1>", self.down_button)
       
        self.lbl_target_angle = ttk.Label(text='---', width=10, font=font)
        self.lbl_target_angle.grid(column=7, row=1 + row)
       
        self.lbl_current_angle = ttk.Label(text='---', width=10, font=font)
        self.lbl_current_angle.grid(column=8, row=1 + row)
        #self.servo.set_widget(self.lbl_current_angle)
        
        self.update()

    def update(self):
        """
        Updates the row for a new servo (or no servo) when offset changes
        """
        if 0 <= (self.row + self.offset) < len(servos):
            self.servo = servos[self.row + self.offset]
            self.lbl_index.config(text=str(self.row + self.offset))
            self.lbl_id.config(text=self.servo.id())
            self.lbl_desc.config(text=self.servo.desc)
            state = 'ON' if self.servo.turn_on else 'OFF'
            self.lbl_state.config(text=state)    
            self.lbl_target_angle.config(text=self.servo.get_target_angle())
            self.lbl_current_angle.config(text=self.servo.get_current_angle())
            #print(f'set widget {self.row} for servo {self.servo.index}')
            self.servo.set_widget(self.lbl_current_angle)
        else:
            self.servo = None
            self.lbl_index.config(text='---')
            self.lbl_id.config(text='---')
            self.lbl_desc.config(text='---')
            self.lbl_state.config(text='---')    
            self.lbl_target_angle.config(text='---')
            self.lbl_current_angle.config(text='---')

    def on_off_button(self, event):
        """ When the On/Off button for this row is pressed. """
        if not self.servo:
            print('BAD INPUT: No servo at row')
            return

        if self.servo.turn_on:
            self.lbl_state.config(text='OFF')
            self.lbl_target_angle.config(text=self.servo.get_off_angle())
            request['action'] = 'off'
            request['servo'] = self.servo.index
        else:
            self.lbl_state.config(text='ON')
            self.lbl_target_angle.config(text=self.servo.get_on_angle())
            request['action'] = 'on'
            request['servo'] = self.servo.index

    def up_button(self, event):
        """ When the Up button for this row is pressed. """
        if not self.servo:
            print('No servo at row')
            return

        if self.servo.turn_on:
            if self.servo.on_angle > 17000 - ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go over 170')
                return
            self.servo.on_angle += ANGLE_ADJUST * 100
           
        else:
            if self.servo.off_angle > 17000 - ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go over 170')
                return
            self.servo.off_angle += ANGLE_ADJUST * 100

        self.servo.target_angle += ANGLE_ADJUST * 100
        self.lbl_target_angle.config(text=self.servo.get_target_angle())

    def down_button(self, event):
        """ When the Down button for this row is pressed. """
        if not self.servo:
            print('No servo at row')
            return

        if self.servo.turn_on:
            if self.servo.on_angle < 1000 + ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go under 10')
                return
            self.servo.on_angle -= ANGLE_ADJUST * 100
           
        else:
            if self.servo.off_angle < 1000 + ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go under 10')
                return
            self.servo.off_angle -= ANGLE_ADJUST * 100

        self.servo.target_angle -= ANGLE_ADJUST * 100
        self.lbl_target_angle.config(text=self.servo.get_target_angle())


class ButtonGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one (real) button,
    and buttons and labels on the row will change and reflect its state, but
    which (real) button that is can vary depending on what offset is.
    """
    
    offset = 0

    def show_buttons():
        newWindow = ButtonsWindow(window)
        newWindow.title('Buttons')
        ButtonGridRow.headers(newWindow)
        for i in range(NUMBER_OF_ROWS):
            button_grid_rows.append(ButtonGridRow(newWindow, i))

    def headers(win):
        """ Set the first row. """
        if img:
            ttk.Label(win, image=window.img, font=window.heading_font).grid(column=0, row=0)
        ttk.Label(win, text='ID', width=5, font=window.heading_font).grid(column=1, row=0)
        ttk.Label(win, text='Off servos', width=20, font=window.heading_font).grid(column=2, row=0)
        ttk.Label(win, text='On servos', width=20, font=window.heading_font).grid(column=3, row=0)
        ttk.Label(win, text='State', font=window.heading_font, width=7).grid(column=4, row=0)

    def offset_plus_10():
        if ButtonGridRow.offset > len(buttons) - INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        ButtonGridRow.offset += INCREMENT
        ButtonGridRow.set_offset()

    def offset_minus_10():
        if ButtonGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        ButtonGridRow.offset -= INCREMENT
        ButtonGridRow.set_offset()


    def set_offset():
        for button in buttons:
            button.set_widget(None)
        for row in button_grid_rows:
            row.update()


    def __init__(self, win, row):
        # When creating, the first button is 0
        self.row = row             # The row in the table in the GUI
        self.lbl_index = ttk.Label(win, text=str(row), font=window.label_font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_desc = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_desc.grid(column=1, row=1 + row, sticky='w')

        self.lbl_off_list = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_off_list.grid(column=2, row=1 + row, sticky='w')

        self.lbl_on_list = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_on_list.grid(column=3, row=1 + row, sticky='w')

        self.lbl_state = ttk.Label(win, text='---', width=7, font=window.label_font)    
        self.lbl_state.grid(column=4, row=1 + row)
        self.update()


    def update(self):
        """
        Updates the row for a new button (or no button) when offset changes
        """
        if 0 <= (self.row + ButtonGridRow.offset) < len(buttons):
            self.button = buttons[self.row + ButtonGridRow.offset]
            self.lbl_index.config(text=str(self.row + ButtonGridRow.offset))
            self.lbl_desc.config(text=self.button.id())
            self.lbl_off_list.config(text=self.button.list_servos(False))
            self.lbl_on_list.config(text=self.button.list_servos(True))
            self.button.set_widget(self.lbl_state)
        else:
            self.button = None
            self.lbl_index.config(text='---')
            self.lbl_desc.config(text='---')
            self.lbl_state.config(text='---')    
            self.lbl_off_list.config(text='---')
            self.lbl_on_list.config(text='---')
            self.lbl_state.config(text='---')
            
    def destroy_button(self):
        self.lbl_state.destroy()


class LedGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one LED,
    and buttons and labels on the row will change and reflect its state, but
    which LED that is can vary depending on what offset is.
    """

    offset = 0


    def show_leds():
        """ Responds to a menu click to show the window for LEDs"""

        newWindow = Toplevel(window)
        newWindow.title('LEDs')
        LedGridRow.headers(newWindow)
        for i in range(NUMBER_OF_ROWS):
            led_grid_rows.append(LedGridRow(newWindow, i))
           
    def all_leds_on():
        """ Responds to a menu click to tirn on all LEDs"""
        request['action'] = 'all LED on'

    def all_leds_off():
        """ Responds to a menu click to tirn off all LEDs"""
        request['action'] = 'all LED off'


    def headers(win):
        """ Set the first row. """
        if img:
            ttk.Label(win, image=window.img, font=window.heading_font).grid(column=0, row=0)
        ttk.Label(win, text='ID', width=5, font=window.heading_font).grid(column=1, row=0)
        ttk.Label(win, text='Off servos', width=20, font=window.heading_font).grid(column=2, row=0)
        ttk.Label(win, text='On servos', width=20, font=window.heading_font).grid(column=3, row=0)

    def offset_plus_10():
        if LedGridRow.offset > len(leds) - INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        LedGridRow.offset += INCREMENT
        LedGridRow.set_offset()

    def offset_minus_10():
        if LedGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        LedGridRow.offset -= INCREMENT
        LedGridRow.set_offset()


    def set_offset():
        for button in buttons:
            button.set_widget(None)
        for row in button_grid_rows:
            row.update()

    def __init__(self, win, row):
        # When creating, the first button is 0
        self.row = row             # The row in the table in the GUI
        self.lbl_index = ttk.Label(win, text=str(row), font=window.label_font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_desc = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_desc.grid(column=1, row=1 + row, sticky='w')

        self.lbl_off_list = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_off_list.grid(column=2, row=1 + row, sticky='w')

        self.lbl_on_list = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_on_list.grid(column=3, row=1 + row, sticky='w')

        self.btn_on = ttk.Button(win, text="On")
        self.btn_on.grid(column=4, row=1 + row)
        self.btn_on.bind("<Button-1>", self.led_on_button)
       
        self.btn_off = ttk.Button(win, text="Off")
        self.btn_off.grid(column=5, row=1 + row)
        self.btn_off.bind("<Button-1>", self.led_off_button)

        self.update()



    def update(self):
        """
        Updates the row for a new led (or no led) when offset changes
        """
        if 0 <= (self.row + LedGridRow.offset) < len(leds):
            self.led = leds[self.row + LedGridRow.offset]
            self.lbl_index.config(text=str(self.row + LedGridRow.offset))
            self.lbl_desc.config(text=self.led.id())
            self.lbl_off_list.config(text=self.led.list_servos(False))
            self.lbl_on_list.config(text=self.led.list_servos(True))
        else:
            self.button = None
            self.lbl_index.config(text='---')
            self.lbl_desc.config(text='---')
            self.lbl_off_list.config(text='---')
            self.lbl_on_list.config(text='---')

    def led_on_button(self, event):
        request['action'] = 'LED on'
        request['servo'] = self.led.index

    def led_off_button(self, event):
        request['action'] = 'LED off'
        request['servo'] = self.led.index


class ServoWindow(tk.Tk):
    def __init__(self, *args, **kwargs):
        
        tk.Tk.__init__(self, *args, **kwargs)  # Note: super() does not work here
        if ON_LINE:
            self.title("P&D MRS ServoMaster")
        else:
            self.title("P&D MRS ServoMaster (off-line)")
            
        self.protocol('WM_DELETE_WINDOW', self.confirm_quit)

        self.heading_font = font.Font(slant="italic")
        self.label_font = font.Font()

        self.create_menubar()
        
        try:
            self.img = Image.open("servo_icon.png")
            self.img = ImageTk.PhotoImage(self.img)
        except FileNotFoundError:
            self.img = None
            print('WARNING: Failed to find icon file, "servo_icon.png", but carrying on regardless!')

        # The widgets that do the work
        ServoGridRow.headers(self.img, self.heading_font)
        for i in range(NUMBER_OF_ROWS):
            servo_grid_rows.append(ServoGridRow(i, self.label_font))

        ttk.Label(text='Power supply:', font=self.heading_font).grid(column=1, row=NUMBER_OF_ROWS + 1)
        self.power_label = ttk.Label(text='---', font=self.heading_font)
        self.power_label.grid(column=2, row=NUMBER_OF_ROWS + 1)

        ttk.Label(text='Cycle count:', font=self.heading_font).grid(column=6, row=NUMBER_OF_ROWS + 1)
        self.count_label = ttk.Label(text='---', font=self.heading_font)
        self.count_label.grid(column=7, row=NUMBER_OF_ROWS + 1)



    def create_menubar(self):
        menu_font = font.Font(size=10)
        menubar = Menu(self)
        filemenu = Menu(menubar, tearoff=0, font=menu_font)
        filemenu.add_command(label="Save", command=save, font=menu_font)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.confirm_quit, font=menu_font)
        menubar.add_cascade(label="File", menu=filemenu, font=menu_font)

        servosmenu = Menu(menubar, tearoff=0)
        servosmenu.add_command(label="Next " + str(INCREMENT), command=ServoGridRow.offset_plus_10, font=menu_font)
        servosmenu.add_command(label="Previous " + str(INCREMENT), command=ServoGridRow.offset_minus_10, font=menu_font)
        menubar.add_cascade(label="Servos", menu=servosmenu, font=menu_font)

        ledsmenu = Menu(menubar, tearoff=0)
        ledsmenu.add_command(label="LEDs...", command=LedGridRow.show_leds, font=menu_font)
        ledsmenu.add_command(label="All on", command=LedGridRow.all_leds_on, font=menu_font)
        ledsmenu.add_command(label="All off", command=LedGridRow.all_leds_off, font=menu_font)
        ledsmenu.add_command(label="Next " + str(INCREMENT), command=LedGridRow.offset_plus_10, font=menu_font)
        ledsmenu.add_command(label="Previous " + str(INCREMENT), command=LedGridRow.offset_minus_10, font=menu_font)
        menubar.add_cascade(label="LEDs", menu=ledsmenu, font=menu_font)

        buttonsmenu = Menu(menubar, tearoff=0)
        buttonsmenu.add_command(label="Buttons...", command=ButtonGridRow.show_buttons, font=menu_font)
        buttonsmenu.add_command(label="Next " + str(INCREMENT), command=ButtonGridRow.offset_plus_10, font=menu_font)
        buttonsmenu.add_command(label="Previous " + str(INCREMENT), command=ButtonGridRow.offset_minus_10, font=menu_font)
        menubar.add_cascade(label="Buttons", menu=buttonsmenu, font=menu_font)

        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Help", command=self.help_function, font=menu_font)
        helpmenu.add_command(label="About...", command=self.about_function, font=menu_font)
        menubar.add_cascade(label="Help", menu=helpmenu, font=menu_font)
        self.config(menu=menubar)

    def confirm_quit(self):
        """
        Called when exit is selected from the menu or the x clicked in the top-right,
        this function will ask for confirmation before destroying the window.
        
        
        Checks QUIT_WITHOUT_CONFIRM - when developing the confirmation box is just annoying.
        """
        if QUIT_WITHOUT_CONFIRM:
            self.terminate_gui()
        else:
            response = messagebox.askyesno('Exit','Are you sure you want to exit?')
            if response:
                self.terminate_gui()

    def terminate_gui(self):
        # Has to destroy count_label explicitly because the main loop will try to use it otherwise.
        # Just setting to None is not good enough (and I do not now why).
        self.power_label.destroy()
        self.power_label = None
        self.count_label.destroy()
        self.count_label = None
        self.destroy()
        print('INFO: GUI terminated.')
        request['action'] = 'terminate'

    def about_function(self):
        messagebox.showinfo("About", "This software was created by Andy Joel for Preston&District MRS, copyright 2024.")

    def help_function(self):
        messagebox.showinfo("Help", "Each row controls a servo. Switch the point from left to right and back using On/Off.\n\nThe first angle is the target - what the servo is heading for. The second angle is the current value.\n\nUse Up and Down to modify the target angle.\n\nRemember to do File - Save to save your changes before you exit the program.")




######################################################################
# Create the GUI!



if len(sys.argv) > 1 and sys.argv[1]:
   print('Running headless. Type "x" and press ENTER to exit.')
else:
    window = ServoWindow()
    window.mainloop()
