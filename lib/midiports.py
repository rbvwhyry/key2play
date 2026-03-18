import time
from collections import deque

import mido

from lib import connectall
from lib.log_setup import logger


class MidiPorts:
    def __init__(self, config, usersettings):
        self.config = config
        self.usersettings = usersettings
        # midi queues will contain a tuple (midi_msg, timestamp)
        self.midifile_queue = deque()
        self.midi_queue = deque()
        self.last_activity = 0
        self.inport = None
        self.playport = None
        self.midipending = None
        self.currently_pressed_keys = []
        self.frontend_events = deque() #accumulates note_on/note_off events for the frontend polling endpoint; drained on each read so no keypress is ever lost between polls

        # mido backend python-rtmidi has a bug on some (debian-based) systems
        # involving the library location of alsa plugins
        # https://github.com/SpotlightKid/python-rtmidi/issues/138
        # The bug will cause the first attempt at accessing a port to fail (due to the failed plugin lookup?)
        # but succeed on the second
        # Access once to trigger bug if exists, so open port later will succeed on attempt:
        try:
            mido.get_input_names()
        except Exception:
            logger.warning(
                "First access to mido failed.  Possibly from known issue: https://github.com/SpotlightKid/python-rtmidi/issues/138"
            )

        # checking if the input port was previously set by the user
        port = self.usersettings.get_setting_value("input_port")
        if port != "default":
            try:
                self.inport = mido.open_input(port, callback=self.msg_callback)
                logger.info("Inport loaded and set to " + port)
            except Exception:
                logger.info("Can't load input port: " + port)
        else:
            # if not, try to find the new midi port
            try:
                for port in mido.get_input_names():
                    if (
                        "Through" not in port
                        and "RPi" not in port
                        and "RtMidOut" not in port
                        and "USB-USB" not in port
                    ):
                        self.inport = mido.open_input(port, callback=self.msg_callback)
                        self.usersettings.change_setting_value("input_port", port)
                        logger.info("Inport set to " + port)
                        break
            except Exception:
                logger.info("no input port")
        # checking if the play port was previously set by the user
        port = self.usersettings.get_setting_value("play_port")
        if port != "default":
            try:
                self.playport = mido.open_output(port)
                logger.info("Playport loaded and set to " + port)
            except Exception:
                logger.info("Can't load input port: " + port)
        else:
            # if not, try to find the new midi port
            try:
                for port in mido.get_output_names():
                    if (
                        "Through" not in port
                        and "RPi" not in port
                        and "RtMidOut" not in port
                        and "USB-USB" not in port
                    ):
                        self.playport = mido.open_output(port)
                        self.usersettings.change_setting_value("play_port", port)
                        logger.info("Playport set to " + port)
                        break
            except Exception:
                logger.info("no play port")

        self.portname = "inport"

    def connectall(self):
        # Reconnect the input and playports on a connectall
        self.reconnect_ports()
        # Now connect all the remaining ports
        connectall.connectall()

    def change_port(self, port, portname):
        try:
            destroy_old = None
            if port == "inport":
                destroy_old = self.inport
                self.inport = mido.open_input(portname, callback=self.msg_callback)
                self.usersettings.change_setting_value("input_port", portname)
            elif port == "playport":
                destroy_old = self.playport
                self.playport = mido.open_output(portname)
                self.usersettings.change_setting_value("play_port", portname)
            if destroy_old is not None:
                destroy_old.close()
        except Exception:
            return

    def reconnect_ports(self):
        try:
            destroy_old = self.inport
            port = self.usersettings.get_setting_value("input_port")
            self.inport = mido.open_input(port, callback=self.msg_callback)
            if destroy_old is not None:
                time.sleep(0.002)
                destroy_old.close()
        except Exception:
            logger.info("Can't reconnect input port: " + port)
        try:
            destroy_old = self.playport
            port = self.usersettings.get_setting_value("play_port")
            self.playport = mido.open_output(port)
            if destroy_old is not None:
                time.sleep(0.002)
                destroy_old.close()
        except Exception:
            logger.info("Can't reconnect play port: " + port)

    def msg_callback(self, msg):
        if msg.type not in ("note_on", "note_off"): #reject everything that isn't a real key press or release — active sensing, clock, control change, sysex, garbage bytes
            return

        if not hasattr(msg, "note") or not hasattr(msg, "velocity"): #safety net — some malformed messages pass the type check but lack expected attributes
            return

        if msg.note < 21 or msg.note > 108: #reject notes outside the 88-key piano range (A0=21 to C8=108); real keyboards never send these, but garbage bytes can decode to anything 0-127
            return

        if msg.type == "note_on":
            if msg.velocity == 0: #note_on with velocity 0 is equivalent to note_off per MIDI spec
                self.currently_pressed_keys = [
                    x for x in self.currently_pressed_keys if msg.note != x.note
                ]
            else:
                self.currently_pressed_keys.append(msg)
        elif msg.type == "note_off":
            self.currently_pressed_keys = [
                x for x in self.currently_pressed_keys if msg.note != x.note
            ]

        self.midi_queue.append((msg, time.perf_counter()))
        self.frontend_events.append({"type": msg.type, "note": msg.note, "velocity": msg.velocity})
