# Configuration constants

ON_LINE = False   # Set to False to test without connecting to I2C
QUIT_WITHOUT_CONFIRM = True
TIME_FACTOR = 10.0
REPORT_SERVO_SWITCHING = True
NUMBER_OF_ROWS = 10   # If you have less servos or LEDS or buttons than this it will crash!!!
INCREMENT = 5


# general Python Imports
import time
import re
import sys
from threading import Thread


if ON_LINE:
    # Imports for I2C
    import board
    import digitalio
    import adafruit_pcf8575
    import I2C_LCD_driver
    from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C
    from adafruit_servokit import ServoKit

# Imorts for GUI
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import font, Menu, messagebox, PhotoImage, Toplevel, Scrollbar, TclError, TclError
#import PIL as pil
#from PIL import Image, ImageTk


print("Starting up...")






#################################################################################
# Represents a servo
# Works in hundredths of degrees internally
# The real servo is identified by cluster and number
# Has an "on" angle and an "off" angle, which can be either way around
class Servo:
    count = 0

    # Adds a servo object, given a string
    # The string should consist of an "s" to identify it as a servo
    # followed by (all separated with spaces):
    #    the address - the board number, a dot and the pin number
    #    the speed
    #    the off angle
    #    the on angle
    #    the descriptor
    def create(lst, s):
        md = re.match('s (\\d+)\\.(\\d+),? (\\d+),? (\\d+),? (\\d+),? ?(.*)', s)
        if md:
            servo = Servo(int(md.group(1)), int(md.group(2)), int(md.group(3)), int(md.group(4)), int(md.group(5)), md.group(6))
            lst.append(servo)
            return servo
        else:
            print('ERROR: Badly formatted line for servo: ' + s)
            return None
   
    def __init__(self, _board_no, _pin_no, _speed, _off_angle, _on_angle, _desc=None):
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
        return f'{self.board_no}.{self.pin_no}'

    def write_to_file(self, f):
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
        self.widget = _widget

    def set_led(self, led, turn_on):
        if turn_on:
            self.on_leds.append(led)
        else:
            self.off_leds.append(led)

    def set_button(self, button, turn_on):
        if turn_on:
            self.on_buttons.append(button)
        else:
            self.off_buttons.append(button)

    def set(self, _turn_on):
        self.target_angle = self.on_angle if _turn_on else self.off_angle
        self.turn_on = _turn_on
        if REPORT_SERVO_SWITCHING:
            state = 'ON' if _turn_on else 'OFF'
            print(f'INFO: Setting servo {self.board_no}.{self.pin_no} ({self.desc}) to {state}')
        
    def set_angle(self, angle):
        self.target_angle = angle * 100

    def get_target_angle(self):
        return str(round(self.target_angle / 100)) + '°'

    def get_current_angle(self):
        return str(round(self.current_angle / 100)) + '°'

    def get_on_angle(self):
        return str(round(self.on_angle / 100)) + '°'

    def get_off_angle(self):
        return str(round(self.off_angle / 100)) + '°'

    def adjust(self, elapsed):
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
       
        #print(self.status())
        if self.widget:
            self.widget.config(text=self.get_current_angle())
        return True

    def status(self):
        return str(self.current_angle) + "/" + str(self.target_angle)

    def reset_leds(self):
        for led in self.on_leds:
            led.set(False)
        for led in self.off_leds:
            led.set(False)
        
    def set_leds(self):
        if self.target_angle == self.on_angle:
            for led in self.on_leds:
                led.set(True)
        else:
            for led in self.off_leds:
                led.set(True)






#############################################
# represents an IOPin, super class for buttons and LEDs
class IOPin:

    # Adds a telltale object, given a string
    # The string should consist of a "l" (for LED) to identify it as a telltale
    # followed by (all separated with spaces):
    #    on/off
    #    the address - the board number, a dot and the pin number
    def create(klass, lst, not_lst, letter, s, servos):
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

    def id(self):
        return f'{self.board_no}.{self.pin_no}'

    def servo_list(lst):
        lst2 = []
        for servo in lst:
            lst2.append(servo.id())
        return '/'.join(lst2)

    def list_off_servos(self):
        s= IOPin.servo_list(self.off_servos)
        print('off', s)
        return s

    def list_on_servos(self):
        s= IOPin.servo_list(self.on_servos)
        print('on', s)
        return s

    def find_in_list(lst, board_no, pin_no):
        for el in lst:
            if el.board_no == board_no and el.pin_no == pin_no:
                return el
        return None
        
    def __init__(self, _board_no, _pin_no):
        self.board_no = _board_no
        self.pin_no = _pin_no
        self.on_servos = []
        self.off_servos = []
       
    def set_servo(self, servo, turn_on):
        if turn_on:
            self.on_servos.append(servo)
        else:
            self.off_servos.append(servo)
            
        
    #def desc(self):
    #    return f'On: {IOPin.servo_list(self.on_servos)} Off: {IOPin.servo_list(self.off_servos)}'


