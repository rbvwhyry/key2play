from webinterface import webinterface, app_state
from flask import render_template, send_file, request, jsonify
from werkzeug.security import safe_join
from lib.functions import (
    get_last_logs,
    find_between,
    fastColorWipe,
    play_midi,
    clamp,
)
import lib.colormaps as cmap
import psutil
import threading
import webcolors as wc
import mido
from xml.dom import minidom
from subprocess import call
import subprocess
import datetime
import os
import math
from zipfile import ZipFile
import json
import ast
import re
from lib.rpi_drivers import GPIO
from lib.log_setup import logger


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


@webinterface.route("/api/update_to_release", methods=["POST"])
def update_to_release():
    release = request.values.get("release", default=None)
    if not release:
        return jsonify(success=False)
    print(f"updating to release {release}")
    import requests

    req = requests.get(f"https://rbvwhyry.github.io/key2play/{release}")
    with open(release, "wb") as fd:
        for chunk in req.iter_content(chunk_size=128):
            fd.write(chunk)
    print(f"downloaded release to {release}")
    releasedir = release.removesuffix(".zip")
    subprocess.run(["unzip", release, "-d", releasedir])
    subprocess.run(["cp", "-R", f"{releasedir}/", "."])
    return jsonify(success=True)


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


@webinterface.route("/api/connect_to_wifi", methods=["POST"])
def connect_to_wifi():
    ssid = request.values.get("ssid")
    psk = request.values.get("psk")
    webinterface.platform.connect_to_wifi(
        ssid, psk, webinterface.hotspot, webinterface.usersettings
    )
    return jsonify(success=True)


@webinterface.route("/api/disconnect_from_wifi", methods=["POST"])
def disconnect_from_wifi():
    webinterface.platform.disconnect_from_wifi(
        webinterface.hotspot, webinterface.usersettings
    )
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
        "led_fps": round(app_state.ledstrip.current_fps, 2),
        "screen_on": app_state.menu.screen_on,
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


@webinterface.route("/api/get_song_list_setting", methods=["GET"])
def get_song_list_setting():
    response = {
        "songs_per_page": app_state.usersettings.get_setting_value("songs_per_page"),
        "sort_by": app_state.usersettings.get_setting_value("sort_by"),
    }
    return jsonify(response)


@webinterface.route("/api/get_ports", methods=["GET"])
def get_ports():
    ports = mido.get_input_names()
    ports = list(dict.fromkeys(ports))
    response = {
        "ports_list": ports,
        "input_port": app_state.usersettings.get_setting_value("input_port"),
        "secondary_input_port": app_state.usersettings.get_setting_value(
            "secondary_input_port"
        ),
        "play_port": app_state.usersettings.get_setting_value("play_port"),
        "connected_ports": str(subprocess.check_output(["aconnect", "-i", "-l"])),
        "midi_logging": app_state.usersettings.get_setting_value("midi_logging"),
    }

    return jsonify(response)


@webinterface.route("/api/switch_ports", methods=["GET"])
def switch_ports():
    active_input = app_state.usersettings.get_setting_value("input_port")
    secondary_input = app_state.usersettings.get_setting_value("secondary_input_port")
    app_state.midiports.change_port("inport", secondary_input)
    app_state.usersettings.change_setting_value("secondary_input_port", active_input)
    app_state.usersettings.change_setting_value("input_port", secondary_input)

    fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

    return jsonify(success=True)


@webinterface.route("/api/get_sequences", methods=["GET"])
def get_sequences():
    response = {}
    sequences_list = []
    sequences_tree = minidom.parse("config/sequences.xml")
    i = 0
    while True:
        try:
            i += 1
            sequences_list.append(
                sequences_tree.getElementsByTagName("sequence_" + str(i))[0]
                .getElementsByTagName("sequence_name")[0]
                .firstChild.nodeValue
            )
        except:
            break
    response["sequences_list"] = sequences_list
    response["sequence_number"] = app_state.ledsettings.sequence_number

    return jsonify(response)


