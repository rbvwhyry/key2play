import random
import json
import sys
from flask import send_file, request, jsonify, send_from_directory
from werkzeug.security import safe_join
import psutil
import threading
import webcolors as wc
import mido
from xml.dom import minidom
from subprocess import call
import subprocess
import datetime
import os
from zipfile import ZipFile
import ast

from lib.functions import (
    get_last_logs,
    find_between,
    fastColorWipe,
)
import lib.colormaps as cmap
from lib.rpi_drivers import GPIO
from lib.log_setup import logger
from lib.rpi_drivers import Color
from webinterface import webinterface


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


SENSECOVER = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSECOVER, GPIO.IN, GPIO.PUD_UP)

pid = psutil.Process(os.getpid())


@webinterface.route("/static/js/listenWorker.js")
def serve_worker():
    return send_from_directory(
        "static/js", "listenWorker.js", mimetype="application/javascript"
    )


@webinterface.route("/api/currently_pressed_keys", methods=["GET"])
def currently_pressed_keys():
    result = [
        {"note": msg.note, "velocity": msg.velocity}
        for msg in webinterface.midiports.currently_pressed_keys
    ]
    return jsonify(result)


@webinterface.route("/api/get_current_song", methods=["GET"])
def get_current_song():
    song_tracks = webinterface.learning.song_tracks
    song_tracks = [msg.__dict__ for msg in song_tracks]
    return jsonify(song_tracks)


@webinterface.route("/api/load_local_midi", methods=["POST"])
def load_local_midi():
    filename = request.values.get("filename", default=None)
    if not filename:
        return jsonify(success=False)
    webinterface.learning.load_midi(filename)
    return jsonify(success=True)


@webinterface.route("/api/set_light/<light_num>")
def set_light(light_num):
    light_num = int(light_num)
    strip = webinterface.ledstrip.strip
    red = int(request.args.get("red", default=255))
    blue = int(request.args.get("blue", default=255))
    green = int(request.args.get("green", default=255))
    color = Color(red, green, blue)
    strip.setPixelColor(light_num, color)
    strip.show()
    return jsonify(success=True)


@webinterface.route("/api/set_many_lights", methods=["POST"])
def set_many_lights():
    lights = request.values.get("lights")
    lights = json.loads(lights)
    assert len(lights) > 0
    strip = webinterface.ledstrip.strip
    for light_num, color in lights:
        red = int(color[0])
        blue = int(color[1])
        green = int(color[2])
        color = Color(red, green, blue)
        strip.setPixelColor(light_num, color)
    strip.setBrightness(128)
    strip.show()
    return jsonify(success=True)


@webinterface.route("/api/set_all_lights", methods=["POST"])
def set_all_lights():
    color = request.values.get("color")
    color = json.loads(color)
    red = int(color["r"])
    blue = int(color["b"])
    green = int(color["g"])
    color = Color(red, green, blue)
    strip = webinterface.ledstrip.strip
    cntLed = webinterface.appconfig.num_leds_on_strip()
    for i in range(cntLed):
        strip.setPixelColor(i, color)

    # 224 definitely doesn't work;
    # 223 seems to be the brightest for 200 LEDs (sometimes?);
    # 222 is probably safest
    strip.setBrightness(222)
    strip.show()
    return jsonify(success=True)


@webinterface.route("/api/get_config/<key>", methods=["GET"])
def get_config(key):
    result = webinterface.appconfig.get_config(key)
    return jsonify(result)


@webinterface.route("/api/set_config/<key>", methods=["POST"])
def set_config(key):
    assert key is not None  # assert non-emptiness
    value = str(request.values.get("value"))
    webinterface.appconfig.set_config(key, value)
    return jsonify(success=True)


@webinterface.route("/api/delete_config/<key>", methods=["DELETE"])
def delete_config(key):
    assert key is not None
    webinterface.appconfig.delete_config(key)
    return jsonify(success=True)


@webinterface.route("/api/button_mot", methods=["GET"])
def button_mot():
    print("🍭Hello, mot!")
    print("button_mot stdout")
    eprint("button_mot - does this show up in journalctl?")
    strip = webinterface.ledstrip.strip
    # strip.clear()
    # numPixels = strip.numPixels()
    strip.setBrightness(111)
    # for i in range(0, numPixels):
    #     strip.setPixelColor(i, Color(255,255,255))
    strip.setPixelColor(10, Color(212, 44, 67))
    strip.show()
    return jsonify(success=True)


# @webinterface.route('/api/button_one', methods=['GET'])
# def button_one():
#     indexLight = request.args.get("indexLight", type=int)
#     color_str = request.args.get("color")  # Expecting "255,255,255"

#     if indexLight is None or color_str is None:
#         return jsonify(success=False, error="Missing parameters"), 400

#     # Convert color string "255,255,255" to (255, 255, 255)
#     r, g, b = map(int, color_str.split(","))

#     # Apply color to the specified LED
#     strip.setPixelColor(indexLight, color_str)
#     strip.show()

#     return jsonify(success=True)

# @webinterface.route('/api/button_two', methods=['GET'])
# def button_two():
#     strip = webinterface.ledstrip.strip
#     strip.clear()
#     numPixels = strip.numPixels()
#     strip.setBrightness(25)
#     for i in range(0, numPixels):
#         strip.setPixelColor(i, Color(0,255,0))
#     strip.show()
#     return jsonify(success=True)


