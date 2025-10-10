#!/usr/bin/env python3

import sys
import os
import fcntl
import time

from lib.argument_parser import ArgumentParser
from lib.component_initializer import ComponentInitializer
from lib.functions import fastColorWipe, screensaver, \
    manage_idle_animation
from lib.gpio_handler import GPIOHandler
from lib.led_effects_processor import LEDEffectsProcessor
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.log_setup import logger
from lib.menulcd import MenuLCD
from lib.midi_event_processor import MIDIEventProcessor
from lib.color_mode import ColorMode
from lib.webinterface_manager import WebInterfaceManager

from lib.log_setup import logger


def restart_script():
    """Restart the current script."""
    python = sys.executable
    os.execl(python, python, *sys.argv)


class VisualizerApp:
    def __init__(self):
        self.fh = None
        self.ensure_singleton()
        os.chdir(sys.path[0])

        # State tracking
        self.last_sustain = 0
        self.pedal_deadzone = 10

        # Initialize components
        self.args = ArgumentParser().args
        self.component_initializer = ComponentInitializer(self.args)

        # Check and enable SPI if running on Raspberry Pi
        if hasattr(self.component_initializer.platform, 'check_and_enable_spi'):
            self.component_initializer.platform.check_and_enable_spi()

        self.color_mode = ColorMode(self.component_initializer.ledsettings.color_mode,
                                    self.component_initializer.ledsettings)
        self.color_mode_name = self.component_initializer.ledsettings.color_mode
        self.gpio_handler = GPIOHandler(self.args, self.component_initializer.midiports, self.component_initializer.menu,
                                        self.component_initializer.ledstrip, self.component_initializer.ledsettings,
                                        self.component_initializer.usersettings)
        self.web_interface_manager = WebInterfaceManager(self.args, self.component_initializer.usersettings,
                                                         self.component_initializer.ledsettings,
                                                         self.component_initializer.ledstrip,
                                                         self.component_initializer.learning,
                                                         self.component_initializer.saving,
                                                         self.component_initializer.midiports,
                                                         self.component_initializer.menu,
                                                         self.component_initializer.hotspot,
                                                         self.component_initializer.platform)
        self.midi_event_processor = MIDIEventProcessor(self.component_initializer.midiports,
                                                       self.component_initializer.ledstrip,
                                                       self.component_initializer.ledsettings,
                                                       self.component_initializer.usersettings,
                                                       self.component_initializer.saving,
                                                       self.component_initializer.learning,
                                                       self.component_initializer.menu,
                                                       self.color_mode)
        self.led_effects_processor = LEDEffectsProcessor(self.component_initializer.ledstrip,
                                                         self.component_initializer.ledsettings,
                                                         self.component_initializer.menu,
                                                         self.color_mode,
                                                         self.last_sustain,
                                                         self.pedal_deadzone)

        # Frame rate counters
        self.event_loop_stamp = time.perf_counter()
        self.frame_count = 0
        self.frame_avg_stamp = time.perf_counter()
        self.backlight_cleared = False

        # State tracking
        self.display_cycle = 0
        self.screen_hold_time = 16
        self.ledshow_timestamp = time.time()

    def ensure_singleton(self):
        self.fh = open(os.path.realpath(__file__), 'r')
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as error:
            logger.warning(f"[ensure_singleton] Unexpected exception occurred: {error}")
            restart_script()

<<<<<<< HEAD
logger.info(args)

appmap = map.MidiToLedMapping()

# pins are interpreted as BCM pins.
GPIO.setmode(GPIO.BCM)