@webinterface.route("/api/get_steps_list", methods=["GET"])
def get_steps_list():
    response = {}
    sequence = request.args.get("sequence")
    sequences_tree = minidom.parse("config/sequences.xml")
    steps_list = []
    i = 0

    for step in sequences_tree.getElementsByTagName("sequence_" + str(sequence))[
        0
    ].childNodes:
        if step.nodeType == 1:
            if step.nodeName == "settings":
                response["control_number"] = step.getElementsByTagName(
                    "control_number"
                )[0].firstChild.nodeValue
                response["next_step"] = step.getElementsByTagName("next_step")[
                    0
                ].firstChild.nodeValue
            else:
                steps_list.append(step.nodeName)

    response["steps_list"] = steps_list
    return jsonify(response)


@webinterface.route("/api/set_step_properties", methods=["GET"])
def set_step_properties():
    sequence = request.args.get("sequence")
    step = request.args.get("step")
    app_state.ledsettings.set_sequence(sequence, step, True)
    app_state.ledsettings.incoming_setting_change = True
    return jsonify(success=True)


@webinterface.route("/api/get_wifi_list", methods=["GET"])
def get_wifi_list():
    wifi_list = app_state.platform.get_wifi_networks()
    success, wifi_ssid, address = app_state.platform.get_current_connections()

    response = {
        "wifi_list": wifi_list,
        "connected_wifi": wifi_ssid,
        "connected_wifi_address": address,
    }
    return jsonify(response)


@webinterface.route("/api/get_local_address", methods=["GET"])
def get_local_address():
    result = app_state.platform.get_local_address()
    if result["success"]:
        return jsonify(
            {
                "success": True,
                "local_address": result["local_address"],
                "ip_address": result["ip_address"],
            }
        )
    else:
        return jsonify({"success": False, "error": result["error"]}), 500


@webinterface.route("/api/change_local_address", methods=["POST"])
def change_local_address():
    new_name = request.json.get("new_name")
    if not new_name:
        return jsonify({"success": False, "error": "No name provided"}), 400

    try:
        success = app_state.platform.change_local_address(new_name)
        if success:
            return jsonify({"success": True, "new_address": f"{new_name}.local"})
        else:
            return jsonify({"success": False, "error": "Failed to change address"}), 500
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@webinterface.route("/api/get_logs", methods=["GET"])
def get_logs():
    last_logs = request.args.get("last_logs")
    return get_last_logs(last_logs)


@webinterface.route("/api/get_colormap_gradients", methods=["GET"])
def get_colormap_gradients():
    return jsonify(cmap.colormaps_preview)


# ========== Port Manager Helper Functions ==========


def parse_aconnect_ports(output, port_type="input"):
    """
    Parse aconnect output to extract port information.
    Returns a list of dicts with port info: {id, client_id, port_id, name, full_name}
    """
    ports = []
    current_client = None
    current_client_name = ""

    for line in output.split("\n"):
        line = line.strip()

        # Match client lines: "client 20: 'Midi Through' [type=kernel]"
        client_match = re.match(r"client (\d+):\s+'([^']+)'", line)
        if client_match:
            current_client = client_match.group(1)
            current_client_name = client_match.group(2)

            # Skip special clients
            if current_client == "0" or "Through" in current_client_name:
                current_client = None
            continue

        # Match port lines: "    0 'Midi Through Port-0'"
        if current_client and line and not line.startswith("client"):
            port_match = re.match(r"(\d+)\s+'([^']+)'", line)
            if port_match:
                port_id = port_match.group(1)
                port_name = port_match.group(2)
                full_id = f"{current_client}:{port_id}"

                ports.append(
                    {
                        "id": full_id,
                        "client_id": current_client,
                        "port_id": port_id,
                        "name": port_name,
                        "client_name": current_client_name,
                        "full_name": f"{current_client_name} - {port_name}",
                    }
                )

    return ports