#############################################
# represents an LED
class Telltale(IOPin):
    count = 0

    # Adds a telltale object, given a string
    # The string should consist of a "l" (for LED) to identify it as a telltale
    # followed by (all separated with spaces):
    #    on/off
    #    the address - the board number, a dot and the pin number
    def create(s, servos):
        led, turn_on = IOPin.create(Telltale, telltales, buttons, 'l', s, servos)
        servo.set_led(led, turn_on)


    def __init__(self, _board_no, _pin_no):
        super().__init__(_board_no, _pin_no)
        if ON_LINE:
            self.led = io_boards[self.board_no].get_pin(self.pin_no)
            self.led.switch_to_output(value=True)
        self.index = Telltale.count
        print(self.index)
        Telltale.count += 1
       
    def set(self, value):
        print(value)
        print(self.index)
        if ON_LINE:
            self.led.value = not value


#############################################
# represents a push button
class PButton(IOPin):
    count = 0

    # Adds a button object, given a string
    # The string should consist of a "b" to identify it as a button
    # followed by (all separated with spaces):
    #    on/off
    #    the address - the board number, a dot and the pin number
    def create(s, servos):
        button, turn_on = IOPin.create(PButton, buttons, telltales, 'b', s, servos)
        servo.set_button(button, turn_on)

    def __init__(self, _board_no, _pin_no):
        super().__init__(_board_no, _pin_no)
        if ON_LINE:
            self.button = io_boards[self.board_no].get_pin(self.pin_no)
            self.button.switch_to_input(pull=digitalio.Pull.UP)
        self.widget = None
        self.index = PButton.count
        PButton.count += 1
 
    # Only access the button state through this as it has exception handling
    # to deal with issues (hopefully) and for testing with no I2C connected
    def get(self):
        if not ON_LINE:
            return False
        
        try:
            return not self.button.value
        except OSError:
            print('ERROR: Got an OSError, possibly because I am trying to read a board that does not exist or is faulty?')
            print(f'board={self.board} pin={self.pin}')

    def set_widget(self, widget):
        self.widget = widget

    def check_state(self):
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
        except AttributeError:
            print('.')



#########################################################################
# Initialise arrays, etc.

previous_time = time.time()

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
telltales = []
buttons = []






##################################################
# SAVING AND LOADING


"""
We can record everything to file so it is saved for next time

Text file, servo.txt
Each line indicates a thing
If it starts "s", it is a servo, etc
Note that board addresses are in hex, other numbers are not!
Does some checks on loading, but aimed at spotting bad connections, etc.
Does not check for repeated addresses

S0x40
S0x41
IO0x24
LCD0x20

s 0.0, 1000, 0, 170, one
b on 0.1
b off 0.2
l on 0.12
l off 0.13

s 0.1, 3000, 30, 120, servo 2
b on 0.3
b off 0.4
l on 0.14
l off 0.15

s 0.3, 1000, 0, 90, number 3
b on 0.3
b off 0.4

s 0.1, 1000, 0, 170, 
b on 0.5
b off 0.6

s 0.2, 4000, 170, 0, five

s 0.3, 4000, 0, 30, six



"""

def save():
    with open('servo.txt', 'w', encoding="utf-8") as f:
        # Save the boards
        for servo_board in servo_boards:
            f.write(f'S{hex(servo_board._pca.i2c_device.device_address)}\n')
        for io_board in io_boards:
            f.write(f'IO{hex(io_board.i2c_device.device_address)}\n')
        for lcd_board in lcd_boards:
            f.write(f'LCD{hex(lcd_board.lcd_device.addr)}\n')

        # Now save the servos and related data
        for servo in servos:
            servo.write_to_file(f)
