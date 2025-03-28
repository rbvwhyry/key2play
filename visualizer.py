#!/usr/bin/env python3

import argparse
import asyncio
import atexit
import fcntl
import os
import sys
import threading
import time

from waitress import serve

import config
import lib.colormaps as cmap
import webinterface as web_mod
from lib.functions import startup_animation
from lib.learnmidi import LearnMIDI
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.log_setup import logger
from lib.menulcd import MenuLCD
from lib.midiports import MidiPorts
from lib.platform import Hotspot, Platform_null, PlatformRasp
from lib.rpi_drivers import GPIO, Color, RPiException
from lib.usersettings import UserSettings
from webinterface import webinterface

os.chdir(sys.path[0])

# Ensure there is only one instance of the script running.
fh = 0


def singleton():
    global fh
    fh = open(os.path.realpath(__file__), "r")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception as error:
        logger.warning(f"Unexpected exception occurred: {error}")
        restart_script()


def restart_script():
    python = sys.executable
    os.execl(python, python, *sys.argv)


singleton()

appmode_default = "platform"
if isinstance(RPiException, RuntimeError):
    # If Raspberry GPIO fails (no Raspberry Pi detected) then set default to app mode
    appmode_default = "app"

parser = argparse.ArgumentParser()
parser.add_argument(
    "-p", "--port", type=int, help="set port for webinterface (80 is default)"
)
parser.add_argument(
    "-s",
    "--skipupdate",
    action="store_true",
    help="Do not try to update /usr/local/bin/connectall.py",
)
parser.add_argument(
    "-a",
    "--appmode",
    default=appmode_default,
    help="appmode: 'platform' (default) | 'app'",
)
parser.add_argument(
    "-l",
    "--leddriver",
    default="rpi_ws281x",
    help="leddriver: 'rpi_ws281x' (default) | 'emu' ",
)
args = parser.parse_args()


if args.appmode == "platform":
    platform = PlatformRasp()
else:
    platform = Platform_null()

if not args.skipupdate:
    platform.copy_connectall_script()

logger.info(args)

appconfig = config.Config()

# pins are interpreted as BCM pins.
GPIO.setmode(GPIO.BCM)

usersettings = UserSettings()
midiports = MidiPorts(appconfig, usersettings)
ledsettings = LedSettings(appconfig, usersettings)
ledstrip = LedStrip(appconfig, usersettings, ledsettings, args.leddriver)

cmap.gradients.update(cmap.load_colormaps())
cmap.generate_colormaps(cmap.gradients, ledstrip.led_gamma)
cmap.update_multicolor(ledsettings.multicolor_range, ledsettings.multicolor)

t = threading.Thread(target=startup_animation, args=(ledstrip, ledsettings))
t.start()

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