def parse_aconnect_connections(output):
    """
    Parse aconnect -l output to extract current connections.
    Returns a list of dicts: {source, destination, source_name, dest_name}
    """
    connections = []
    current_client = None
    current_port = None
    current_client_name = ""
    current_port_name = ""

    for line in output.split("\n"):
        line_stripped = line.strip()

        # Match client lines
        client_match = re.match(r"client (\d+):\s+'([^']+)'", line_stripped)
        if client_match:
            current_client = client_match.group(1)
            current_client_name = client_match.group(2)
            current_port = None
            continue

        # Match port lines with connections: "    0 'port name'"
        if current_client and line.startswith("    ") and not line.startswith("\t"):
            port_match = re.match(r"\s+(\d+)\s+'([^']+)'", line)
            if port_match:
                current_port = port_match.group(1)
                current_port_name = port_match.group(2)
                continue

        # Match connection lines: "\tConnecting To: 130:0" or "\tConnecting To: 130:0, 131:0, 132:0"
        if current_client and current_port and "\t" in line:
            # Only process "Connecting To:" to avoid duplicates
            if "Connecting To:" in line:
                # Find all port connections in the line (handles multiple connections)
                conn_matches = re.findall(r"(\d+):(\d+)", line_stripped)
                source_id = f"{current_client}:{current_port}"

                for conn_match in conn_matches:
                    dest_id = f"{conn_match[0]}:{conn_match[1]}"
                    connections.append(
                        {
                            "source": source_id,
                            "destination": dest_id,
                            "source_name": f"{current_client_name} - {current_port_name}",
                        }
                    )

    return connections


def get_all_available_ports():
    """
    Get all available MIDI input and output ports.
    Returns dict with 'inputs' and 'outputs' lists.
    """
    try:
        input_output = subprocess.check_output(["aconnect", "-l"], text=True)
        input_ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
        output_ports = subprocess.check_output(["aconnect", "-o", "-l"], text=True)

        return {
            "inputs": parse_aconnect_ports(input_ports, "input"),
            "outputs": parse_aconnect_ports(output_ports, "output"),
            "all": parse_aconnect_ports(input_output, "all"),
        }
    except subprocess.CalledProcessError as e:
        return {"inputs": [], "outputs": [], "all": []}


def get_all_current_connections():
    """
    Get all current MIDI port connections.
    Returns list of connection dicts.
    """
    try:
        output = subprocess.check_output(["aconnect", "-l"], text=True)
        return parse_aconnect_connections(output)
    except subprocess.CalledProcessError:
        return []


def create_midi_port_connection(source, destination):
    """
    Create a connection between two MIDI ports.
    Args:
        source: Source port in format "client:port" (e.g., "20:0")
        destination: Destination port in format "client:port"
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.call(["aconnect", source, destination])
        return result == 0
    except Exception as e:
        print(f"Error creating connection: {e}")
        return False


def delete_midi_port_connection(source, destination):
    """
    Delete a connection between two MIDI ports.
    Args:
        source: Source port in format "client:port"
        destination: Destination port in format "client:port"
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.call(["aconnect", "-d", source, destination])
        return result == 0
    except Exception as e:
        print(f"Error deleting connection: {e}")
        return False


# ========== Port Connection API Endpoints ==========


@webinterface.route("/api/get_available_ports", methods=["GET"])
def get_available_ports():
    """Get all available MIDI ports (inputs and outputs)"""
    ports = get_all_available_ports()
    return jsonify(ports)


@webinterface.route("/api/get_port_connections", methods=["GET"])
def get_port_connections():
    """Get all current MIDI port connections"""
    connections = get_all_current_connections()
    return jsonify({"connections": connections})


@webinterface.route("/api/create_port_connection", methods=["POST"])
def create_port_connection():
    """Create a connection between two MIDI ports"""
    data = request.get_json()
    source = data.get("source")
    destination = data.get("destination")

    if not source or not destination:
        return jsonify(
            {"success": False, "error": "Missing source or destination"}
        ), 400

    # Prevent self-connection
    if source == destination:
        return jsonify(
            {"success": False, "error": "Cannot connect a port to itself"}
        ), 400

    success = create_midi_port_connection(source, destination)
    return jsonify({"success": success})


@webinterface.route("/api/delete_port_connection", methods=["POST"])
def delete_port_connection():
    """Delete a connection between two MIDI ports"""
    data = request.get_json()
    source = data.get("source")
    destination = data.get("destination")

    if not source or not destination:
        return jsonify(
            {"success": False, "error": "Missing source or destination"}
        ), 400

    success = delete_midi_port_connection(source, destination)
    return jsonify({"success": success})


def pretty_print(dom):
    return "\n".join(
        [line for line in dom.toprettyxml(indent=" " * 4).split("\n") if line.strip()]
    )


def pretty_save(file_path, sequences_tree):
    with open(file_path, "w", encoding="utf8") as outfile:
        outfile.write(pretty_print(sequences_tree))