#            f.write(f's {servo.board_no}.{servo.number}, {servo.speed}, {round(servo.off_angle / 100)}, {round(servo.on_angle / 100)}, {servo.desc}\n')
        #for telltale in telltales:
        #    f.write(f's {telltale.board_no}.{telltale.number}, {telltale.desc}\n')
        #for button in buttons:
        #    f.write(f's {button.board_no}.{button.number}, {button.desc}\n')
    print("Save successful")



# We can check devices are connected as they are loaded from file
# so first get a list of addresses on the I2C bus
if ON_LINE:
    i2c_devices = i2c.scan()
    print("INFO: Found I2C devices:", [hex(device_address) for device_address in i2c_devices])


# Adds an I2C board, given a string
# The string should consist of the board type identifier - one or more letters in upper case
# followed directly by the addess in hexadecimal (use lower case letters if required!)
def load_device(line):
    if not ON_LINE:
        return
        
    md = re.match('([A-Z]+)(?:0x|)([0-9a-f]+)', line)
    if not md:
        print('ERROR: Badly formatted line: ' + line)
        return
   
    address = int(md.group(2), 16)
    if not address in i2c_devices:
        print('ERROR: Device not found: ' + line)
        return False                
    match md.group(1):
        case 'S':
            servo_boards.append(ServoKit(channels=16, address=address))
        case 'IO':
            io_boards.append(adafruit_pcf8575.PCF8575(i2c, address))
        case 'LCD':
            lcd_boards.append(I2C_LCD_driver.lcd())
        case 'UPS':
            ups_boards.append(ServoKit(channels=16, address=address)) # !!!
        case _:
            print('ERROR: Device code not recognised: ' + line)

try:
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
                Telltale.create(line, servo)
            # etc!!!
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
print(f"INFO: Found {len(telltales)} LED(s).")
print(f"INFO: Found {len(buttons)} button(s).")


        


##############################################################################
# Command line
#
# For testing it is good to be able to type requests to set the servo, and this function handles that
# It runs in its own thread, and sets the global variable "req" when a request is made
req = { 'action':False, 'testing':True}
patterns = [
    re.compile("^(exit|quit|x)$", re.IGNORECASE),
    re.compile("^(\\d+) (\\d+)$"),
    re.compile("^(\\d+) on$", re.IGNORECASE),
    re.compile("^(\\d+) off$", re.IGNORECASE),
    re.compile("^l(\\d+) on$", re.IGNORECASE),
    re.compile("^l(\\d+) off$", re.IGNORECASE),
]

def input_loop():
    while not req['action'] == 'terminate':
        s = input()
        print("Got: " + s)
        mds = []
        for pattern in patterns:
            mds.append(pattern.match(s))
        if mds[0]:
            req['action'] = 'terminate'
        elif mds[1]:
            req['action'] = 'angle'
            req['servo'] = int(mds[1].group(1))
            req['angle'] = int(mds[1].group(2))
        elif mds[2]:
            print('servo on')
            req['action'] = 'on'
            req['servo'] = int(mds[2].group(1))
        elif mds[3]:
            print('servo off')
            req['action'] = 'off'
            req['servo'] = int(mds[3].group(1))
        elif mds[4]:
            print('LED on')
            req['action'] = 'LED on'
            req['servo'] = int(mds[4].group(1))
        elif mds[5]:
            print('LED off')
            req['action'] = 'LED off'
            req['servo'] = int(mds[5].group(1))
        else:
            print("Input commands in the form x y")
            print(req)
   



