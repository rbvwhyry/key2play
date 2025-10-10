import time
import threading
import subprocess
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
        self.midi_monitor_thread = None
        self.monitor_running = False

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
        # Now connect the input and secondary input ports
        connectall.connectall(self.usersettings)

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            destroy_old = None
            if port == "inport":
                destory_old = self.inport
                self.inport = mido.open_input(portname, callback=self.msg_callback)
                self.usersettings.change_setting_value("input_port", portname)
            elif port == "playport":
                destory_old = self.playport
                self.playport = mido.open_output(portname)
                self.usersettings.change_setting_value("play_port", portname)
            self.menu.render_message("Changing " + port + " to:", portname, 1500)
            if destroy_old is not None:
                destory_old.close()
            self.menu.show()
        except Exception:
            self.menu.render_message("Can't change " + port + " to:", portname, 1500)
            self.menu.show()

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
        if msg.type == "note_on":
            if msg.velocity == 0:
                self.currently_pressed_keys = [
                    x for x in self.currently_pressed_keys if msg.note != x.note
                ]
            else:
                self.currently_pressed_keys.append(msg)
        if msg.type == "note_off":
            self.currently_pressed_keys = [
                x for x in self.currently_pressed_keys if msg.note != x.note
            ]
        self.midi_queue.append((msg, time.perf_counter()))

    def start_midi_monitor(self):
        """Start monitoring for MIDI device changes and auto-connect"""
        if self.midi_monitor_thread is None or not self.midi_monitor_thread.is_alive():
            self.monitor_running = True
            self.midi_monitor_thread = threading.Thread(
                target=self._monitor_midi_devices, daemon=True
            )
            self.midi_monitor_thread.start()
            logger.info("MIDI device monitor started")

    def stop_midi_monitor(self):
        """Stop monitoring for MIDI device changes"""
        self.monitor_running = False
        if self.midi_monitor_thread and self.midi_monitor_thread.is_alive():
            self.midi_monitor_thread.join(timeout=1)
        logger.info("MIDI device monitor stopped")

    def _monitor_midi_devices(self):
        """Monitor for MIDI device changes and auto-connect configured ports - optimized for weak devices"""
        last_port_count = 0
        check_interval = 10  # Check every 10 seconds
        consecutive_checks = 0
        connection_exists = False

        while self.monitor_running:
            try:
                # Only check if we haven't checked recently or if it's been a while
                if (
                    consecutive_checks == 0 or consecutive_checks % 6 == 0
                ):  # Every minute
                    # Use a lighter approach - just check if aconnect command works
                    result = subprocess.run(
                        ["aconnect", "-l"], capture_output=True, text=True, timeout=3
                    )
                    if result.returncode == 0:
                        # Simple port count - just count non-empty lines that aren't client headers
                        lines = [
                            line
                            for line in result.stdout.splitlines()
                            if line.strip()
                            and not line.startswith("client")
                            and not line.startswith("\t")
                        ]
                        current_port_count = len(lines)

                        # Check if our desired connection already exists
                        connection_exists = self._check_desired_connection_exists(
                            result.stdout
                        )

                        # If port count changed significantly, try to connect
                        if abs(current_port_count - last_port_count) > 0:
                            logger.info(
                                f"MIDI port count changed from {last_port_count} to {current_port_count}"
                            )
                            last_port_count = current_port_count

                            # Wait a bit for ports to stabilize
                            time.sleep(3)

                            # Try to connect configured ports
                            self.connectall()
                            connection_exists = True  # Assume connection was created

                consecutive_checks += 1

                # Adaptive sleep based on connection status
                if connection_exists:
                    # If connection exists, check much less frequently
                    if consecutive_checks > 5:  # After 50 seconds of stable connection
                        check_interval = 120  # Check every 2 minutes
                    else:
                        check_interval = 30  # Check every 30 seconds
                else:
                    # If no connection, check more frequently
                    if consecutive_checks > 10:  # After 100 seconds of no changes
                        check_interval = 30  # Check every 30 seconds
                    else:
                        check_interval = 10  # Check every 10 seconds

                time.sleep(check_interval)

            except Exception as e:
                logger.warning(f"Error in MIDI device monitor: {e}")
                time.sleep(60)  # Wait a full minute on error

    def _check_desired_connection_exists(self, aconnect_output):
        """Check if the desired two-way connection between input and secondary input ports exists"""
        try:
            # Get configured ports
            input_port = self.usersettings.get_setting_value("input_port")
            secondary_input_port = self.usersettings.get_setting_value(
                "secondary_input_port"
            )

            # Skip if ports are not configured
            if input_port == "default" or secondary_input_port == "default":
                return False

            # Extract port IDs
            input_port_id = input_port.split()[
                -1
            ]  # Get the last part (client_id:port_id)
            secondary_input_port_id = secondary_input_port.split()[
                -1
            ]  # Get the last part (client_id:port_id)

            # Check if both directions of the connection exist
            lines = aconnect_output.splitlines()
            input_to_secondary = False
            secondary_to_input = False

            for line in lines:
                if (
                    f"Connecting To: {secondary_input_port_id}" in line
                    and input_port_id in line
                ):
                    input_to_secondary = True
                if (
                    f"Connecting To: {input_port_id}" in line
                    and secondary_input_port_id in line
                ):
                    secondary_to_input = True

            return input_to_secondary and secondary_to_input

        except Exception as e:
            logger.warning(f"Error checking desired connection: {e}")
            return False