usersettings = UserSettings()
midiports = MidiPorts(appconfig, usersettings)
ledsettings = LedSettings(appconfig, usersettings)
ledstrip = LedStrip(appconfig, usersettings, ledsettings, args.leddriver)
=======
    def run(self):
        self.component_initializer.platform.manage_hotspot(self.component_initializer.hotspot,
                                                            self.component_initializer.usersettings,
                                                            self.component_initializer.midiports, True)

        while True:
            try:
                elapsed_time = time.perf_counter() - self.component_initializer.saving.start_time
            except Exception as e:
                logger.warning(f"[elapsed time calculation] Unexpected exception occurred: {e}")
                elapsed_time = 0

            self.check_screensaver()
            manage_idle_animation(self.component_initializer.ledstrip, self.component_initializer.ledsettings,
                                  self.component_initializer.menu, self.component_initializer.midiports)
            self.check_activity_backlight()
            self.update_display(elapsed_time)
            self.check_color_mode()
            self.check_settings_changes()
            self.component_initializer.platform.manage_hotspot(self.component_initializer.hotspot,
                                                                self.component_initializer.usersettings,
                                                                self.component_initializer.midiports)
            self.gpio_handler.process_gpio_keys()

            event_loop_time = time.perf_counter() - self.event_loop_stamp
            self.event_loop_stamp = time.perf_counter()

            self.led_effects_processor.process_fade_effects(event_loop_time)
            self.midi_event_processor.process_midi_events()

            self.component_initializer.ledstrip.strip.show()
            self.update_fps_stats()
>>>>>>> upstream/master

    def update_fps_stats(self):
        self.frame_count += 1
        frame_seconds = time.perf_counter() - self.frame_avg_stamp

        if frame_seconds >= 2:
            fps = self.frame_count / frame_seconds
            self.component_initializer.ledstrip.current_fps = fps

<<<<<<< HEAD
learning = LearnMIDI(usersettings, ledsettings, midiports, ledstrip)
hotspot = Hotspot(platform)
menu = MenuLCD(
    "config/menu.xml",
    usersettings,
    ledsettings,
    ledstrip,
    learning,
    midiports,
    hotspot,
    platform,
)

midiports.add_instance(menu)
ledsettings.add_instance(menu, ledstrip)
learning.add_instance(menu)

menu.show()
z = 0
display_cycle = 0
screen_hold_time = 16

midiports.last_activity = time.time()
hotspot.hotspot_script_time = time.time()

last_sustain = 0
pedal_deadzone = 10
ledshow_timestamp = time.time()
color_mode_name = ""


def start_webserver():
    if not args.port:
        args.port = 80

    webinterface.usersettings = usersettings
    webinterface.ledsettings = ledsettings
    webinterface.ledstrip = ledstrip
    webinterface.learning = learning
    webinterface.midiports = midiports
    webinterface.menu = menu
    webinterface.hotspot = hotspot
    webinterface.platform = platform

    webinterface.appconfig = appconfig
    webinterface.appmap = appmap

    webinterface.jinja_env.auto_reload = True
    webinterface.config["TEMPLATES_AUTO_RELOAD"] = True
    # webinterface.run(use_reloader=False, debug=False, port=80, host='0.0.0.0')
    serve(webinterface, host="0.0.0.0", port=args.port, threads=20)


websocket_loop = asyncio.new_event_loop()

logger.info("Starting webinterface")
processThread = threading.Thread(target=start_webserver, daemon=True)
processThread.start()

# Start websocket server
processThread = threading.Thread(
    target=web_mod.start_server, args=(websocket_loop,), daemon=True
)
processThread.start()

# Register the shutdown handler
atexit.register(web_mod.stop_server, websocket_loop)


platform.manage_hotspot(hotspot, usersettings, midiports, True)

# Frame rate counters
event_loop_stamp = time.perf_counter()
frame_count = 0
frame_avg_stamp = time.perf_counter()
backlight_cleared = False
# Main event loop

strip = ledstrip.strip
numPixels = strip.numPixels()
strip.setBrightness(128)
for i in range(0, numPixels):
    strip.setPixelColor(i, Color(0, 0, 0))
strip.show()