#############################################################
# MAIN LOOP
#
# Main loop:
#    handles time
#    checks if buttons have been pressed
#    responds to requestion from the command line/GUI
#    moves servo
# ... but most of the work is done elsewhere
def main_loop():
    global previous_time, count_label, loop_count
    print('INFO: Starting the main loop')
    while not req['action'] == 'terminate':
        # HANDLE TIME
        now_time = time.time() # !!!
        elapsed = now_time - previous_time
        previous_time = now_time
        increment = TIME_FACTOR * elapsed
        
        """
        # If the GUI is up, then count_label is a Label object
        # and can be updated with the loop count to show it is going
        # and indicate how fast. Cap at a million so no chance of overflow.
        # !!! prevents graceful exit !!!
        if count_label:
            count_label.config(text=str(loop_count))
            loop_count += 1
            if loop_count > 999999:
                loop_count = 0
        """    


        # HANDLE INPUTS
        for button in buttons:
            button.check_state()
           
        # HANDLE INPUT REQUESTS
        if req['action'] == 'angle':
            if req['servo'] >= len(servos):
                print("WARNING: Servo out of range (0-" + str(len(servos)) + ")")
            else:
                servos[req['servo']].set_angle(req['angle'])
            req['action'] = False

        if req['action'] == 'on':
            if req['servo'] >= len(servos):
                print("WARNING: Servo out of range (0-" + str(len(servos)) + ")")
            else:
                servos[req['servo']].set(True)
            req['action'] = False

        if req['action'] == 'off':
            if req['servo'] >= len(servos):
                print("WARNING: Servo out of range (0-" + str(len(servos)) + ")")
            else:
                servos[req['servo']].set(False)
            req['action'] = False

        if req['action'] == 'LED on':
            if req['servo'] >= len(telltales):
                print("WARNING: LED out of range (0-" + str(len(telltales)) + ")")
            else:
                telltales[req['servo']].set(True)
            req['action'] = False
        if req['action'] == 'LED off':
            if req['servo'] >= len(telltales):
                print("WARNING: LED out of range (0-" + str(len(telltales)) + ")")
            else:
                telltales[req['servo']].set(False)
            req['action'] = False
        if req['action'] == 'all LED on':
            for telltale in telltales:
                telltale.set(True)
            req['action'] = False
        if req['action'] == 'all LED off':
            for telltale in telltales:
                telltale.set(False)
            req['action'] = False



        # HANDLE SERVOS
        moving_flag = False;
        for servo in servos:
            if servo.adjust(increment):
                moving_flag = True

        time.sleep(0.01)





###################################################################
# THREADING
# 
# We have three threads, one that does the work, for for the GUI,
# one for the command line.

# The command line is a daemon thread - no need to shutdown gracefully
input_thread = Thread(target = input_loop)
input_thread.daemon = True
input_thread.start()

# The main loop is not a daemon thread, it might be in the middle of doing stuff
# not sure if this is an issue, but just in case
# has to be stopped by setting req['action'] = 'terminate'
count_label = None
loop_count = 0
Thread(target = main_loop).start()  #!!!!!

# The GUI is done in the defaut thread; no need to define a new one





######################################################################
# The GUI

# Some globals that track which ones are being displayed
# If servo_offset is 10, then we show servos 10 to 29
servo_offset = 0
button_offset = 0
led_offset = 0




