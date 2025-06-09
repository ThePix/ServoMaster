"""
ServoMaster
Copyright 2024 Andy joel and Preston&District MRS

See here:
https://github.com/ThePix/ServoMaster/wiki

All configuration options are in config.py


S - servoboard
IO
LCD
UPS

s - servo
l - led
r - relay
b - button
f - flasher
- - trackplan

"""


VERSION = '1.5'




#################################################################################
# PYTHON IMPORTS

import time
import re
import sys
import random
import math
import traceback
import os
from threading import Thread

import config


if config.ON_LINE:
    try:
        # Imports for I2C
        import board
        import digitalio
        import adafruit_pcf8575
        import I2C_LCD_driver
        from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C
        from adafruit_servokit import ServoKit
        #import INA219
        from adafruit_ina219 import ADCResolution, BusVoltageRange, INA219
    except ModuleNotFoundError as err:
        print(traceback.format_exc())
        print(f"ERROR: ModuleNotFoundError {err}")
        print('This is likely because you have not activated the environment.\nTo do so, type "source pdmrs/bin/activate", then try again.')
        print('Also check the I2C bus is turned on (click on the raspberry icon, top left, and  select Preferences - Raspberry Pi Configuration, then go to the "Interfaces" tab, and turn on I2C; will need a reboot)')
        exit()
        
        
# Imports for GUI
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import font, Menu, messagebox, PhotoImage, Toplevel, Scrollbar, TclError
from PIL import Image, ImageTk



def verify(n, min, max, msg):
    """
    Checks a value is in the right range. If not the message is printed and the program will quit.
    Used in constructors to ensure servos, etc. are on boards and pins that make sense,
    and angles are in suitable ranges.
    Note that n must be equal or greater than min, but less than max.
    """
    """
    # Is this a better solution than below?!?
    if n < min:
        print(f'{msg} Found {n}, expected that to be {min} or over')
        exit()
    if n != 0 and n >= max:
        print(f'{msg} Found {n}, expected that to be less than {max}')
        exit()
    """
    if n >= max or n < min:
        print(f'ERROR: {msg} Found {n}, expected that to be {min} or over and less than {max}')
        exit()



"""
Custom exceptions so we can handle them neatly without losing info for the unexpected ones.
"""
class ServoConfigException(Exception):
    pass



#################################################################################

class Device:
    def __init__(self):
        global comments
        self.comments = list(comments)
        self.widget = None
        comments = []
        
    def write_to_file(self, f, newline=False):
        if newline:
            f.write('\n')
        for s in self.comments:
            f.write(s)

    def set_widget(self, widget):
        """
        Set a Label widget that the servo can report its angle to.
        Or set to None.
        """
        self.widget = widget



#################################################################################

