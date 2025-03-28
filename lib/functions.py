import math
import os
import socket
import subprocess
import threading
import time

import mido

from lib.log_setup import logger
from lib.rpi_drivers import GPIO, Color

SENSECOVER = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSECOVER, GPIO.IN, GPIO.PUD_UP)


def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
    except OSError:
        return "0.0.0.0"
    local_ip = s.getsockname()[0]
    s.close()
    return local_ip


def get_last_logs(n=100):
    file_path = "visualizer.log"
    # If the file does not exist, create it with write permissions
    if not os.path.exists(file_path):
        open(file_path, "w").close()
        os.chmod(file_path, 0o777)

    try:
        # Use the 'tail' command to get the last N lines of the log file
        tail_command = ["tail", f"-n{n}", file_path]
        result = subprocess.run(
            tail_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        # Split the output into lines and return as a list
        lines = result.stdout.splitlines()
        string = ""
        for line in lines:
            string += "\r\n" + line
        return string
    except subprocess.CalledProcessError as e:
        # Handle any errors that occur during the 'tail' command execution
        return [f"Error: {e.stderr}"]


def find_between(s, start, end):
    try:
        return (s.split(start))[1].split(end)[0]
    except IndexError:
        return False


def clamp(val, val_min, val_max):
    return max(val_min, min(val, val_max))


def shift(lst, num_shifts):
    return lst[num_shifts:] + lst[:num_shifts]


def play_midi(song_path, midiports, saving, menu, ledsettings, ledstrip):
    midiports.midifile_queue.append((mido.Message("note_on"), time.perf_counter()))

    if song_path in saving.is_playing_midi.keys():
        menu.render_message(song_path, "Already playing", 2000)
        return

    saving.is_playing_midi.clear()

    saving.is_playing_midi[song_path] = True
    menu.render_message("Playing: ", song_path, 2000)
    saving.t = threading.currentThread()

    try:
        mid = mido.MidiFile("Songs/" + song_path)
        fastColorWipe(ledstrip.strip, True, ledsettings)
        # length = mid.length
        t0 = False
        total_delay = 0
        delay = 0
        for message in mid:
            if song_path in saving.is_playing_midi.keys():
                if not t0:
                    t0 = time.perf_counter()

                total_delay += message.time
                current_time = (time.perf_counter() - t0) + message.time
                drift = total_delay - current_time

                if drift < 0:
                    delay = message.time + drift
                else:
                    delay = message.time
                if delay < 0:
                    delay = 0

                msg_timestamp = time.perf_counter() + delay
                if delay > 0:
                    time.sleep(delay)
                if not message.is_meta:
                    midiports.playport.send(message)
                    midiports.midifile_queue.append(
                        (message.copy(time=0), msg_timestamp)
                    )

            else:
                midiports.midifile_queue.clear()
                strip = ledstrip.strip
                fastColorWipe(strip, True, ledsettings)
                break
        logger.info(
            "play time: {:.2f} s (expected {:.2f})".format(
                time.perf_counter() - t0, total_delay
            )
        )
        # print('play time: {:.2f} s (expected {:.2f})'.format(time.perf_counter() - t0, length))
        # saving.is_playing_midi = False
    except FileNotFoundError:
        menu.render_message(song_path, "File not found", 2000)
    except Exception as e:
        menu.render_message(song_path, "Error while playing song " + str(e), 2000)
        logger.warning(e)
    saving.is_playing_midi.clear()


def manage_idle_animation(ledstrip, ledsettings, menu, midiports):
    animation_delay_minutes = int(menu.led_animation_delay)
    if animation_delay_minutes == 0:
        return

    time_since_last_activity_minutes = (time.time() - menu.last_activity) / 60
    time_since_last_ports_activity_minutes = (
        time.time() - midiports.last_activity
    ) / 60

    if time_since_last_ports_activity_minutes < animation_delay_minutes:
        menu.is_idle_animation_running = False

    # Check conditions
    if (
        0 < animation_delay_minutes < time_since_last_activity_minutes
        and not menu.is_idle_animation_running
        and 0 < animation_delay_minutes < time_since_last_ports_activity_minutes
    ):
        menu.is_idle_animation_running = True

        time.sleep(1)


# Get note position on the strip
def get_note_position(note, ledstrip, ledsettings):
    note_offsets = ledsettings.note_offsets
    note_offset = 0
    for i in range(0, len(note_offsets)):
        if note > note_offsets[i][0]:
            note_offset = note_offsets[i][1]
            # break

    note_offset -= ledstrip.shift

    density = ledstrip.leds_per_meter / 72

    note_pos_raw = int(density * (note - 20) - note_offset)
    if ledstrip.reverse:
        return max(0, ledstrip.num_leds_on_strip() - note_pos_raw)
    else:
        return max(0, note_pos_raw)


# scale: 1 means in C, scale: 2 means in C#, scale: 3 means in D, etc...
# and scale: 1 means in C m, scale: 2 means in C# m, scale: 3 means in D m, etc...
def get_scale_color(scale, note_position, key_in_scale, key_not_in_scale):
    scale = int(scale)
    if scale < 12:
        notes_in_scale = [0, 2, 4, 5, 7, 9, 11]
    else:
        notes_in_scale = [0, 2, 3, 5, 7, 8, 10]
    note_position = (note_position - scale) % 12

    if note_position in notes_in_scale:
        return list(key_in_scale.values())
    else:
        return list(key_not_in_scale.values())


def get_rainbow_colors(pos, color):
    pos = int(pos)
    if pos < 85:
        if color == "green":
            return pos * 3
        elif color == "red":
            return 255 - pos * 3
        elif color == "blue":
            return 0
    elif pos < 170:
        pos -= 85
        if color == "green":
            return 255 - pos * 3
        elif color == "red":
            return 0
        elif color == "blue":
            return pos * 3
    else:
        pos -= 170
        if color == "green":
            return 0
        elif color == "red":
            return pos * 3
        elif color == "blue":
            return 255 - pos * 3


def powercurve(x, p):
    if p == 0:
        return x
    return (math.exp(-p * x) - 1) / (math.exp(-p) - 1)


def gammacurve(x, p):
    if p != 0:
        return x ** (1 / p)
    else:
        return 1


def check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
    if ledsettings.adjacent_mode == "Off":
        if i < len(ledstrip.keylist_status) and i < len(ledstrip.keylist):
            if ledstrip.keylist_status[i] == 0 and ledstrip.keylist[i] == 0:
                return True
        return False
    else:
        if 1 < i < (ledstrip.num_leds_on_strip() - 1):
            if (
                ledstrip.keylist[i + 1]
                == ledstrip.keylist[i - 1]
                == ledstrip.keylist[i]
                == ledstrip.keylist_status[i + 1]
                == ledstrip.keylist_status[i - 1]
                == ledstrip.keylist_status[i]
            ):
                return True
        else:
            return True
    return False


# LED animations
def fastColorWipe(strip, update, ledsettings):
    if ledsettings.backlight_stopped:
        color = Color(0, 0, 0)
    else:
        brightness = ledsettings.backlight_brightness_percent / 100
        red = int(ledsettings.get_backlight_color("Red") * brightness)
        green = int(ledsettings.get_backlight_color("Green") * brightness)
        blue = int(ledsettings.get_backlight_color("Blue") * brightness)
        color = Color(red, green, blue)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    if update:
        strip.show()


def calculate_brightness(ledsettings):
    brightness = ledsettings.led_animation_brightness_percent
    brightness /= 100
    return brightness


def stop_animations(menu):
    temp_is_idle_animation_running = menu.is_idle_animation_running
    temp_is_animation_running = menu.is_animation_running
    menu.is_idle_animation_running = False
    menu.is_animation_running = False
    time.sleep(0.3)
    menu.is_idle_animation_running = temp_is_idle_animation_running
    menu.is_animation_running = temp_is_animation_running


def wheel(pos, ledsettings):
    """Generate rainbow colors across 0-255 positions."""

    brightness = calculate_brightness(ledsettings)

    if pos < 85:
        return Color(int((pos * 3) * brightness), int((255 - pos * 3) * brightness), 0)
    elif pos < 170:
        pos -= 85
        return Color(int((255 - pos * 3) * brightness), 0, int((pos * 3) * brightness))
    else:
        pos -= 170
        return Color(0, int((pos * 3) * brightness), int((255 - pos * 3) * brightness))


def startup_animation(
    ledstrip, ledsettings, duration_ms=15000, max_leds=180
):  # duration doesn't seem to change real timing
    strip = ledstrip.strip
    total_pixels = strip.numPixels()

    num_red_leds = max_leds // 3
    num_blue_leds = max_leds // 3
    num_green_leds = max_leds - num_red_leds - num_blue_leds

    start_red_led = (total_pixels - max_leds) // 2
    start_blue_led = start_red_led + num_red_leds
    start_green_led = start_blue_led + num_blue_leds

    brightness = 0.0

    num_steps = 200

    step_delay = duration_ms / num_steps / 1000.0

    brightness_increment = 1.0 / num_steps

    for step in range(num_steps):
        if brightness < 0:
            break
        red = int(255 * brightness)
        blue = int(255 * brightness)
        green = int(255 * brightness)

        for i in range(start_red_led, start_blue_led):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(red, 0, 0))
        for i in range(start_blue_led, start_green_led):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, 0, blue))
        for i in range(start_green_led, start_green_led + num_green_leds):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, green, 0))

        strip.show()
        brightness += brightness_increment

        if brightness > 0.5:
            brightness_increment *= -1

        time.sleep(int(step_delay))

    for i in range(total_pixels):
        strip.setPixelColor(i, 0)

    strip.show()
