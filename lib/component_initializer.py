import threading
import time

from lib import colormaps as cmap
from lib.functions import startup_animation, fastColorWipe
from lib.learnmidi import LearnMIDI
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.log_setup import logger
from lib.midiports import MidiPorts
from lib.platform import PlatformRasp, PlatformNull, Hotspot
from lib.usersettings import UserSettings
from lib.config import Config


class ComponentInitializer:
    def __init__(self, args):
        self.args = args
        self.platform = (
            PlatformRasp() if self.args.appmode == "platform" else PlatformNull()
        )
        self.usersettings = UserSettings()
        self.config = Config()
        self.midiports = MidiPorts(self.config, self.usersettings)
        self.ledsettings = LedSettings(self.config, self.usersettings)
        self.ledstrip = LedStrip(
            self.config, self.usersettings, self.ledsettings, self.args.leddriver
        )
        self.learning = LearnMIDI(
            self.usersettings, self.ledsettings, self.midiports, self.ledstrip
        )
        self.hotspot = Hotspot(self.platform)
        self.setup_components()

    def setup_components(self):
        return
        if not self.args.skipupdate:
            self.platform.copy_connectall_script()
            # Disable system MIDI scripts that use the old connectall behavior
            self.platform.disable_system_midi_scripts()

        self.platform.install_midi2abc()
        logger.info(self.args)

        cmap.gradients.update(cmap.load_colormaps())
        cmap.generate_colormaps(cmap.gradients, self.ledstrip.led_gamma)
        cmap.update_multicolor(
            self.ledsettings.multicolor_range, self.ledsettings.multicolor
        )

        t = threading.Thread(
            target=startup_animation, args=(self.ledstrip, self.ledsettings)
        )
        t.start()

        self.midiports.last_activity = time.time()
        self.hotspot.hotspot_script_time = time.time()

        # Start MIDI device monitoring for auto-connection
        self.midiports.start_midi_monitor()

        fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
