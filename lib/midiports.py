import time
import asyncio
import threading
from collections import deque

import mido

from lib import connectall
from lib.log_setup import logger


class MidiPorts:
    def __init__(self, config, usersettings):
        self.config = config
        self.usersettings = usersettings
        self.midifile_queue = deque() #midi queue will contain a tuple (midi_msg, timestamp)
        self.midi_queue = deque()
        self.last_activity = 0
        self.inport = None
        self.playport = None
        self.midipending = None
        self.currently_pressed_keys = []
        self._keys_lock = threading.Lock()
        self.frontend_events = deque() #kept for HTTP fallback endpoint compatibility; drained on each read
        self.ws_queue = None #asyncio.Queue for WebSocket push; set by the WebSocket server after the event loop starts
        self.ws_loop = None #reference to the asyncio event loop running the WebSocket server; needed for thread-safe queue puts

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

        port = self.usersettings.get_setting_value("input_port")
        if port != "default":
            try:
                self.inport = mido.open_input(port, callback=self.msg_callback)
                logger.info("Inport loaded and set to " + port)
            except Exception:
                logger.info("Can't load input port: " + port)
        else:
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

        port = self.usersettings.get_setting_value("play_port")
        if port != "default":
            try:
                self.playport = mido.open_output(port)
                logger.info("Playport loaded and set to " + port)
            except Exception:
                logger.info("Can't load input port: " + port)
        else:
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
        self.reconnect_ports()
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
        if msg.type not in ("note_on", "note_off"): #reject everything that isn't a real key press or release
            return

        if not hasattr(msg, "note") or not hasattr(msg, "velocity"): #safety net for malformed messages
            return

        if msg.note < 21 or msg.note > 108: #reject notes outside 88-key piano range (A0=21 to C8=108)
            return

        with self._keys_lock:
            if msg.type == "note_on":
                if msg.velocity == 0:
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

        Event = {"type": msg.type, "note": msg.note, "velocity": msg.velocity}

        self.frontend_events.append(Event) #HTTP fallback — kept for /api/drain_midi_events compatibility

        if self.ws_queue is not None and self.ws_loop is not None: #push to WebSocket queue if available
            self.ws_loop.call_soon_threadsafe(self.ws_queue.put_nowait, Event) #thread-safe push from mido callback thread into asyncio event loop
