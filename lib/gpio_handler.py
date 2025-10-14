import time
from lib.rpi_drivers import GPIO
from lib.functions import fastColorWipe


class GPIOHandler:
    def __init__(self, args, midiports, ledstrip, ledsettings, usersettings):
        self.args = args
        self.midiports = midiports
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.usersettings = usersettings
        self.setup_gpio()

    def setup_gpio(self):
        if self.args.rotatescreen != "true":
            self.KEYRIGHT = 26
            self.KEYLEFT = 5
            self.KEYUP = 6
            self.KEYDOWN = 19
            self.KEY1 = 21
            self.KEY3 = 16
        else:
            self.KEYRIGHT = 5
            self.KEYLEFT = 26
            self.KEYUP = 19
            self.KEYDOWN = 6
            self.KEY1 = 16
            self.KEY3 = 21

        self.KEY2 = 20
        self.JPRESS = 13
        self.BACKLIGHT = 24

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.KEYRIGHT, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYLEFT, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYUP, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYDOWN, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY1, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY2, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY3, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.JPRESS, GPIO.IN, GPIO.PUD_UP)

    def process_gpio_keys(self):
        if GPIO.input(self.KEYUP) == 0:
            self.midiports.last_activity = time.time()
            while GPIO.input(self.KEYUP) == 0:
                time.sleep(0.001)

        if GPIO.input(self.KEYDOWN) == 0:
            self.midiports.last_activity = time.time()
            while GPIO.input(self.KEYDOWN) == 0:
                time.sleep(0.001)

        if GPIO.input(self.KEY1) == 0:
            self.midiports.last_activity = time.time()
            while GPIO.input(self.KEY1) == 0:
                time.sleep(0.001)

        if GPIO.input(self.KEY2) == 0:
            self.midiports.last_activity = time.time()
            while GPIO.input(self.KEY2) == 0:
                time.sleep(0.01)

        if GPIO.input(self.KEY3) == 0:
            self.midiports.last_activity = time.time()
            if self.ledsettings.sequence_active:
                self.ledsettings.set_sequence(0, 1)
            else:
                active_input = self.usersettings.get_setting_value("input_port")
                secondary_input = self.usersettings.get_setting_value(
                    "secondary_input_port"
                )
                self.midiports.change_port("inport", secondary_input)
                self.usersettings.change_setting_value(
                    "secondary_input_port", active_input
                )
                self.usersettings.change_setting_value("input_port", secondary_input)
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
            while GPIO.input(self.KEY3) == 0:
                time.sleep(0.01)

        if GPIO.input(self.KEYLEFT) == 0:
            self.midiports.last_activity = time.time()
            time.sleep(0.1)

        if GPIO.input(self.KEYRIGHT) == 0:
            self.midiports.last_activity = time.time()
            time.sleep(0.1)

        if GPIO.input(self.JPRESS) == 0:
            self.midiports.last_activity = time.time()
            while GPIO.input(self.JPRESS) == 0:
                time.sleep(0.01)
