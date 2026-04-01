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
        mid = mido.MidiFile(song_path)  #song_path is now the full resolved path from the caller
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


def _hsv_to_rgb_tuple(hue, brightness=1.0):
    """Convert hue (0-360) and brightness (0.0-1.0) to (r, g, b) tuple."""
    h = hue / 60.0
    i = int(h) % 6
    f = h - int(h)
    v = brightness
    p, q, t_val = 0.0, v * (1 - f), v * f
    if i == 0:   r, g, b = v, t_val, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t_val
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t_val, p, v
    else:        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def _hex_to_rgb_tuple(hex_str, brightness=1.0):
    """Convert hex color string (with or without #) to (r, g, b) tuple with brightness applied."""
    h = hex_str.lstrip('#')
    if len(h) != 6:
        return int(255 * brightness), 0, 0
    r = int(int(h[0:2], 16) * brightness)
    g = int(int(h[2:4], 16) * brightness)
    b = int(int(h[4:6], 16) * brightness)
    return r, g, b


def _interpolate_rgb(rgb_a, rgb_b, t):
    """Linearly interpolate between two (r, g, b) tuples; t=0 returns a, t=1 returns b."""
    return (
        int(rgb_a[0] + (rgb_b[0] - rgb_a[0]) * t),
        int(rgb_a[1] + (rgb_b[1] - rgb_a[1]) * t),
        int(rgb_a[2] + (rgb_b[2] - rgb_a[2]) * t),
    )


def _startup_sweep(strip, num_leds, brightness, duration, timing):
    """Rainbow sweep left to right in batches, hold, then smooth fade out."""
    batch_size = 4
    delay = max(0.004, timing * 0.004)  # timing 1-5 → 4-20ms per batch

    rgb_colors = []
    for i in range(num_leds):
        hue = (i / max(1, num_leds - 1)) * 270.0
        rgb_colors.append(_hsv_to_rgb_tuple(hue, brightness))

    for batch_start in range(0, num_leds, batch_size):
        for i in range(batch_start, min(batch_start + batch_size, num_leds)):
            r, g, b = rgb_colors[i]
            strip.setPixelColor(i, Color(r, g, b))
        strip.show()
        time.sleep(delay)

    time.sleep(duration)

    fade_steps = 12
    for step in range(1, fade_steps + 1):
        factor = 1.0 - step / fade_steps
        for i in range(num_leds):
            r, g, b = rgb_colors[i]
            strip.setPixelColor(i, Color(int(r * factor), int(g * factor), int(b * factor)))
        strip.show()
        time.sleep(0.05)


def _startup_comet(strip, num_leds, brightness, duration, timing, color_a):
    """Comet with tail travels right then left in user color, then clears."""
    tail_length = 14
    speed = max(0.003, timing * 0.005)  # timing 1-5 → 5-25ms per step
    color_rgb = _hex_to_rgb_tuple(color_a, brightness)

    def make_pass(direction):  # direction: +1 = left→right, -1 = right→left
        start = 0 if direction == 1 else num_leds - 1
        total_steps = num_leds + tail_length
        for step in range(total_steps):
            head = start + direction * step
            for tail in range(tail_length):
                pos = head - direction * tail
                if 0 <= pos < num_leds:
                    tail_factor = (1 - tail / tail_length) ** 2
                    strip.setPixelColor(pos, Color(
                        int(color_rgb[0] * tail_factor),
                        int(color_rgb[1] * tail_factor),
                        int(color_rgb[2] * tail_factor)
                    ))
            erase = head - direction * tail_length
            if 0 <= erase < num_leds:
                strip.setPixelColor(erase, Color(0, 0, 0))
            strip.show()
            time.sleep(speed)

    make_pass(1)   # left → right
    time.sleep(0.08)
    make_pass(-1)  # right → left
    time.sleep(0.4)