@webinterface.route("/api/button_two", methods=["GET"])
def button_two():
    print("🍫Hello, two!")
    print("button_two stdout")
    eprint("button_two - does this show up?")
    strip = webinterface.ledstrip.strip
    strip.setBrightness(111)
    strip.setPixelColor(
        13,
        Color(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
    )
    strip.show()
    return jsonify(success=True)


def get_random_color():
    return Color(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


@webinterface.route("/api/get_homepage_data")
def get_homepage_data():
    global pid

    try:
        temp = find_between(
            str(psutil.sensors_temperatures()["cpu_thermal"]), "current=", ","
        )
    except:
        temp = 0

    temp = round(float(temp), 1)

    upload = psutil.net_io_counters().bytes_sent
    download = psutil.net_io_counters().bytes_recv

    card_space = psutil.disk_usage("/")

    cover_opened = GPIO.input(SENSECOVER)

    homepage_data = {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count(),
        "cpu_pid": pid.cpu_percent(),
        "cpu_freq": psutil.cpu_freq().current,
        "memory_usage_percent": psutil.virtual_memory()[2],
        "memory_usage_total": psutil.virtual_memory()[0],
        "memory_usage_used": psutil.virtual_memory()[3],
        "memory_pid": pid.memory_full_info().rss,
        "cpu_temp": temp,
        "upload": upload,
        "download": download,
        "card_space_used": card_space.used,
        "card_space_total": card_space.total,
        "card_space_percent": card_space.percent,
        "cover_state": "Opened" if cover_opened else "Closed",
        "screen_on": webinterface.menu.screen_on,
        "reinitialize_network_on_boot": int(
            webinterface.usersettings.get_setting_value("reinitialize_network_on_boot")
        ),
    }
    return jsonify(homepage_data)


@webinterface.route("/api/get_learning_status", methods=["GET"])
def get_learning_status():
    response = {
        "loading": webinterface.learning.loading,
        "practice": webinterface.usersettings.get_setting_value("practice"),
        "hands": webinterface.usersettings.get_setting_value("hands"),
        "mute_hand": webinterface.usersettings.get_setting_value("mute_hand"),
        "start_point": webinterface.usersettings.get_setting_value("start_point"),
        "end_point": webinterface.usersettings.get_setting_value("end_point"),
        "set_tempo": webinterface.usersettings.get_setting_value("set_tempo"),
        "hand_colorR": webinterface.usersettings.get_setting_value("hand_colorR"),
        "hand_colorL": webinterface.usersettings.get_setting_value("hand_colorL"),
        "show_wrong_notes": webinterface.usersettings.get_setting_value(
            "show_wrong_notes"
        ),
        "show_future_notes": webinterface.usersettings.get_setting_value(
            "show_future_notes"
        ),
        "hand_colorList": ast.literal_eval(
            webinterface.usersettings.get_setting_value("hand_colorList")
        ),
        "is_loop_active": ast.literal_eval(
            webinterface.usersettings.get_setting_value("is_loop_active")
        ),
        "number_of_mistakes": ast.literal_eval(
            webinterface.usersettings.get_setting_value("number_of_mistakes")
        ),
    }

    return jsonify(response)


@webinterface.route("/api/get_songs", methods=["GET"])
def get_songs():
    songs_list = os.listdir("Songs/")
    songs_list = list(filter(lambda s: s.endswith(".mid"), songs_list))

    return jsonify(songs_list)


@webinterface.route("/api/get_ports", methods=["GET"])
def get_ports():
    ports = mido.get_input_names()
    ports = list(dict.fromkeys(ports))
    response = {
        "ports_list": ports,
        "input_port": webinterface.usersettings.get_setting_value("input_port"),
        "secondary_input_port": webinterface.usersettings.get_setting_value(
            "secondary_input_port"
        ),
        "play_port": webinterface.usersettings.get_setting_value("play_port"),
        "connected_ports": str(subprocess.check_output(["aconnect", "-i", "-l"])),
        "midi_logging": webinterface.usersettings.get_setting_value("midi_logging"),
    }

    return jsonify(response)


@webinterface.route("/api/switch_ports", methods=["GET"])
def switch_ports():
    active_input = webinterface.usersettings.get_setting_value("input_port")
    secondary_input = webinterface.usersettings.get_setting_value(
        "secondary_input_port"
    )
    webinterface.midiports.change_port("inport", secondary_input)
    webinterface.usersettings.change_setting_value("secondary_input_port", active_input)
    webinterface.usersettings.change_setting_value("input_port", secondary_input)

    fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    return jsonify(success=True)


@webinterface.route("/api/get_wifi_list", methods=["GET"])
def get_wifi_list():
    wifi_list = webinterface.platform.get_wifi_networks()
    success, wifi_ssid, address = webinterface.platform.get_current_connections()

    response = {
        "wifi_list": wifi_list,
        "connected_wifi": wifi_ssid,
        "connected_wifi_address": address,
    }
    return jsonify(response)


@webinterface.route("/api/get_logs", methods=["GET"])
def get_logs():
    last_logs = request.args.get("last_logs")
    return get_last_logs(last_logs)


@webinterface.route("/api/get_colormap_gradients", methods=["GET"])
def get_colormap_gradients():
    return jsonify(cmap.colormaps_preview)


def pretty_print(dom):
    return "\n".join(
        [line for line in dom.toprettyxml(indent=" " * 4).split("\n") if line.strip()]
    )


def pretty_save(file_path, sequences_tree):
    with open(file_path, "w", encoding="utf8") as outfile:
        outfile.write(pretty_print(sequences_tree))