while True:
    # Save settings if changed
    if (time.time() - usersettings.last_save) > 1:
        if usersettings.pending_changes:
            usersettings.save_changes()
        if usersettings.pending_reset:
            usersettings.pending_reset = False
            ledsettings = LedSettings(usersettings)
            ledstrip = LedStrip(usersettings, ledsettings)
            menu = MenuLCD(
                "config/menu.xml",
                usersettings,
                ledsettings,
                ledstrip,
                learning,
                midiports,
                hotspot,
                platform,
            )
            menu.show()
            ledsettings.add_instance(menu, ledstrip)

    platform.manage_hotspot(hotspot, usersettings, midiports)

    # Prep midi event queue
    if learning.is_started_midi is False:
        midiports.midipending = midiports.midi_queue
    else:
        midiports.midipending = midiports.midifile_queue
=======
            self.frame_avg_stamp = time.perf_counter()
            self.frame_count = 0

    def check_screensaver(self):
        if int(self.component_initializer.menu.screensaver_delay) > 0:
            if (time.time() - self.component_initializer.midiports.last_activity) > (int(self.component_initializer.menu.screensaver_delay) * 60):
                screensaver(self.component_initializer.menu, self.component_initializer.midiports,
                            self.component_initializer.saving, self.component_initializer.ledstrip,
                            self.component_initializer.ledsettings)

    def check_activity_backlight(self):
        if (time.time() - self.component_initializer.midiports.last_activity) > 120:
            if not self.backlight_cleared:
                self.component_initializer.ledsettings.backlight_stopped = True
                fastColorWipe(self.component_initializer.ledstrip.strip, True,
                              self.component_initializer.ledsettings)
                self.backlight_cleared = True
        else:
            if self.backlight_cleared:
                self.component_initializer.ledsettings.backlight_stopped = False
                fastColorWipe(self.component_initializer.ledstrip.strip, True,
                              self.component_initializer.ledsettings)
                self.backlight_cleared = False

    def update_display(self, elapsed_time):
        if self.display_cycle >= 3:
            self.display_cycle = 0
            if elapsed_time > self.screen_hold_time:
                self.component_initializer.menu.show()
        self.display_cycle += 1

    def check_color_mode(self):
        if self.component_initializer.ledsettings.color_mode != self.color_mode_name or self.component_initializer.ledsettings.incoming_setting_change:
            self.component_initializer.ledsettings.incoming_setting_change = False
            self.color_mode = ColorMode(self.component_initializer.ledsettings.color_mode,
                                        self.component_initializer.ledsettings)
            self.color_mode_name = self.component_initializer.ledsettings.color_mode
            # Reinitialize MIDIEventProcessor and LEDEffectsProcessor with the new color_mode
            self.midi_event_processor.color_mode = self.color_mode
            self.led_effects_processor.color_mode = self.color_mode
            logger.info(f"Color mode changed to {self.color_mode_name}")

    def check_settings_changes(self):
        if (time.time() - self.component_initializer.usersettings.last_save) > 1:
            if self.component_initializer.usersettings.pending_changes:
                self.color_mode.LoadSettings(self.component_initializer.ledsettings)
                self.component_initializer.usersettings.save_changes()

            if self.component_initializer.usersettings.pending_reset:
                self.component_initializer.usersettings.pending_reset = False
                self.component_initializer.ledsettings = LedSettings(self.component_initializer.usersettings)
                self.component_initializer.ledstrip = LedStrip(self.component_initializer.usersettings,
                                                                self.component_initializer.ledsettings)
                self.component_initializer.menu = MenuLCD("config/menu.xml", self.args,
                                                          self.component_initializer.usersettings,
                                                          self.component_initializer.ledsettings,
                                                          self.component_initializer.ledstrip,
                                                          self.component_initializer.learning,
                                                          self.component_initializer.saving,
                                                          self.component_initializer.midiports,
                                                          self.component_initializer.hotspot,
                                                          self.component_initializer.platform)
                self.component_initializer.menu.show()
                self.component_initializer.ledsettings.add_instance(self.component_initializer.menu,
                                                                     self.component_initializer.ledstrip)


if __name__ == "__main__":
    app = VisualizerApp()
    app.run()
>>>>>>> upstream/master