class ButtonsWindow(tk.Toplevel):
    """ Define a special child window that stops buttons trying to update it when it is destroyed"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def destroy(self):
        for i in range(len(buttons)):
            buttons[i].set_widget(None)        
        return super().destroy()

class ServoGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one servo,
    and buttons and labels on the row will change and reflect its state, but
    which servo that is can vary depending on what servo_offset is.
    """
    def find_row(widget):
        """ Finds the row associated with a button press """
        for row in servo_grid_rows:
            if row.btn_up == widget or row.btn_down == widget or row.btn_on_off == widget:
                return row

    def headers():
        ttk.Label(text='#', font=heading_font).grid(column=0, row=0)
        ttk.Label(text='Identity', width=20, font=heading_font).grid(column=1, row=0)
        ttk.Label(text='Switch', font=heading_font).grid(column=2, row=0)
        ttk.Label(text='State', width=10, font=heading_font).grid(column=3, row=0)
        ttk.Label(text='Target', width=10, font=heading_font).grid(column=6, row=0)
        ttk.Label(text='Current', width=10, font=heading_font).grid(column=7, row=0)

    def __init__(self, row):
        # When creating, the first servo is 0
        self.row = row             # The row in the table in the GUI
        self.servo = servos[row]   # The current servo - but can change
        self.lbl_index = ttk.Label(text=str(row), font=label_font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_desc = ttk.Label(text=self.servo.desc, width=20, font=label_font)
        self.lbl_desc.grid(column=1, row=1 + row)

        self.btn_on_off = ttk.Button(text="On/Off")
        self.btn_on_off.grid(column=2, row=1 + row)
        self.btn_on_off.bind("<Button-1>", on_off_button_pressed)
       
        self.lbl_state = ttk.Label(text='OFF', width=10, font=label_font)    
        self.lbl_state.grid(column=3, row=1 + row)
       
        self.btn_up = ttk.Button(text="Up")
        self.btn_up.grid(column=4, row=1 + row)
        self.btn_up.bind("<Button-1>", up_button_pressed)
        self.btn_up.index = row
       
        self.btn_down = ttk.Button(text="Down")
        self.btn_down.grid(column=5, row=1 + row)
        self.btn_down.bind("<Button-1>", down_button_pressed)
       
        self.lbl_target_angle = ttk.Label(text=self.servo.get_target_angle(), width=10, font=label_font)
        self.lbl_target_angle.grid(column=6, row=1 + row)
       
        self.lbl_current_angle = ttk.Label(text=self.servo.get_current_angle(), width=10, font=label_font)
        self.lbl_current_angle.grid(column=7, row=1 + row)
        self.servo.set_widget(self.lbl_current_angle)

    def update(self):
        """
        Updates the row for a new servo (or no servo) when servo_offset changes
        """
        if 0 <= (self.row + servo_offset) < len(servos):
            self.servo = servos[self.row + servo_offset]
            self.lbl_index.config(text=str(self.row + servo_offset))
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
            self.lbl_desc.config(text='---')
            self.lbl_state.config(text='---')    
            self.lbl_target_angle.config(text='---')
            self.lbl_current_angle.config(text='---')
            #print(f'no servo')

    
    def on_off_button(self):
        """ When the On/Off button for this row is pressed. """
        if not self.servo:
            print('BAD INPUT: No servo at row')
            return

        if self.servo.turn_on:
            self.lbl_state.config(text='OFF')
            self.lbl_target_angle.config(text=self.servo.get_off_angle())
            req['action'] = 'off'
            req['servo'] = self.servo.index
        else:
            self.lbl_state.config(text='ON')
            self.lbl_target_angle.config(text=self.servo.get_on_angle())
            req['action'] = 'on'
            req['servo'] = self.servo.index


    def up_button(self):
        """ When the Up button for this row is pressed. """
        if not self.servo:
            print('No servo at row')
            return

        if self.servo.turn_on:
            if self.servo.on_angle > 16000:
                print('BAD INPUT: Cannot go over 170')
                return
            self.servo.on_angle += 1000
           
        else:
            if self.servo.off_angle > 16000:
                print('BAD INPUT: Cannot go over 170')
                return
            self.servo.off_angle += 1000

        self.servo.target_angle += 1000
        self.lbl_target_angle.config(text=self.servo.get_target_angle())


    def down_button(self):
        """ When the Down button for this row is pressed. """
        if not self.servo:
            print('No servo at row')
            return

        if self.servo.turn_on:
            if self.servo.on_angle < 2000:
                print('BAD INPUT: Cannot go under 10')
                return
            self.servo.on_angle -= 1000
           
        else:
            if self.servo.off_angle < 2000:
                print('BAD INPUT: Cannot go under 10')
                return
            self.servo.off_angle -= 1000

        self.servo.target_angle -= 1000
        self.lbl_target_angle.config(text=self.servo.get_target_angle())

class ButtonGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one (real) button,
    and buttons and labels on the row will change and reflect its state, but
    which (real) button that is can vary depending on what button_offset is.
    """
    def headers(win):
        ttk.Label(win, text='#', font=heading_font).grid(column=0, row=0)
        ttk.Label(win, text='ID', width=5, font=heading_font).grid(column=1, row=0)
        ttk.Label(win, text='Off servos', width=20, font=heading_font).grid(column=2, row=0)
        ttk.Label(win, text='On servos', width=20, font=heading_font).grid(column=3, row=0)
        ttk.Label(win, text='State', font=heading_font, width=7).grid(column=4, row=0)

    def __init__(self, win, row):
        # When creating, the first button is 0
        self.row = row             # The row in the table in the GUI
        self.lbl_index = ttk.Label(win, text=str(row), font=label_font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_desc = ttk.Label(win, text='---', width=20, font=label_font)
        self.lbl_desc.grid(column=1, row=1 + row, sticky='w')

        self.lbl_off_list = ttk.Label(win, text='---', width=20, font=label_font)
        self.lbl_off_list.grid(column=2, row=1 + row, sticky='w')

        self.lbl_on_list = ttk.Label(win, text='---', width=20, font=label_font)
        self.lbl_on_list.grid(column=3, row=1 + row, sticky='w')

        self.lbl_state = ttk.Label(win, text='---', width=7, font=label_font)    
        self.lbl_state.grid(column=4, row=1 + row)
        self.update()


    def update(self):
        """
        Updates the row for a new button (or no button) when button_offset changes
        """
        if 0 <= (self.row + button_offset) < len(buttons):
            self.button = buttons[self.row + button_offset]
            self.lbl_index.config(text=str(self.row + button_offset))
            self.lbl_desc.config(text=self.button.id())
            self.lbl_off_list.config(text=self.button.list_off_servos())
            self.lbl_on_list.config(text=self.button.list_on_servos())
            self.button.set_widget(self.lbl_state)
        else:
            self.button = None
            self.lbl_index.config(text='---')
            self.lbl_desc.config(text='---')
            self.lbl_state.config(text='---')    
            self.lbl_off_list.config(text='---')
            self.lbl_on_list.config(text='---')


class TelltaleGridRow():
    """
    Represents a row on the grid of the GUI. This will correspond to one LED (telltale),
    and buttons and labels on the row will change and reflect its state, but
    which LED that is can vary depending on what led_offset is.
    """
    def find_row(widget):
        """ Finds the row associated with a button press """
        for row in led_grid_rows:
            if row.btn_on == widget or row.btn_off == widget:
                return row

    def headers(win):
        ttk.Label(win, text='#', font=heading_font).grid(column=0, row=0)
        ttk.Label(win, text='ID', width=5, font=heading_font).grid(column=1, row=0)
        ttk.Label(win, text='Off servos', width=20, font=heading_font).grid(column=2, row=0)
        ttk.Label(win, text='On servos', width=20, font=heading_font).grid(column=3, row=0)


    def __init__(self, win, row):
        # When creating, the first button is 0
        self.row = row             # The row in the table in the GUI
        self.lbl_index = ttk.Label(win, text=str(row), font=label_font)
        self.lbl_index.grid(column=0, row=1 + row, pady=5)
       
        self.lbl_desc = ttk.Label(win, text='---', width=20, font=label_font)
        self.lbl_desc.grid(column=1, row=1 + row, sticky='w')

        self.lbl_off_list = ttk.Label(win, text='---', width=20, font=label_font)
        self.lbl_off_list.grid(column=2, row=1 + row, sticky='w')

        self.lbl_on_list = ttk.Label(win, text='---', width=20, font=label_font)
        self.lbl_on_list.grid(column=3, row=1 + row, sticky='w')

        self.btn_on = ttk.Button(win, text="On")
        self.btn_on.grid(column=4, row=1 + row)
        self.btn_on.bind("<Button-1>", led_on_button_pressed)
       
        self.btn_off = ttk.Button(win, text="Off")
        self.btn_off.grid(column=5, row=1 + row)
        self.btn_off.bind("<Button-1>", led_off_button_pressed)

        self.update()



    def update(self):
        """
        Updates the row for a new telltale (or no telltale) when led_offset changes
        """
        if 0 <= (self.row + led_offset) < len(telltales):
            self.telltale = telltales[self.row + led_offset]
            self.lbl_index.config(text=str(self.row + led_offset))
            self.lbl_desc.config(text=self.telltale.id())
            self.lbl_off_list.config(text=self.telltale.list_off_servos())
            self.lbl_on_list.config(text=self.telltale.list_on_servos())
        else:
            self.button = None
            self.lbl_index.config(text='---')
            self.lbl_desc.config(text='---')
            self.lbl_off_list.config(text='---')
            self.lbl_on_list.config(text='---')




# Define some callback functions

def confirm_quit():
    """
    Called when exit is selected from the menu or the x clicked in the top-right,
    this function will ask for confirmation before destroying the window.
    
    
    Checks QUIT_WITHOUT_CONFIRM - when developing the confirmation box is just annoying.
    """
    
    if QUIT_WITHOUT_CONFIRM:
        window.destroy()
    else:
        response = messagebox.askyesno('Exit','Are you sure you want to exit?')
        if response:
            window.destroy()

def up_button_pressed(event):
    """
    Called when an UP button is clicked,
    adds 10 degrees to the target angle.
    """
    ServoGridRow.find_row(event.widget).up_button()

def down_button_pressed(event):
    """
    Called when a DOWN button is clicked,
    adds 10 degrees to the target angle.
    """
    ServoGridRow.find_row(event.widget).down_button()

def on_off_button_pressed(event):
    """
    Called when an ON/OFF button is clicked,
    it changes the state of the servo from off to on or VV.
    """
    ServoGridRow.find_row(event.widget).on_off_button()

def show_led_function():
    """ Responds to a menu click to show the window for LEDs"""

    newWindow = Toplevel(window)
    newWindow.title('LEDs')
    TelltaleGridRow.headers(newWindow)
    for i in range(NUMBER_OF_ROWS):
        led_grid_rows.append(TelltaleGridRow(newWindow, i))
       
def all_led_on_button_pressed():
    """ Responds to a menu click to tirn on all LEDs"""
    req['action'] = 'all LED on'

def all_led_off_button_pressed():
    """ Responds to a menu click to tirn off all LEDs"""
    req['action'] = 'all LED off'

def led_on_button_pressed(event):
    index = TelltaleGridRow.find_row(event.widget).row + led_offset
    req['action'] = 'LED on'
    req['servo'] = index

def led_off_button_pressed(event):
    index = TelltaleGridRow.find_row(event.widget).row + led_offset
    req['action'] = 'LED off'
    req['servo'] = index

def show_button_function():
    newWindow = ButtonsWindow(window)
    newWindow.title('Buttons')
    ButtonGridRow.headers(newWindow)
    for i in range(NUMBER_OF_ROWS):
        button_grid_rows.append(ButtonGridRow(newWindow, i))
       
def about_function():
    messagebox.showinfo("About", "This software was created by Andy Joel for Preston&District MRS, copyright 2024.")

def help_function():
    messagebox.showinfo("Help", "Each row controls a servo. Switch the point from left to right and back using On/Off.\n\nThe first angle is the target - what the servo is heading for. The second angle is the current value.\n\nUse Up and Down to modify the target angle.\n\nRemember to do File - Save to save your changes before you exit the program.")

def offset_plus_10_function():
    global servo_offset
    if servo_offset > len(servos) - 5:
        print('BAD INPUT: Trying to go beyond end!')
        return
    servo_offset += INCREMENT
    set_grid_offset()

def offset_minus_10_function():
    global servo_offset
    if servo_offset == 0:
        print('BAD INPUT: Trying to go beyond start!')
        return
    servo_offset -= INCREMENT
    set_grid_offset()

def led_offset_plus_10_function():
    global led_offset
    if led_offset > len(telltales) - 5:
        print('BAD INPUT: Trying to go beyond end!')
        return
    led_offset += INCREMENT
    set_led_grid_offset()

def led_offset_minus_10_function():
    global led_offset
    if led_offset == 0:
        print('BAD INPUT: Trying to go beyond start!')
        return
    led_offset -= INCREMENT
    set_led_grid_offset()

def button_offset_plus_10_function():
    global button_offset
    if button_offset > len(buttons) - 5:
        print('BAD INPUT: Trying to go beyond end!')
        return
    button_offset += INCREMENT
    set_button_grid_offset()

def button_offset_minus_10_function():
    global button_offset
    if button_offset == 0:
        print('BAD INPUT: Trying to go beyond start!')
        return
    button_offset -= INCREMENT
    set_button_grid_offset()

def set_grid_offset():
    # reset widgets in servos
    for servo in servos:
        servo.set_widget(None)
        
    for row in servo_grid_rows:
        row.update()


def set_button_grid_offset():
    # reset widgets in servos
    # !!! needs to be converted to buttons!
    for button in buttons:
        button.set_widget(None)
        
    for i in range(NUMBER_OF_ROWS):
        if 0 <= (i + button_offset) < len(buttons):
            servo = servos[i + servo_offset]
            lbl_index[i].config(text=str(i + servo_offset))
            lbl_desc[i].config(text=servo.desc)
            state = 'ON' if servo.turn_on else 'OFF'
            lbl_state[i].config(text=state)    
            lbl_target_angle[i].config(text=servo.get_target_angle())
            lbl_current_angle[i].config(text=servo.get_current_angle())
            print(f'set widget {i} for servo {i + servo_offset}')
            servo.set_widget(lbl_current_angle[i])
        else:
            lbl_index[i].config(text='---')
            lbl_desc[i].config(text='---')
            lbl_state[i].config(text='---')    
            lbl_target_angle[i].config(text='---')
            lbl_current_angle[i].config(text='---')
            print(f'no servo')






# Set up arrays of widgets and other variables
window = None
heading_font = None
label_font = None
menu_font = None

btn_led_on = [None] * len(telltales)
btn_led_off = [None] * len(telltales)

servo_grid_rows = []
button_grid_rows = []
led_grid_rows = []


def gui_setup():
    # Create the UI
    # First the basics
    global window, heading_font, label_font, menu_font, count_label
    
    window = tk.Tk()
    window.title("P&D MRS ServoMaster")
    heading_font = font.Font(slant="italic")
    label_font = font.Font()
    menu_font = font.Font(size=14)

    try:
        img = tk.PhotoImage(file='servo_icon.png')
        window.iconphoto(True, img)
    except tk.TclError:
        print('WARNING: Failed to find icon file, "servo_icon.png", but carrying on regardless!')

    window.protocol('WM_DELETE_WINDOW',confirm_quit)



    # Now add some menus
    menubar = Menu(window)
    filemenu = Menu(menubar, tearoff=0, font=menu_font)
    filemenu.add_command(label="Save", command=save, font=menu_font)
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=confirm_quit, font=menu_font)
    menubar.add_cascade(label="File", menu=filemenu, font=menu_font)

    servosmenu = Menu(menubar, tearoff=0)
    servosmenu.add_command(label="Next " + str(INCREMENT), command=offset_plus_10_function, font=menu_font)
    servosmenu.add_command(label="Previous " + str(INCREMENT), command=offset_minus_10_function, font=menu_font)
    menubar.add_cascade(label="Servos", menu=servosmenu, font=menu_font)

    ledsmenu = Menu(menubar, tearoff=0)
    ledsmenu.add_command(label="LEDs...", command=show_led_function, font=menu_font)
    ledsmenu.add_command(label="All on", command=all_led_on_button_pressed, font=menu_font)
    ledsmenu.add_command(label="All off", command=all_led_off_button_pressed, font=menu_font)
    ledsmenu.add_command(label="Next " + str(INCREMENT), command=led_offset_plus_10_function, font=menu_font)
    ledsmenu.add_command(label="Previous " + str(INCREMENT), command=led_offset_minus_10_function, font=menu_font)
    menubar.add_cascade(label="LEDs", menu=ledsmenu, font=menu_font)

    buttonsmenu = Menu(menubar, tearoff=0)
    buttonsmenu.add_command(label="Buttons...", command=show_button_function, font=menu_font)
    buttonsmenu.add_command(label="Next " + str(INCREMENT), command=button_offset_plus_10_function, font=menu_font)
    buttonsmenu.add_command(label="Previous " + str(INCREMENT), command=button_offset_minus_10_function, font=menu_font)
    menubar.add_cascade(label="Buttons", menu=buttonsmenu, font=menu_font)

    helpmenu = Menu(menubar, tearoff=0)
    helpmenu.add_command(label="Help", command=help_function, font=menu_font)
    helpmenu.add_command(label="About...", command=about_function, font=menu_font)
    menubar.add_cascade(label="Help", menu=helpmenu, font=menu_font)

    window.config(menu=menubar)


    # Headings for the main window



    # The widgets that do the work
    ServoGridRow.headers()
    for i in range(NUMBER_OF_ROWS):
        servo_grid_rows.append(ServoGridRow(i))

    ttk.Label(text='Cycle count', font=heading_font).grid(column=6, row=NUMBER_OF_ROWS + 1)
    count_label = ttk.Label(text='---', font=heading_font)
    count_label.grid(column=7, row=NUMBER_OF_ROWS + 1)


    # Set it going
    window.mainloop()

if len(sys.argv) > 1 and sys.argv[1] == 'headless':
   print('Running headless. type "x" and press ENTER to exit.')
else:
    gui_setup()
    # This will run when the GUI is exited
    print('Bye!')
    req['action'] = 'terminate'
    time.sleep(0.1)
    exit()