def _startup_sparkle(strip, num_leds, brightness, duration, timing, color_a):
    """Random LEDs light up in user color, hold, then turn off in reverse."""
    import random
    num_sparks = min(int(num_leds * 0.6), 120)
    delay = max(0.008, timing * 0.012)  # timing 1-5 → 12-60ms per spark
    color_rgb = _hex_to_rgb_tuple(color_a, brightness)

    indices = list(range(num_leds))
    random.shuffle(indices)
    chosen = indices[:num_sparks]

    for led in chosen:
        strip.setPixelColor(led, Color(color_rgb[0], color_rgb[1], color_rgb[2]))
        strip.show()
        time.sleep(delay)

    time.sleep(duration)

    for led in reversed(chosen):
        strip.setPixelColor(led, Color(0, 0, 0))
        strip.show()
        time.sleep(0.018)


def _startup_ripple(strip, num_leds, brightness, duration, timing, color_a, color_b):
    """Color wave expands from center outward using gradient between color A and B, holds, then collapses."""
    center = num_leds // 2
    max_radius = center
    speed = max(0.004, timing * 0.005)  # timing 1-5 → 5-25ms per step
    rgb_a = _hex_to_rgb_tuple(color_a, brightness)
    rgb_b = _hex_to_rgb_tuple(color_b, brightness)

    for radius in range(max_radius + 1):
        t = radius / max(1, max_radius)
        rgb = _interpolate_rgb(rgb_a, rgb_b, t)
        color = Color(rgb[0], rgb[1], rgb[2])
        left, right = center - radius, center + radius
        if left >= 0: strip.setPixelColor(left, color)
        if right < num_leds and right != left: strip.setPixelColor(right, color)
        strip.show()
        time.sleep(speed)

    time.sleep(duration)

    for radius in range(max_radius, -1, -1):
        left, right = center - radius, center + radius
        if left >= 0: strip.setPixelColor(left, Color(0, 0, 0))
        if right < num_leds and right != left: strip.setPixelColor(right, Color(0, 0, 0))
        strip.show()
        time.sleep(speed)


def startup_animation(ledstrip, ledsettings, appconfig=None):
    """Reads saved startup config from DB and plays the appropriate animation once at Pi boot."""
    strip = ledstrip.strip
    num_leds = strip.numPixels()

    sequence  = 'sweep'
    brightness = 0.8
    duration   = 6.0
    timing     = 3.0
    color_a    = '#ff0000'
    color_b    = '#4b0082'
    randomize  = False

    if appconfig:
        try:
            val = appconfig.get_config('startupSequence');  sequence  = val if val else sequence
            val = appconfig.get_config('startupBrightness'); brightness = float(val) / 100.0 if val else brightness
            val = appconfig.get_config('startupDuration');   duration   = float(val) if val else duration
            val = appconfig.get_config('startupTiming');     timing     = float(val) if val else timing
            val = appconfig.get_config('startupColorA');     color_a    = val if val else color_a
            val = appconfig.get_config('startupColorB');     color_b    = val if val else color_b
            val = appconfig.get_config('startupRandomize');  randomize  = (val == 'true') if val else randomize
        except Exception as exc:
            logger.warning(f"startup_animation: config read failed: {exc}")

    if randomize:
        import random
        sequence = random.choice(['sweep', 'comet', 'sparkle', 'ripple'])

    logger.info(f"startup_animation: sequence={sequence} brightness={brightness} duration={duration} timing={timing}")

    if sequence == 'none':
        return
    elif sequence == 'comet':
        _startup_comet(strip, num_leds, brightness, duration, timing, color_a)
    elif sequence == 'sparkle':
        _startup_sparkle(strip, num_leds, brightness, duration, timing, color_a)
    elif sequence == 'ripple':
        _startup_ripple(strip, num_leds, brightness, duration, timing, color_a, color_b)
    else:
        _startup_sweep(strip, num_leds, brightness, duration, timing)

    for i in range(num_leds):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
