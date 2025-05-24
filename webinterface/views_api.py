import ast
import json
import os
import random
import subprocess
import sys
import mido
import psutil
from flask import jsonify, request, send_from_directory
import lib.colormaps as cmap
from lib.functions import (
    fastColorWipe,
    find_between,
    get_last_logs,
)
from lib.rpi_drivers import GPIO, Color
from webinterface import webinterface


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def pretty_print(dom):
    return "\n".join(
        [line for line in dom.toprettyxml(indent=" " * 4).split("\n") if line.strip()]
    )


def pretty_save(file_path, sequences_tree):
    with open(file_path, "w", encoding="utf8") as outfile:
        outfile.write(pretty_print(sequences_tree))


SENSECOVER = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSECOVER, GPIO.IN, GPIO.PUD_UP)

pid = psutil.Process(os.getpid())

# 224 definitely doesn't work;
# 223 seems to be the brightest for 200 LEDs (sometimes?);
# 222 is probably safest
brightest = 222


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


@webinterface.route("/api/get_songs", methods=["GET"])
def get_songs():
    songs_list = os.listdir("Songs/")
    songs_list = list(filter(lambda s: s.endswith(".mid"), songs_list))
    return jsonify(songs_list)


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
        # red = int(color[0])
        # blue = int(color[1])
        # green = int(color[2])
        red = int(color["r"])
        blue = int(color["b"])
        green = int(color["g"])
        color = Color(red, green, blue)
        strip.setPixelColor(light_num, color)
    strip.setBrightness(brightest)
    strip.show()
    return jsonify(success=True)


@webinterface.route("/api/off_many_lights", methods=["POST"])
def off_many_lights():
    indices = request.values.get("indices")
    indices = json.loads(indices)
    assert len(indices) > 0
    strip = webinterface.ledstrip.strip
    for index in indices:
        black = Color(0, 0, 0)
        strip.setPixelColor(index, black)
    strip.setBrightness(brightest)
    strip.show()
    return jsonify(success=True)


@webinterface.route("/api/set_all_lights", methods=["POST"])
def set_all_lights():
    color = request.values.get("color")
    color = json.loads(color)
    strip = webinterface.ledstrip.strip
    red = int(color["r"])
    blue = int(color["b"])
    green = int(color["g"])
    color = Color(red, green, blue)
    cntLed = webinterface.appconfig.num_leds_on_strip()
    for i in range(cntLed):
        strip.setPixelColor(i, color)
    strip.setBrightness(brightest)
    strip.show()
    return jsonify(success=True)


### ---------------------------- database: settings table ---------------------------- ###
@webinterface.route("/api/get_config/<key>", methods=["GET"])
def get_config(key):
    value = webinterface.appconfig.get_config(key)
    return jsonify(success=True, value=value)


@webinterface.route("/api/set_config/<key>", methods=["POST"])
def set_config(key):
    assert key is not None  # assert non-emptiness
    value = request.values.get("value")
    assert value is not None
    value = str(value)
    webinterface.appconfig.set_config(key, value)
    return jsonify(success=True)


@webinterface.route("/api/delete_config/<key>", methods=["DELETE"])
def delete_config(key):
    assert key is not None
    webinterface.appconfig.delete_config(key)
    return jsonify(success=True)


### ------------------------------------------------------------------------------------ ###


### ---------------------------- database: map table ---------------------------- ###
@webinterface.route("/api/get_row/<key>", methods=["GET"])
def get_row(key):
    value = webinterface.appmap.get_midi_led_row(key)
    return jsonify(success=True, value=value)


@webinterface.route("/api/set_row/<key>", methods=["POST"])
def set_row(key):
    assert key is not None  # assert non-emptiness
    led_index = int(request.values.get("led_index"))
    r = int(request.values.get("r"))
    g = int(request.values.get("g"))
    b = int(request.values.get("b"))
    time_on = int(request.values.get("time_on"))
    time_off = int(request.values.get("time_off"))
    webinterface.appmap.set_midi_led_row(key, led_index, r, g, b, time_on, time_off)
    return jsonify(success=True)


@webinterface.route("/api/delete_row/<key>", methods=["DELETE"])
def delete_row(key):
    assert key is not None
    webinterface.appmap.delete_midi_led_row(key)
    return jsonify(success=True)


@webinterface.route("/api/get_map", methods=["GET"])
def get_map():
    mappings = (
        webinterface.appmap.get_midi_led_map()
    )  # call existing method to get all mappings from the database
    result = []
    for mapping in mappings:  # convert SQLAlchemy objects to a serializable format
        result.append(
            {
                "midi_note": mapping.midi_note,
                "led_index": mapping.led_index,
                "r": mapping.r,
                "g": mapping.g,
                "b": mapping.b,
                "time_on": mapping.time_on,
                "time_off": mapping.time_off,
            }
        )
    return jsonify(success=True, mappings=result)


### ------------------------------------------------------------------------------------ ###


@webinterface.route("/api/delete_all_maps", methods=["POST"])
def delete_all_maps():
    webinterface.appmap.delete_all_maps()
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
    except Exception:
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