class Servo(Device):
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
           the centre angle
           the on angle
           the descriptor
        """
        md = re.match(r's (\d+)\.(\d+),? (\d+),? (\d+),? (\d+),? (\d+),?(?: ?\[(.*?)\])? ?(.*)', s)

        if md:
            servo = Servo(int(md.group(1)), int(md.group(2)), int(md.group(3)), int(md.group(4)), int(md.group(5)), int(md.group(6)), md.group(7), md.group(8))
            lst.append(servo)
            return servo
        else:
            print('ERROR: Badly formatted line for servo: ' + s)
            return None
   
    def quiet_all():
        for servo in servos:
            servo.quiet()
            

    def __init__(self, board_no, pin_no, speed, off_angle, centre_angle, on_angle, graphic=None, desc=None):
        """
        Constructor. As well as setting the given values, also creates a servo object from the I2C
        board.        
        """
        super().__init__()
        verify(board_no, 0, len(servo_boards), 'Servo board number out of range.')
        verify(pin_no, 0, 16, 'Servo pin number out of range.')
        verify(off_angle, 10, 180, 'Servo off angle out of range.')
        verify(centre_angle, 10, 180, 'Servo centre angle out of range.')
        verify(on_angle, 10, 180, 'Servo on angle out of range.')
        verify(speed, 10, 1000000, 'Speed out of range.')
        
        self.board_no = board_no
        self.pin_no = pin_no
        self.speed = speed
        self.off_angle = off_angle * 100
        self.centre_angle = centre_angle * 100
        if config.START_CENTRED:
            self.target_angle = centre_angle * 100
            self.current_angle = centre_angle * 100
            self.centred = True
        else:
            self.target_angle = off_angle * 100
            self.current_angle = off_angle * 100
            self.centred = False
        self.on_angle = on_angle * 100
        self.desc = desc
        self.moving = False
        self.on_leds = []
        self.off_leds = []
        self.on_buttons = []
        self.off_buttons = []
        self.main_colour = None
        self.branch_colour = None
        self.relay = None
        self.relay_state = None
       
        if graphic:
            md = re.match(r'(r)?([ABY]) (\d+), (\d+)', graphic)
            if md:
                self.graphic = {
                    'reverse':md.group(1) == 'r',
                    'shape':md.group(2),
                    'x':int(md.group(3)),
                    'y':int(md.group(4)),
                }
            else:
                self.graphic = None
                print('ERROR: Badly formatted line for servo (graphic data): ' + graphic)
        else:
            self.graphic = None

        if config.ON_LINE:
            self.servo = servo_boards[self.board_no].servo[self.pin_no]
            # Do we need these lines?!?
            #print('..' + str(self.current_angle / 100))
            #self.servo.angle = self.current_angle / 100
        self.turn_on = False
        self.index = Servo.count
        Servo.count += 1
       
       
    def is_here(self, x, y):
        if not self.graphic:
            return False

        if self.graphic['x'] != x:
            return False
           
        if self.graphic['y'] == y:
            return True
        # This type opf point goes above the line
        if (self.graphic['shape'] == 'Y' or self.graphic['shape'] == 'A') and self.graphic['y'] == y - 1:
            return True
        # This type opf point goes below the line
        if (self.graphic['shape'] == 'Y' or self.graphic['shape'] == 'B') and self.graphic['y'] == y + 1:
            return True
        return False
       
    def draw(self, trackplan, full=False):
        if not self.graphic:
            return
           
        main_colour = 'silver'
        branch_colour = 'silver'
        if self.current_angle == self.off_angle:
            main_colour = config.POINT_COLOUR
            if self.widget:
                self.state_label.config(text='OFF', foreground='black', background='white')
        if self.current_angle == self.on_angle:
            branch_colour = config.POINT_COLOUR
            if self.widget:
                self.state_label.config(text='ON', foreground='white', background='black')
           
        if self.main_colour != main_colour or self.branch_colour != branch_colour or full:
            if self.graphic['reverse']:
                # Main
                # For Y, 
                offset = -1 if self.graphic['shape'] == 'Y' else 0
                trackplan.r_line(self.graphic['x'], self.graphic['y'], offset, main_colour)
               
                # Branch
                offset = -1 if self.graphic['shape'] == 'B' else 1
                trackplan.r_line(self.graphic['x'], self.graphic['y'], offset, branch_colour)
            else:      
                # Main
                offset = -1 if self.graphic['shape'] == 'Y' else 0
                trackplan.line(self.graphic['x'], self.graphic['y'], offset, main_colour)
               
                # Branch
                offset = -1 if self.graphic['shape'] == 'B' else 1
                trackplan.line(self.graphic['x'], self.graphic['y'], offset, branch_colour)
            self.main_colour = main_colour
            self.branch_colour = branch_colour
     
    def id(self):
        """ The ID is the 'board.pin'. """
        return f'{self.board_no}.{self.pin_no}'

    def write_to_file(self, f):
        """ Writes not just this servo, but also connected buttons and LEDs. """
        super().write_to_file(f, True)
        s = f's {self.board_no}.{self.pin_no}, {self.speed}, {round(self.off_angle / 100)}, {round(self.centre_angle / 100)}, {round(self.on_angle / 100)},'
        if self.graphic:
            s += '['
            if self.graphic['reverse']:
                s += 'r'
            s += f"{self.graphic['shape']} {self.graphic['x']}, {self.graphic['y']}]"
        f.write(f'{s} {self.desc.strip()}\n')
        for led in self.on_leds:
            f.write(f'l on {led.board_no}.{led.pin_no}\n')
        for led in self.off_leds:
            f.write(f'l off {led.board_no}.{led.pin_no}\n')
        if self.relay:
            f.write(f'r {self.relay.board_no}.{self.relay.pin_no}\n')
        for b in self.on_buttons:
            f.write(f'b on {b.board_no}.{b.pin_no}\n')
        for b in self.off_buttons:
            f.write(f'b off {b.board_no}.{b.pin_no}\n')
       
    def set_widget(self, angle_label, state_label):
        """
        Set a Label widget that the servo can report its angle to.
        Or set to None to stop it.
        """
        self.widget = angle_label
        self.state_label = state_label
       
    def sanity_check(self):
        if self.centre_angle < self.off_angle and self.centre_angle < self.on_angle:
            print(f'WARNING: Centre position is less than both ON and OFF positions for servo {self.id()} ({self.desc}).')
        if self.centre_angle > self.off_angle and self.centre_angle > self.on_angle:
            print(f'WARNING: Centre position is greater than both ON and OFF positions for servo {self.id()} ({self.desc}).')
        
        
        if config.SUPPRESS_WARNINGS:
            return

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

    def set_relay(self, relay):
        """ Add the given relay to the list of "on" or "off" relays. """
        self.relay = relay
        self.relay_state = False
        self.relay.set(False)  # May need some thought - could short when first turned on

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
        self.centred = False
        if config.REPORT_SERVO_SWITCHING:
            state = 'ON' if _turn_on else 'OFF'
            print(f'INFO: Setting servo {self.board_no}.{self.pin_no} ({self.desc}) to {state}')
            print_lcd(2, f"Set {self.board_no}.{self.pin_no} to {state}")
       
    def centre(self):
        """"
        Set the target angle to the centre angle, which will cause the servo
        to move to that angle over a few seconds.
        """
        self.target_angle = self.centre_angle
        self.centred = True
        if config.REPORT_SERVO_SWITCHING:
            print(f'INFO: Setting servo {self.board_no}.{self.pin_no} ({self.desc}) to centred')
            print_lcd(2, f"Set {self.board_no}.{self.pin_no} to cen")
       
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
                if config.ON_LINE:
                    self.servo.angle = None
                if self.relay:
                    # Is relay ON and we are now between the centre and off position?
                    if self.off_angle < self.centre_angle and self.current_angle < self.centre_angle and self.relay_state:
                        self.relay_state = False
                        self.relay.set(False)
                    elif self.off_angle > self.centre_angle and self.current_angle > self.centre_angle and self.relay_state:
                        self.relay_state = False
                        self.relay.set(False)
                
                    # Is relay OFF and we are now between the centre and on position?
                    if self.on_angle < self.centre_angle and self.current_angle < self.centre_angle and not self.relay_state:
                        self.relay_state = True
                        self.relay.set(True)
                    elif self.n_angle > self.centre_angle and self.current_angle > self.centre_angle and not self.relay_state:
                        self.relay_state = True
                        self.relay.set(True)
                
            return False

        if not self.moving:
            # Could do this in set, but prefer here as set can be done repeatedly
            self.moving = True
            self.reset_leds()


        increment = elapsed * self.speed * abs(self.on_angle - self.off_angle) / 10000
        # print(increment)
        # diff is then capped at that
        if diff > 0:
            if diff > increment:
                diff = increment
            self.current_angle -= diff
        else:
            if diff < increment:
                diff = increment
            self.current_angle += diff
       
        if config.ON_LINE:
            try:
                self.servo.angle = self.current_angle / 100
            except OSError as err:
                print("ERROR: OSError {err}")
                print("This may be because there is no ground connection\nto the servo board on the I2C side")
                print("Terminating!")
                exit()
                 
       
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

    def quiet(self):
        self.servo.angle = None


"""
Just used by the trackplan during setting up
"""
class Decorator(Device):
    def create(line):
        if line[0:2] == '-c':
            Connector.create(line)
        elif line[0:2] == '-p':
            Platform.create(line)
        elif line[0:2] == '-t':
            Text.create(line)


"""
Used by trackplan to draw a line connecting points.
"""
class Connector(Device):
    """
    Represents a connector - a non-functional line on the trackplan
    """

    offsets = {
        '-':0,
        'u':1,
        'U':2,
        'd':-1,
        'D':-2,
    }

    def create(s):
        md = re.match(r'\-c ?([-uUdD]) (\d+), (\d+) ?(.*)', s)
        if md:
            conn = Connector(md.group(1), int(md.group(2)), int(md.group(3)), md.group(4))
            decorators.append(conn)
            return conn
        else:
            print('ERROR: Badly formatted line for connector: ' + s)
            return None
   
    def __init__(self, shape, x, y, desc=None):
        super().__init__()
        self.offset = Connector.offsets[shape]
        self.shape = shape
        self.desc = desc
        self.x = x
        self.y = y
       
    def draw(self, trackplan):
        trackplan.line(self.x, self.y, self.offset, config.LINE_COLOUR)

    def write_to_file(self, f):
        super().write_to_file(f)
        f.write(f'-c {self.shape} {self.x}, {self.y} {self.desc}\n')
       

"""
Used by trackplan to draw a thick line representing a platform.
"""
class Platform(Device):
    """
    Represents a platform - decoration on the trackplan
    """

    def create(s):
        md = re.match(r'\-p ?(\d+), (\d+) ?(.*)', s)
        if md:
            p = Platform(int(md.group(1)), int(md.group(2)), md.group(3))
            decorators.append(p)
            return p
        else:
            print('ERROR: Badly formatted line for platform: ' + s)
            return None
   
    def __init__(self, x, y, desc=None):
        super().__init__()
        self.x = x
        self.y = y
        self.desc = desc
       
    def draw(self, trackplan):
        trackplan.platform(self.x, self.y)
       
    def write_to_file(self, f):
        super().write_to_file(f)
        f.write(f'-p {self.x}, {self.y} {self.desc}\n')


"""
Used by trackplan to draw text.
"""
class Text(Device):
    """
    Represents a platform - decoration on the trackplan
    """

    def create(s):
        md = re.match(r'\-t ?(\d+), (\d+) (.+)', s)
        if md:
            t = Text(int(md.group(1)), int(md.group(2)), md.group(3))
            decorators.append(t)
            return t
        else:
            print('ERROR: Badly formatted line for text: ' + s)
            return None
   
    def __init__(self, x, y, desc):
        super().__init__()
        self.x = x
        self.y = y
        self.desc = desc
       
    def draw(self, trackplan):
        trackplan.text(self.x, self.y, self.desc)
       
    def write_to_file(self, f):
        super().write_to_file(f)
        f.write(f'-t {self.x}, {self.y} {self.desc}\n')








#################################################################################
 
class IOPin(Device):
    """
    Represents an I/O pin, superclass for buttons and LEDs.
    """

    def create(klass, lst, letter, s, servos):
        """
        Adds an I/O pin object, given a string
        The string should consist of a "l" (for LED) or "b" (for button) or "r" (for relay) to identify it as such
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        """
        md = re.match(letter + ' (on|off) (\\d+)\\.(\\d+)', s)
        if not md:
            raise ServoConfigException('ERROR: Badly formatted line for IOPin: ' + s)
        # get the data from the regex match
        turn_on = md.group(1) == 'on'
        board_no = int(md.group(2))
        pin_no = int(md.group(3))
        # is there already an item of the wrong sort assigned there? if so, that is an error
        IOPin.check_io(lst, board_no, pin_no)
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
       
    def check_io(safe_lst, board_no, pin_no):
        """
        Checks if the board/pin is already in use.
        If it is, an exception is thrown.
        If it is good, does nothing
        """
        for lst in io_lists:
            if lst == safe_lst:
                continue
            for el in lst:
                if el.board_no == board_no and el.pin_no == pin_no:
                    raise ServoConfigException(f'ERROR: Trying to set board/pin to something when already something else: {board_no}.{pin_no}')
                
       

    def __init__(self, board_no, pin_no):
        """ Constructor. """
        super().__init__()
        self.board_no = board_no
        self.pin_no = pin_no
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
        led, turn_on = IOPin.create(Led, leds, 'l', s, servos)
        servo.set_led(led, turn_on)


    def __init__(self, board_no, pin_no):
        """
        Constructor. Uses the super contructor, but also connects to the I/O board.
        """
        super().__init__(board_no, pin_no)
        verify(self.board_no, 0, len(io_boards), 'I/O board number out of range for LED.')
        verify(self.pin_no, 0, 16, 'LED pin number out of range.')
        if config.ON_LINE:
            self.led = io_boards[self.board_no].get_pin(self.pin_no)
            self.led.switch_to_output(value=True)
        self.index = Led.count
        Led.count += 1
       
    def set(self, value):
        """ Sets the LED on or off. """
        if config.ON_LINE:
            self.led.value = not value


class Relay(IOPin):
    """
    Represents an input to a relay
    """
    count = 0

    def create(s, servos):
        """
        Adds a Relay object, given a string.
        The string should consist of a "r" to identify it
        followed by (all separated with spaces):
           on/off
           the address - the board number, a dot and the pin number
        Uses IOPin.create to do most of the work
        """
        relay, turn_on = IOPin.create(Relay, relays, 'r', s, servos)
        servo.set_relay(relay, turn_on)


    def __init__(self, board_no, pin_no):
        """
        Constructor. Uses the super contructor, but also connects to the I/O board.
        """
        super().__init__(board_no, pin_no)
        verify(self.board_no, 0, len(io_boards), 'I/O board number out of range for relay.')
        verify(self.pin_no, 0, 16, 'Relay pin number out of range.')
        if config.ON_LINE:
            self.relay = io_boards[self.board_no].get_pin(self.pin_no)
            self.relay.switch_to_output(value=True)
        self.index = Relay.count
        Relay.count += 1
       
    def set(self, value):
        """ Sets the relay on or off. """
        if config.ON_LINE:
            self.relay.value = value


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
        button, turn_on = IOPin.create(PButton, buttons, 'b', s, servos)
        servo.set_button(button, turn_on)

    def __init__(self, board_no, pin_no):
        """
        Constructor. Uses the super contructor, but also connects to the I/O board.
        """
        super().__init__(board_no, pin_no)
        verify(self.board_no, 0, len(io_boards), 'I/O board number out of range for button.')
        verify(self.pin_no, 0, 16, 'Button pin number out of range.')
        if config.ON_LINE:
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
        if not config.ON_LINE:
            return False
       
        try:
            return not self.button.value
        except OSError:
            print('ERROR: Got an OSError, possibly because I am trying to read a board that does not exist or is faulty?')
            print(f'board={self.board} pin={self.pin}')
            print(e)

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

class Flasher(Device):
    """
    Represents a flashing LED. The flashing is defined by an initial delay, and either:
      an on time and an off time; the length of the cycle is on+off
      a string pattern, with dots for off and asterisks for on; the length of the cycle is the length of the string
    Times are in tenths of a second.
    """

    count = 0

    def create(s):
        """
        Adds a flasher object, given a string
        The string should consist of
          an "f"
          "s" or "r" or "p" indicating the type
          the address - the board number, a dot and the pin number
          the start delay
          the flashing patttern as a string of dots and asterisks or the on time followed by the off time
        """
        md = re.match('f(s|r|p)', s)
        if not md:
            raise ServoConfigException('ERROR: Badly formatted line for Flasher: ' + s)
        if  md.group(1) == 'p':
            Flasher._p_create(s)
        else:
            Flasher._sr_create(s)

    def _sr_create(s):
        # Used by create to create a standard or variable flasher
        md = re.match('f(s|r) (\\d+)\\.(\\d+),? (\\d+),? (\\d+),? (\\d+)', s)
        if not md:
            raise ServoConfigException('ERROR: Badly formatted line for Flasher: ' + s)
        # get the data from the regex match
        board_no = int(md.group(2))
        pin_no = int(md.group(3))
        start = int(md.group(4))
        on = int(md.group(5))
        off = int(md.group(6))
        letter = md.group(1)
        # is there already an item of the wrong sort assigned there? if so, that is an error
        IOPin.check_io(None, board_no, pin_no)
        flashers.append(Flasher(board_no, pin_no, letter, start, on=on, off=off))

    def _p_create(s):
        # Used by create to create a pattern flasher
        md = re.match('fp (\\d+)\\.(\\d+),? (\\d+),? ([\\.\\*]+)', s)
        if not md:
            raise ServoConfigException('ERROR: Badly formatted line for Flasher: ' + s)
        # get the data from the regex match
        board_no = int(md.group(1))
        pin_no = int(md.group(2))
        start = int(md.group(3))
        pattern = md.group(4)
        # is there already an item of the wrong sort assigned there? if so, that is an error
        IOPin.check_io(None, board_no, pin_no)
        flashers.append(Flasher(board_no, pin_no, 'p', start, pattern=pattern))


    def __init__(self, board_no, pin_no, letter, start, on=0, off=0, pattern=None):
        """
        Constructor.
        """
        super().__init__()
        verify(board_no, 0, len(io_boards), 'I/O board number out of range for LED.')
        verify(pin_no, 0, 16, 'LED pin number out of range.')
        self.board_no = board_no
        self.pin_no = pin_no
        self.state = False
        if config.ON_LINE:
            self.led = io_boards[self.board_no].get_pin(self.pin_no)
            self.led.switch_to_output(value=True)
        self.index = Flasher.count
        Flasher.count += 1
        self.letter = letter
        self.start = start
        self.on = on
        self.off = off
        self.loop_on = on
        self.loop_off = off
        self.pattern = []
        if pattern:
            for c in pattern:
                self.pattern.append(c == '*')

    def id(self):
        """ The ID is the 'board.pin'. """
        return f'{self.board_no}.{self.pin_no}'

    def _vary(self, n):
        m = round(n/2)
        return m + random.randint(0, m) + random.randint(0, m)

    def set(self, value):
        """ Sets the LED on or off. """
        self.state = value
        if config.ON_LINE:
            self.led.value = not value
        if self.widget:
            if self.state:
                self.widget.config(text='ON!', foreground='black', background='#80ff00')
            else:
                self.widget.config(text='---', foreground='black', background='#aaaaaa')
       
       
    def check(self, t):
        """
        Should be called every loop with the elapsed time in tenths of a second
        """
        getattr(self, '_' + self.letter + '_check')(t)
   
    def _s_check(self, t):
        if t < self.start:
            return
        t2 = (t - self.start) % (self.on + self.off)
        if t2 < self.on:
            if not self.state:
                self.set(True)
        else:
            if self.state:
                self.set(False)

    def _r_check(self, t):
        if t < self.start:
            return
        if not self.loop_on:
           # is this used?
           self.loop_on = self._vary(self.on)
           self.cycle_count = 0
        t2 = (t - self.start) % (self.loop_on + self.loop_off)
        if t2 < self.loop_on:
            if not self.state:
                self.set(True)
                self.loop_off = self._vary(self.off)
        else:
            if self.state:
                self.set(False)
                self.loop_on = self._vary(self.on)

    def _p_check(self, t):
        if t < self.start:
            return
        t2 = math.floor((t - self.start) % len(self.pattern))
        desired = self.pattern[t2]
        if self.state != desired:
            self.set(desired)

    def write_to_file(self, f):
        """ Writes the flasher to file. """
        super().write_to_file(f)
        if self.letter == 'p':
            pattern = ''
            for flag in self.pattern:
                pattern += ('*' if flag else '.')
            f.write(f'fp {self.board_no}.{self.pin_no}, {self.start}, {pattern}\n')
        else:
            f.write(f'f{self.letter} {self.board_no}.{self.pin_no}, {self.start}, {self.on}, {self.off}\n')
       







#################################################################################
# INITIALISING

start_time = time.time()
previous_time = start_time

if config.ON_LINE:
    i2c = board.I2C()  # uses board.SCL and board.SDA
io_boards = []
servo_boards = []
lcd_board = None
ups_board = None

def print_lcd(n, s):
    #print(f'LCD{n}: {s}')
    #print(type(lcd_board))
    #print(lcd_board)
    if config.ON_LINE and lcd_board:
        lcd_board.lcd_display_string(s, n)


servos = []
leds = []
buttons = []
relays = []
flashers = []
io_lists = [leds, buttons, relays, flashers]
decorators = []

trackplan = None


request = { 'action':False, 'testing':True}  # User input is done by changing this to request a change
loop_count = 0

window = None

comments = None

servo_grid_rows = []
button_grid_rows = []
led_grid_rows = []
flasher_grid_rows = []



#################################################################################
# SAVING AND LOADING

def save():
    """
    Saves the configuration to file.
    """
    try:
        with open('servo.txt', 'w', encoding="utf-8") as f:
            # Save the boards
            if config.ON_LINE:
                for servo_board in servo_boards:
                    f.write(f'S{hex(servo_board._pca.i2c_device.device_address)}\n')
                for io_board in io_boards:
                    f.write(f'IO{hex(io_board.i2c_device.device_address)}\n')
                if lcd_board:
                    f.write(f'LCD{hex(lcd_board.lcd_device.addr)}\n')
                if usp_board:
                    f.write(f'UPS{hex(usp_board.addr)}\n')
            else:
                for servo_board in servo_boards:
                    f.write(f'S{hex(servo_board.addr)}\n')
                for io_board in io_boards:
                    f.write(f'IO{hex(io_board.addr)}\n')
                if lcd_board:
                    f.write(f'LCD{hex(lcd_board.addr)}\n')
                if usp_board:
                    f.write(f'UPS{hex(usp_board.addr)}\n')

            # Now save the servos and related data
            for lst in [servos, flashers, decorators]:
                f.write('\n\n')
                for el in lst:
                    el.write_to_file(f)
               
        print("INFO: Save successful")

    except Exception as err:
        print('ERROR: Failed to save the configuration file, servo.txt.')
        print(f"Reported: Unexpected {err=}, {type(err)=}")
        print(traceback.format_exc())



# We can check devices are connected as they are loaded from file
# so first get a list of addresses on the I2C bus
if config.ON_LINE:
    i2c_devices = i2c.scan()
    print("INFO: Found I2C devices:", [hex(device_address) for device_address in i2c_devices])
else:
    print("WARNING: Running in off-line mode, not connecting to I2C bus.")


class fake_board:
    def __init__(self, addr):
        self.addr = addr

class fake_ups_board:
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
    # If a device not found - other than LCD or UPS - give up
    if config.ON_LINE and not address in i2c_devices and not md.group(1) in ['LCD', 'UPS']:
        print('ERROR: Device not found: ' + line)
        print('This is not going well; I am giving up!\nYou need to ensure the I2C boards are connected\nand correctly configured in "servo.txt".\nGood luck...')
        exit()
                        
    if config.ON_LINE:
        match md.group(1):
            case 'S':
                servo_boards.append(ServoKit(channels=16, address=address))
            case 'IO':
                io_boards.append(adafruit_pcf8575.PCF8575(i2c, address))
            case 'LCD':
                global lcd_board
                lcd_board = I2C_LCD_driver.lcd()
            case 'UPS':
                global ups_board
                ups_board = INA219(i2c, addr=address)
            case _:
                print('ERROR: Device code not recognised: ' + line)
    else:
        match md.group(1):
            case 'S':
                servo_boards.append(fake_board(address))
            case 'IO':
                io_boards.append(fake_board(address))
            case 'LCD':
                lcd_board = fake_board(address)
            case 'UPS':
                ups_board = fake_ups_board(address)
            case _:
                print('ERROR: Device code not recognised: ' + line)
    print(f'Done')




try:
    """
    File access can be problematic, so wrap in a try/except block
    """
    with open('/home/f2andy/pdmrs/servo.txt', encoding="utf-8") as f:
        print('opened')
        servo = None
        comments = []
        for line in f:
            if line.isspace():
                continue
            if line[0:1] == '#':
                comments.append(line)
            elif line[0:1] == 's':
                servo = Servo.create(servos, line)
            elif line[0:1] == '-':
                Decorator.create(line)
            elif line[0:1] == 'b':
                PButton.create(line, servo)
            elif line[0:1] == 'r':
                Relay.create(line, servo)
            elif line[0:1] == 'l':
                Led.create(line, servo)
            elif line[0:1] == 'f':
                Flasher.create(line)
            else:
                load_device(line)
except FileNotFoundError as ex:
    print(ex)
    print('ERROR: Failed to open the configuration file, servo.txt.')
    print('Should be a text file in the same directory as this program.')
    print('Not much I can do with it, so giving up...')
    exit()
except ServoConfigException as ex:
    print(ex)
    print('Failed to load data file.')
    exit()


               
# report how it went for diagostics
print(f"INFO: Found {len(servo_boards)} servo board(s).")
print(f"INFO: Found {len(io_boards)} I/O board(s).")

print(f"INFO: Found {'one' if lcd_board else 'no'} LCD board; sending welcome message.")
print_lcd(1, "Hello P&D MRS!")

print(f"INFO: Found {'one' if ups_board else 'no'} UPS board.")

print(f"INFO: Found {len(servos)} servo(s).")
print(f"INFO: Found {len(buttons)} button(s).")
print(f"INFO: Found {len(leds)} indicator LED(s).")
print(f"INFO: Found {len(relays)} relay(s).")
print(f"INFO: Found {len(flashers)} flashing LED(s).")
for servo in servos:
    servo.sanity_check()

print(f"INFO: Passed sanity check.")

       

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
        increment = config.TIME_FACTOR * elapsed
       
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

       
        # HANDLE UPS
        # Only do this every 100 loops; it is not going to change much
        # Get values from device
        # If below config.SHUTDOWN_AT% and draining, shutdown
        # Otherwise report to GUI
        # https://github.com/adafruit/Adafruit_CircuitPython_INA219/blob/main/examples/ina219_simpletest.py
        if loop_count % 100 == 0 and ups_board:
            bus_voltage = ups_board.bus_voltage            # voltage on V- (load side)
            current = ups_board.current                    # current in mA
            if window and window.power_label:
                #print(f"v(bus)={'%.2f' % bus_voltage}, I={'%.2f' % current}")
                try:
                    if current < config.ON_BATTERY:
                        window.power_label.config(text=f'On batteries, at {round(bus_voltage, 2)} V')
                        #print('draining')
                        if bus_voltage < config.SHUTDOWN_VOLTAGE:
                            print("Battery supply about to expire - shutting down.")
                            os.system(f". {config.SHUTDOWN_FILE}")
                    elif current > config.CHARGING:
                        window.power_label.config(text=f'Battery charging, at {round(bus_voltage, 2)} V')
                        #print('charging')
                    else:
                        window.power_label.config(text=f'Power normal, at {round(bus_voltage, 2)} V')
                        #print('normal')
                except tk.TclError:
                    print('*')
            # also want to do LCD


        # HANDLE INPUTS
        for button in buttons:
            button.check_state()
       
           
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
                if config.REPORT_SERVO_SWITCHING:
                    ident = leds[request['servo']].id()
                    print(f'INFO: LED on {ident}')
            request['action'] = False
        if request['action'] == 'LED off':
            if request['servo'] >= len(leds):
                print("WARNING: LED out of range (0-" + str(len(leds)) + ")")
            else:
                leds[request['servo']].set(False)
                if config.REPORT_SERVO_SWITCHING:
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


        # HANDLE FLASHERS
        if loop_count % 100 == 10:
            t = (time.time() - start_time) * 10
            for flasher in flashers:
                flasher.check(t)


        # HANDLE SERVOS
        moving_flag = False;
        for servo in servos:
            if servo.adjust(increment):
                moving_flag = True


        if loop_count % 100 == 50 and trackplan:
            trackplan.redraw()

        time.sleep(config.SLEEP)

    print("INFO: Main loop terminated.")

 
# We have the main_loop on a separate thread. It is set to a daemon thread so
# should ensure it stops when the main thread ends

main_thread = Thread(target = main_loop)
main_thread.daemon = True
main_thread.start()

print("INFO: Main loop thread started.")






######################################################################
# GUI


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


class TrackPlan(tk.Toplevel):
    """
    """
    def show():
        global trackplan
        if not trackplan:
            trackplan = TrackPlan(window)
            trackplan.redraw(True)
            trackplan.geometry("+%d+%d" %(10,80))       
       
       
    def left_click(event):
        TrackPlan._mouse_click(event, False)
       
    def right_click(event):
        TrackPlan._mouse_click(event, True)
       
    def _mouse_click(event, right_click):
        x = TrackPlan._underive_x(event.x)
        y = TrackPlan._underive_y(event.y)
        for servo in servos:
            if servo.is_here(x, y):
                if config.LEFT_CLICK_ONLY:
                    if servo.current_angle == servo.on_angle:
                        servo.set(False)
                    if servo.current_angle == servo.off_angle:
                        servo.set(True)
                else:
                    servo.set(right_click)
       

    def __init__(self, window):
        super().__init__(window, width=config.WIDTH, height=config.HEIGHT + 24)
        self.title('TrackPlan: ' + config.TITLE)
       
        try:
            self.img = Image.open("servo_icon.png")
            self.img = ImageTk.PhotoImage(self.img)
        except FileNotFoundError:
            self.img = None
            print('WARNING: Failed to find icon file, "servo_icon.png", but carrying on regardless!')

        if self.img:
            ttk.Label(self, image=self.img).place(x=0, y=0)
        if config.LEFT_CLICK_ONLY:
            label = tk.Label(self, text='Left click a point to change it (no effect while moving)').place(x=40,y=0)
        else:
            label = tk.Label(self, text='Left click a point for straight, right click for branch (for a Y, the lower counters as straight)').place(x=40,y=0)
       
       
        self.canvas = tk.Canvas(self, width=config.WIDTH, height=config.HEIGHT)
        self.canvas.place(x=0,y=24)
        self.canvas.bind('<Button-1>', TrackPlan.left_click)
        self.canvas.bind('<Button-3>', TrackPlan.right_click)
        self.redraw(True)
       
       
    def redraw(self, full=False):
        if full:
            self.canvas.delete(tk.ALL)
            if config.SHOW_GRID:
                for i in range(math.floor(config.WIDTH / config.X_SCALE)):
                    for j in range(math.floor(config.HEIGHT / config.Y_SCALE)):
                        self.canvas.create_line(TrackPlan._derive_x(i), TrackPlan._derive_y(j), TrackPlan._derive_x(i) + 1, TrackPlan._derive_y(j), fill='black', width=1)
            for el in decorators:
                el.draw(self)

        for servo in servos:
            servo.draw(self, full)
           
    # Convert a grid position to pixels
    def _derive_x(x):
        n = x * config.X_SCALE + config.X_OFFSET
        return config.WIDTH - n if config.X_MIRROR else n

    def _derive_y(y):
        n = config.HEIGHT - y * config.Y_SCALE - config.Y_OFFSET
        return config.HEIGHT - n if config.Y_MIRROR else n
           
           
    # Convert a pixel position to grid
    def _underive_x(x):
        if config.X_MIRROR:
            x = config.WIDTH - x
        return math.floor((x - config.X_OFFSET) / config.X_SCALE)

    def _underive_y(y):
        if config.Y_MIRROR:
            y = config.HEIGHT - y
        return math.floor((config.HEIGHT - y - config.Y_OFFSET) / config.Y_SCALE)




           
    def line(self, x, y, dy, c):
        self.canvas.create_line(TrackPlan._derive_x(x), TrackPlan._derive_y(y), TrackPlan._derive_x(x + 1), TrackPlan._derive_y(y + dy), fill=c, width=config.LINE_WIDTH)

    def r_line(self, x, y, dy, c):
        self.canvas.create_line(TrackPlan._derive_x(x + 1), TrackPlan._derive_y(y), TrackPlan._derive_x(x), TrackPlan._derive_y(y + dy), fill=c, width=config.LINE_WIDTH)

    def platform(self, x, y):
        self.canvas.create_line(TrackPlan._derive_x(x), TrackPlan._derive_y(y + 0.5), TrackPlan._derive_x(x + 1), TrackPlan._derive_y(y + 0.5), fill='grey', width=config.Y_SCALE)

    def text(self, x, y, s):
        self.canvas.create_text(TrackPlan._derive_x(x), TrackPlan._derive_y(y + 0.5), text=s, fill="black", font=('Helvetica 15 bold'))


    def destroy(self):
        global trackplan
        trackplan = None
        return super().destroy()


class ServoGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one servo,
    and buttons and labels on the row will change and reflect its state, but
    which servo that is can _vary depending on what self.offset is.
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

    def centre_all():
        for servo in servos:
            servo.centre()
        for row in servo_grid_rows:
            row.update()
   
    def offset_plus_10():
        if ServoGridRow.offset > len(servos) - config.INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        ServoGridRow.offset += config.INCREMENT
        ServoGridRow.set_offset()

    def offset_minus_10():
        if ServoGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        ServoGridRow.offset -= config.INCREMENT
        ServoGridRow.set_offset()

    def set_offset():
        for servo in servos:
            servo.set_widget(None, None)
        for row in servo_grid_rows:
            row.update()

    def headers(img, font):
        """ Set the first row. """
        if img:
            ttk.Label(width=5, font=font, image=img).grid(column=0, row=0)
        ttk.Label(text='ID', width=7, font=font).grid(column=1, row=0)
        ttk.Label(text='Description', width=config.DESC_WIDTH, font=font).grid(column=2, row=0)
        ttk.Label(text='Switch', font=font).grid(column=3, row=0)
        ttk.Label(text='State', width=10, font=font).grid(column=4, row=0)
        ttk.Label(text='Target', width=10, font=font).grid(column=7, row=0)
        ttk.Label(text='Current', width=10, font=font).grid(column=8, row=0)

    def __init__(self, row, font):
        # When creating, the first servo is 0
        self.row = row             # The row in the table in the GUI
        #self.servo = servos[row]   # The current servo - but can change
        #self.lbl_index = ttk.Label(text=str(row), font=font) # row number turns out to be confusing!
        #self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_id = ttk.Label(text='---', width=7, font=font)
        self.lbl_id.grid(column=1, row=1 + row)

        self.lbl_desc = ttk.Label(text='---', width=config.DESC_WIDTH, font=font)
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
            #self.lbl_index.config(text=str(self.row + self.offset))
            self.lbl_id.config(text=self.servo.id())
            self.lbl_desc.config(text=self.servo.desc)
            state = 'ON' if self.servo.turn_on else 'OFF'
            if servo.centred:
                self.lbl_state.config(text='CENTRE', foreground='blue', background='silver')
            elif self.servo.turn_on:
                self.lbl_state.config(text='ON', foreground='white', background='black')
            else:
                self.lbl_state.config(text='OFF', foreground='black', background='white')
           
            self.lbl_target_angle.config(text=self.servo.get_target_angle())
            self.lbl_current_angle.config(text=self.servo.get_current_angle())
            #print(f'set widget {self.row} for servo {self.servo.index}')
            self.servo.set_widget(self.lbl_current_angle, self.lbl_state)
        else:
            self.servo = None
            #self.lbl_index.config(text='---')
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
            self.lbl_state.config(text='OFF', foreground='black', background='white')
            self.lbl_target_angle.config(text=self.servo.get_off_angle())
            request['action'] = 'off'
            request['servo'] = self.servo.index
        else:
            self.lbl_state.config(text='ON', foreground='white', background='black')
            self.lbl_target_angle.config(text=self.servo.get_on_angle())
            request['action'] = 'on'
            request['servo'] = self.servo.index


    def up_button(self, event):
        """ When the Up button for this row is pressed. """
        if not self.servo:
            print('No servo at row')
            return

        if self.servo.centred:
            if self.servo.centre_angle > 17500 - config.ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go over 175')
                return
            self.servo.centre_angle += config.ANGLE_ADJUST * 100
           
        elif self.servo.turn_on:
            if self.servo.on_angle > 17500 - config.ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go over 175')
                return
            self.servo.on_angle += config.ANGLE_ADJUST * 100
           
        else:
            if self.servo.off_angle > 17500 - config.ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go over 175')
                return
            self.servo.off_angle += config.ANGLE_ADJUST * 100

        self.servo.target_angle += config.ANGLE_ADJUST * 100
        self.lbl_target_angle.config(text=self.servo.get_target_angle())

    def down_button(self, event):
        """ When the Down button for this row is pressed. """
        if not self.servo:
            print('No servo at row')
            return

        if self.servo.centred:
            if self.servo.centre_angle < 500 + config.ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go under 5')
                return
            self.servo.centre_angle -= config.ANGLE_ADJUST * 100
           
        elif self.servo.turn_on:
            if self.servo.on_angle < 500 + config.ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go under 5')
                return
            self.servo.on_angle -= config.ANGLE_ADJUST * 100
           
        else:
            if self.servo.off_angle < 500 + config.ANGLE_ADJUST * 100:
                print('BAD INPUT: Cannot go under 5')
                return
            self.servo.off_angle -= config.ANGLE_ADJUST * 100

        self.servo.target_angle -= config.ANGLE_ADJUST * 100
        self.lbl_target_angle.config(text=self.servo.get_target_angle())


class ButtonGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one (real) button,
    and buttons and labels on the row will change and reflect its state, but
    which (real) button that is can _vary depending on what offset is.
    """
   
    offset = 0

    def show():
        newWindow = ButtonsWindow(window)
        newWindow.title('Buttons: ' + config.TITLE)
        ButtonGridRow.headers(newWindow)
        for i in range(config.NUMBER_OF_ROWS):
            button_grid_rows.append(ButtonGridRow(newWindow, i))

    def headers(win):
        """ Set the first row. """
        ttk.Label(win, text='ID', width=5, font=window.heading_font).grid(column=1, row=0)
        ttk.Label(win, text='Off servos', width=20, font=window.heading_font).grid(column=2, row=0)
        ttk.Label(win, text='On servos', width=20, font=window.heading_font).grid(column=3, row=0)
        ttk.Label(win, text='State', font=window.heading_font, width=7).grid(column=4, row=0)

    def offset_plus_10():
        if ButtonGridRow.offset > len(buttons) - config.INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        ButtonGridRow.offset += config.INCREMENT
        ButtonGridRow.set_offset()

    def offset_minus_10():
        if ButtonGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        ButtonGridRow.offset -= config.INCREMENT
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
    which LED that is can _vary depending on what offset is.
    """

    offset = 0


    def show():
        """ Responds to a menu click to show the window for LEDs"""

        newWindow = Toplevel(window)
        newWindow.title('LEDs: ' +  + config.TITLE)
        LedGridRow.headers(newWindow)
        for i in range(config.NUMBER_OF_ROWS):
            led_grid_rows.append(LedGridRow(newWindow, i))
           
    def all_leds_on():
        """ Responds to a menu click to tirn on all LEDs"""
        request['action'] = 'all LED on'

    def all_leds_off():
        """ Responds to a menu click to tirn off all LEDs"""
        request['action'] = 'all LED off'


    def headers(win):
        """ Set the first row. """
        ttk.Label(win, text='ID', width=5, font=window.heading_font).grid(column=1, row=0)
        ttk.Label(win, text='Off servos', width=20, font=window.heading_font).grid(column=2, row=0)
        ttk.Label(win, text='On servos', width=20, font=window.heading_font).grid(column=3, row=0)

    def offset_plus_10():
        if LedGridRow.offset > len(leds) - config.INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        LedGridRow.offset += config.INCREMENT
        LedGridRow.set_offset()

    def offset_minus_10():
        if LedGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        LedGridRow.offset -= config.INCREMENT
        LedGridRow.set_offset()


    def set_offset():
        for led in leds:
            led.set_widget(None)
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


class FlasherGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one Flasher,
    and buttons and labels on the row will change and reflect its state, but
    which Flasher that is can _vary depending on what offset is.
    """

    offset = 0


    def show():
        """ Responds to a menu click to show the window for LEDs"""

        newWindow = Toplevel(window)
        newWindow.title('Flashers: ' + config.TITLE)
        FlasherGridRow.headers(newWindow)
        for i in range(config.NUMBER_OF_ROWS):
            led_grid_rows.append(FlasherGridRow(newWindow, i))
           
    def headers(win):
        """ Set the first row. """
        ttk.Label(win, text='ID', width=5, font=window.heading_font).grid(column=1, row=0)
        #ttk.Label(win, text='Off servos', width=20, font=window.heading_font).grid(column=2, row=0)
        #ttk.Label(win, text='On servos', width=20, font=window.heading_font).grid(column=3, row=0)

    def offset_plus_10():
        if FlasherGridRow.offset > len(leds) - config.INCREMENT:
            print('BAD INPUT: Trying to go beyond end!')
            return
        FlasherGridRow.offset += config.INCREMENT
        FlasherGridRow.set_offset()

    def offset_minus_10():
        if FlasherGridRow.offset == 0:
            print('BAD INPUT: Trying to go beyond start!')
            return
        FlasherGridRow.offset -= config.INCREMENT
        FlasherGridRow.set_offset()


    def set_offset():
        for flasher in flashers:
            flasher.set_widget(None)
        for row in flasher_grid_rows:
            row.update()

    def __init__(self, win, row):
        # When creating, the first button is 0
        self.row = row             # The row in the table in the GUI
        self.lbl_index = ttk.Label(win, text=str(row), font=window.label_font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_desc = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_desc.grid(column=1, row=1 + row, sticky='w')

        self.lbl_state = ttk.Label(win, text='---', width=20, font=window.label_font)
        self.lbl_state.grid(column=2, row=1 + row, sticky='w')

        """2
        self.btn_on = ttk.Button(win, text="On")
        self.btn_on.grid(column=4, row=1 + row)
        self.btn_on.bind("<Button-1>", self.led_on_button)
       
        self.btn_off = ttk.Button(win, text="Off")
        self.btn_off.grid(column=5, row=1 + row)
        self.btn_off.bind("<Button-1>", self.led_off_button)
        """

        self.update()



    def update(self):
        """
        Updates the row for a new led (or no led) when offset changes
        """
        if 0 <= (self.row + FlasherGridRow.offset) < len(flashers):
            self.flasher = flashers[self.row + FlasherGridRow.offset]
            self.lbl_index.config(text=str(self.row + FlasherGridRow.offset))
            self.lbl_desc.config(text=self.flasher.id())
            self.flasher.set_widget(self.lbl_state)
        else:
            self.flasher = None
            self.lbl_index.config(text='---')
            self.lbl_desc.config(text='---')
    """
    def led_on_button(self, event):
        request['action'] = 'LED on'
        request['servo'] = self.led.index

    def led_off_button(self, event):
        request['action'] = 'LED off'
        request['servo'] = self.led.index
    """

class ServoWindow(tk.Tk):
    """
    Defines instances of a top-level window, whichis used to display servos
    in a grid. Buttons on the grid allow interaction with individual servos,
    while a menu bar gives other options.
    Content of each grid row is done in ServoGridRow.    
    """
    def __init__(self, *args, **kwargs):
       
        tk.Tk.__init__(self, *args, **kwargs)  # Note: super() does not work here
        if config.ON_LINE:
            self.title(f"ServoMaster ({VERSION}): {config.TITLE}")
        else:
            self.title(f"ServoMaster ({VERSION}): {config.TITLE} (off-line)")
           
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
        for i in range(config.NUMBER_OF_ROWS):
            servo_grid_rows.append(ServoGridRow(i, self.label_font))

        ttk.Label(text='Power supply:', font=self.heading_font).grid(column=1, row=config.NUMBER_OF_ROWS + 1)
        self.power_label = ttk.Label(text='---', font=self.heading_font)
        self.power_label.grid(column=2, row=config.NUMBER_OF_ROWS + 1)

        ttk.Label(text='Cycle count:', font=self.heading_font).grid(column=6, row=config.NUMBER_OF_ROWS + 1)
        self.count_label = ttk.Label(text='---', font=self.heading_font)
        self.count_label.grid(column=7, row=config.NUMBER_OF_ROWS + 1)


    def create_menubar(self):
        # Doing this in its own function just to keep it isolated
        menu_font = font.Font(size=10)
        menubar = Menu(self)
        file_menu = Menu(menubar, tearoff=0, font=menu_font)
        file_menu.add_command(label="Save", command=save, font=menu_font)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.confirm_quit, font=menu_font)
        menubar.add_cascade(label="File", menu=file_menu, font=menu_font)

        servos_menu = Menu(menubar, tearoff=0)
        servos_menu.add_command(label="Centre all", command=ServoGridRow.centre_all, font=menu_font)
        servos_menu.add_command(label="Next " + str(config.INCREMENT), command=ServoGridRow.offset_plus_10, font=menu_font)
        servos_menu.add_command(label="Previous " + str(config.INCREMENT), command=ServoGridRow.offset_minus_10, font=menu_font)
        servos_menu.add_command(label="Track plan...", command=TrackPlan.show, font=menu_font)
        servos_menu.add_command(label="Quiet", command=Servo.quiet_all, font=menu_font)
        menubar.add_cascade(label="Servos", menu=servos_menu, font=menu_font)

        leds_menu = Menu(menubar, tearoff=0)
        leds_menu.add_command(label="LEDs...", command=LedGridRow.show, font=menu_font)
        leds_menu.add_command(label="All on", command=LedGridRow.all_leds_on, font=menu_font)
        leds_menu.add_command(label="All off", command=LedGridRow.all_leds_off, font=menu_font)
        leds_menu.add_command(label="Next " + str(config.INCREMENT), command=LedGridRow.offset_plus_10, font=menu_font)
        leds_menu.add_command(label="Previous " + str(config.INCREMENT), command=LedGridRow.offset_minus_10, font=menu_font)
        menubar.add_cascade(label="LEDs", menu=leds_menu, font=menu_font)

        buttons_menu = Menu(menubar, tearoff=0)
        buttons_menu.add_command(label="Buttons...", command=ButtonGridRow.show, font=menu_font)
        buttons_menu.add_command(label="Next " + str(config.INCREMENT), command=ButtonGridRow.offset_plus_10, font=menu_font)
        buttons_menu.add_command(label="Previous " + str(config.INCREMENT), command=ButtonGridRow.offset_minus_10, font=menu_font)
        menubar.add_cascade(label="Buttons", menu=buttons_menu, font=menu_font)

        flashers_menu = Menu(menubar, tearoff=0)
        flashers_menu.add_command(label="Flashers...", command=FlasherGridRow.show, font=menu_font)
        flashers_menu.add_command(label="Next " + str(config.INCREMENT), command=LedGridRow.offset_plus_10, font=menu_font)
        flashers_menu.add_command(label="Previous " + str(config.INCREMENT), command=LedGridRow.offset_minus_10, font=menu_font)
        menubar.add_cascade(label="Flashers", menu=flashers_menu, font=menu_font)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="Help", command=self.help_function, font=menu_font)
        help_menu.add_command(label="About...", command=self.about_function, font=menu_font)
        menubar.add_cascade(label="Help", menu=help_menu, font=menu_font)
        self.config(menu=menubar)

    def confirm_quit(self):
        """
        Called when exit is selected from the menu or the x clicked in the top-right,
        this function will ask for confirmation before destroying the window.
       
       
        Checks config.QUIT_WITHOUT_CONFIRM - when developing the confirmation box is just annoying.
        """
        if config.QUIT_WITHOUT_CONFIRM:
            self.terminate_gui()
        else:
            response = messagebox.askyesno('Exit','Are you sure you want to exit?')
            if response:
                self.terminate_gui()

    def terminate_gui(self):
        # Has to destroy count_label explicitly because the main loop will try to use it otherwise.
        # Just setting to None is not good enough (and I do not know why).
        self.power_label.destroy()
        self.power_label = None
        self.count_label.destroy()
        self.count_label = None
        self.destroy()
        request['action'] = 'terminate'
        print('INFO: GUI terminated.')

    def about_function(self):
        """ Menu response. """
        messagebox.showinfo("About", "This software was created by Andy Joel for Preston&District MRS, copyright 2024.")

    def help_function(self):
        """ Menu response. """
        messagebox.showinfo("Help", "Each row controls a servo. Switch the point from left to right and back using On/Off.\n\nThe first angle is the target - what the servo is heading for. The second angle is the current value.\n\nUse Up and Down to modify the target angle.\n\nRemember to do File - Save to save your changes before you exit the program.")


"""
Set the angle for each servo
Need to do this to ensure the servos are where we expect them to be.
Have already set the current angle in the initialiser
Do it in sequence with slight delay so only drawing minimal power
"""
if config.ON_LINE:
    for servo in servos:
        # print('INFO: Setting servo ' + servo.id() + ' to OFF')
        try:
            servo.servo.angle = servo.current_angle / 100
            if servo.relay:
                servo.relay.set(True)
        except OSError as err:
            print("ERROR: OSError {err}")
            print("This may be because there is no ground or power connection\nto the servo board on the I2C side")
            print("Terminating!")
            exit()
        time.sleep(0.1)
        servo.servo.angle = None


print("INFO: About to open GUI")

window = ServoWindow()
print("INFO: GUI 1")
if config.SHOW_TRACKPLAN:
    TrackPlan.show()
    window.geometry("+%d+%d" %(10, config.HEIGHT + 150))
print("INFO: GUI 2")
window.mainloop()
print("INFO: GUI running")
