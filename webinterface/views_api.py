import subprocess
import threading
import psutil
import random
import shutil
import time
import mido
import json
import ast
import re
import os
from flask import jsonify, redirect, request, send_file, send_from_directory, url_for

import lib.colormaps as cmap
from lib.functions import fastColorWipe, find_between, get_last_logs
from lib.rpi_drivers import GPIO, Color
from lib.song_info import get_all_songs_info, resolve_song_path, DIR_SONGS_DEFAULT, DIR_SONGS_USER
from lib.log_setup import logger
from webinterface import webinterface
from webinterface.views import allowed_file

# IMPORTANT!!! 👇
# ANY CHANGE HERE, AND THEN ANY UPDATE VIA GIT PULL WILL REQUIRE THE PI TO BE RESTARTED TO WORK!
# IMPORTANT!!! 👆

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_CONFIG_KEY = re.compile(r"^[a-zA-Z0-9_]+$")

os.makedirs(DIR_SONGS_USER, exist_ok=True)

SENSECOVER = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSECOVER, GPIO.IN, GPIO.PUD_UP)

pid = psutil.Process(os.getpid())

# 224 definitely doesn't work;
# 223 seems to be the brightest for 200 LEDs (sometimes?);
# 222 is probably safest
brightest = 222

### ===== captive portal ===== ###

@webinterface.before_request
def captive_portal_intercept():
    """When hotspot is active, serve the captive portal page for any non-API browser request."""
    if not hasattr(webinterface, 'platform'):
        return None  #platform not initialized yet

    path = request.path

    #let API calls and static files through
    if path.startswith('/api/') or path.startswith('/static/'):
        return None

    #let captive portal detection URLs be handled by their own route
    if path in ('/generate_204', '/gen_204', '/hotspot-detect.html', '/library/test/success.html', '/connecttest.txt'):
        return None

    try:
        if webinterface.platform.is_hotspot_active_cached():
            return build_captive_html(), 200
    except Exception:
        pass

    return None  #not in hotspot mode — let normal routes handle it

@webinterface.route("/generate_204")
@webinterface.route("/gen_204")
@webinterface.route("/hotspot-detect.html")
@webinterface.route("/library/test/success.html")
@webinterface.route("/connecttest.txt")
def captive_portal_redirect():
    if not webinterface.platform.is_hotspot_active_cached():
        return "", 204

    return build_captive_html(), 200

def build_captive_html():
    """Builds the captive portal page with cached networks pre-rendered in the HTML."""
    try:
        networks = webinterface.platform.scan_wifi_networks()
    except Exception:
        networks = []

    #build network rows as raw HTML — no JavaScript fetch needed
    if networks:
        rows = ""
        for n in networks:
            ssid_safe = n["ssid"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            ssid_attr = ssid_safe.replace("'", "\\'").replace('"', "&quot;")
            lock = "" if n.get("is_open") else "&#x1f512; "
            rows += (
                f'<div class="net" onclick="pick(\'{ssid_attr}\',{str(n.get("is_open", False)).lower()})">'
                f'<span class="net-name">{lock}{ssid_safe}</span>'
                f'<span class="net-info">{n["signal"]}%</span>'
                f'</div>'
            )
        network_html = rows
    else:
        network_html = '<p class="msg">No networks found</p>'

    return CAPTIVE_TEMPLATE.replace("{{NETWORKS}}", network_html)

CAPTIVE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ami — WiFi Setup</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f1f5;color:#1e1f26;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:24px}
h1{font-size:28px;margin:20px 0 4px;letter-spacing:-0.02em}
.sub{font-size:13px;color:#9ca3af;margin-bottom:20px}
.card{background:#fff;border-radius:16px;box-shadow:0 1px 3px rgba(0,0,0,.04),0 8px 32px rgba(0,0,0,.06);width:100%;max-width:400px;padding:20px;margin-bottom:16px}
.card h2{font-size:16px;margin-bottom:12px}
.net{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-bottom:1px solid #f1f2f6;cursor:pointer;transition:background .15s;border-radius:6px}
.net:hover{background:rgba(99,102,241,.07)}
.net-name{font-weight:500;font-size:14px}
.net-info{font-size:12px;color:#9ca3af}
.btn{background:#6366f1;color:#fff;border:none;padding:10px 20px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;width:100%;margin-top:8px;transition:background .2s}
.btn:hover{background:#4f46e5}
.btn:disabled{opacity:.4;cursor:not-allowed}
input[type=password]{width:100%;padding:10px 12px;border:1px solid #e2e4ea;border-radius:8px;font-size:14px;margin:8px 0;box-sizing:border-box}
.msg{font-size:13px;color:#6b7280;text-align:center;margin-top:8px}
.msg.err{color:#c02f2f}
.msg.ok{color:#22c55e}
#networks{max-height:300px;overflow-y:auto}
.spinner{display:inline-block;width:16px;height:16px;border:2px solid #e2e4ea;border-top-color:#6366f1;border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<h1>ami</h1>
<p class="sub">WiFi Setup — tap a network to connect</p>

<div class="card">
<h2>Available Networks</h2>
<div id="networks">{{NETWORKS}}</div>
</div>

<div class="card" id="connect-card" style="display:none">
<h2 id="connect-title">Connect</h2>
<input type="password" id="pw" placeholder="WiFi password">
<button class="btn" id="btn-connect" onclick="connect()">Connect</button>
<p class="msg" id="status"></p>
</div>

<p class="msg">You can also open <strong>http://10.42.0.1</strong> in your browser</p>

<script>
var selectedSsid='';
var selectedOpen=false;

function pick(ssid,isOpen){
  selectedSsid=ssid;
  selectedOpen=isOpen;
  var card=document.getElementById('connect-card');
  var pw=document.getElementById('pw');
  var status=document.getElementById('status');
  document.getElementById('connect-title').textContent='Connect to '+ssid;
  card.style.display='block';
  status.textContent='';
  if(isOpen){
    pw.style.display='none';
  }else{
    pw.style.display='block';
    pw.value='';
    pw.focus();
  }
}

function connect(){
  var pw=document.getElementById('pw').value;
  var btn=document.getElementById('btn-connect');
  var status=document.getElementById('status');

  if(!selectedOpen&&!pw){
    status.className='msg err';
    status.textContent='Password required';
    return;
  }

  btn.disabled=true;
  btn.innerHTML='<span class="spinner"></span>Connecting...';
  status.className='msg';
  status.textContent='This may take a moment...';

  var xhr=new XMLHttpRequest();
  xhr.open('POST','/api/wifi/connect',true);
  xhr.setRequestHeader('Content-Type','application/x-www-form-urlencoded');
  xhr.onload=function(){
    btn.disabled=false;
    btn.textContent='Connect';
    try{
      var d=JSON.parse(xhr.responseText);
      if(d.success){
        status.className='msg ok';
        status.textContent='Connected! Connect your device to '+selectedSsid+', then visit ami.local';
      }else{
        status.className='msg err';
        status.textContent=d.message||'Connection failed';
      }
    }catch(e){
      status.className='msg err';
      status.textContent='Connection lost. Reconnect to ami WiFi and try again.';
    }
  };
  xhr.onerror=function(){
    btn.disabled=false;
    btn.textContent='Connect';
    status.className='msg err';
    status.textContent='Connection lost. Reconnect to ami WiFi and try again.';
  };
  xhr.send('ssid='+encodeURIComponent(selectedSsid)+'&password='+encodeURIComponent(pw));
}
</script>
</body>
</html>"""

### ===== songs: list / load / delete / download / record ===== ###

@webinterface.route("/api/get_songs", methods=["GET"])
def get_songs():
    default_songs = os.listdir(DIR_SONGS_DEFAULT) if os.path.isdir(DIR_SONGS_DEFAULT) else []
    user_songs = os.listdir(DIR_SONGS_USER) if os.path.isdir(DIR_SONGS_USER) else []
    combined = list(set(filter(allowed_file, default_songs + user_songs)))
    combined.sort()
    return jsonify(combined)

@webinterface.route("/api/get_songs_info", methods=["GET"])
def get_songs_info():
    info = get_all_songs_info()
    return jsonify(success=True, songs=info)

@webinterface.route("/api/get_current_song", methods=["GET"])
def get_current_song():
    song_tracks = webinterface.learning.song_tracks
    song_tracks = [msg.__dict__ for msg in song_tracks]
    return jsonify(
        tracks=song_tracks,
        ticks_per_beat=webinterface.learning.ticks_per_beat,
        tempo=webinterface.learning.song_tempo
    )

@webinterface.route("/api/load_local_midi", methods=["POST"])
def load_local_midi():
    filename = request.values.get("filename", default=None)
    if not filename:
        return jsonify(success=False)
    full_path = resolve_song_path(filename)
    if not full_path:
        return jsonify(success=False, error="song not found")
    threading.Thread(target=webinterface.learning.load_midi, args=(full_path,), daemon=True).start()
    return jsonify(success=True)

@webinterface.route("/api/delete_song", methods=["POST"])
def delete_song():
    filename = request.values.get("filename", default=None)
    if not filename:
        return jsonify(success=False, error="no filename")
    path = resolve_song_path(filename)
    if not path:
        return jsonify(success=False, error="song not found")
    os.remove(path)
    return jsonify(success=True)

@webinterface.route("/api/download_song/<filename>", methods=["GET"])
def download_song(filename):
    path = resolve_song_path(filename)
    if not path:
        return jsonify(success=False, error="song not found"), 404
    return send_file(os.path.abspath(path), as_attachment=True, download_name=filename)

@webinterface.route("/api/save_recording", methods=["POST"])
def save_recording():
    data = request.get_json()
    if not data:
        return jsonify(success=False, error="no data")

    filename = data.get("filename", "").strip()
    events = data.get("events", [])

    if not filename:
        return jsonify(success=False, error="no filename")
    if not events:
        return jsonify(success=False, error="no events recorded")

    #sanitize filename — strip path separators, traversal, and non-printable chars
    filename = filename.replace("'", "").replace("/", "").replace("\\", "").replace("..", "").replace("\x00", "")
    filename = filename.strip(". ")  #no leading dots or spaces
    if not filename:
        return jsonify(success=False, error="invalid filename")
    if not filename.lower().endswith((".mid", ".midi")):
        filename += ".mid"

    save_path = os.path.join(DIR_SONGS_USER, filename)

    if os.path.exists(save_path):
        return jsonify(success=False, error="file already exists")

    try:
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)

        track.append(mido.MetaMessage('set_tempo', tempo=500000))  #120 BPM default

        #sort events by time just in case
        events.sort(key=lambda e: e.get("time", 0))

        prev_time_ms = 0

        for evt in events:
            evt_type = evt.get("type")
            note = evt.get("note")
            velocity = evt.get("velocity", 64)
            time_ms = evt.get("time", 0)

            if evt_type not in ("note_on", "note_off") or note is None:
                continue

            #convert millisecond delta to ticks
            delta_ms = max(0, time_ms - prev_time_ms)
            delta_ticks = int(delta_ms * 480 / 500)  #at 120 BPM: 500ms per beat, 480 ticks per beat

            if evt_type == "note_off":
                velocity = 0

            track.append(mido.Message(evt_type, note=int(note), velocity=int(velocity), time=delta_ticks))
            prev_time_ms = time_ms

        mid.save(save_path)
        return jsonify(success=True, filename=filename)

    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)  #clean up partial file
        return jsonify(success=False, error=str(e))

@webinterface.route("/api/get_storage_info", methods=["GET"])
def get_storage_info():
    usage = shutil.disk_usage(DIR_SONGS_USER)

    total_size = 0
    count = 0
    for d in [DIR_SONGS_DEFAULT, DIR_SONGS_USER]:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.lower().endswith((".mid", ".midi")):
                total_size += os.path.getsize(os.path.join(d, f))
                count += 1

    return jsonify(
        success=True,
        available_bytes=usage.free,
        songs_count=count,
        songs_total_bytes=total_size
    )

### ===== MIDI: keys / events / ports ===== ###

@webinterface.route("/api/currently_pressed_keys", methods=["GET"])
def currently_pressed_keys():
    with webinterface.midiports._keys_lock:
        snapshot = list(webinterface.midiports.currently_pressed_keys)
    result = [
        {"note": msg.note, "velocity": msg.velocity}
        for msg in snapshot
    ]
    return jsonify(result)

@webinterface.route("/api/drain_midi_events", methods=["GET"])
def drain_midi_events():
    events = []
    while webinterface.midiports.frontend_events:  #drain all accumulated events since last poll
        events.append(webinterface.midiports.frontend_events.popleft())
    return jsonify(events)

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

### ===== LEDs ===== ###

@webinterface.route("/api/set_light/<light_num>")
def set_light(light_num):
    try:
        light_num = int(light_num)
    except (TypeError, ValueError):
        return jsonify(success=False, error="invalid light number"), 400
    strip = webinterface.ledstrip.strip
    if light_num < 0 or light_num >= strip.numPixels():
        return jsonify(success=False, error="light index out of range"), 400
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
    try:
        lights = json.loads(lights)
    except (TypeError, ValueError, json.JSONDecodeError):
        return jsonify(success=False, error="invalid JSON"), 400
    if not lights:
        return jsonify(success=True)
    strip = webinterface.ledstrip.strip
    for light_num, color in lights:
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
    try:
        indices = json.loads(indices)
    except (TypeError, ValueError, json.JSONDecodeError):
        return jsonify(success=False, error="invalid JSON"), 400
    if not indices:
        return jsonify(success=True)
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
    try:
        color = json.loads(color)
    except (TypeError, ValueError, json.JSONDecodeError):
        return jsonify(success=False, error="invalid JSON"), 400
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

### ===== WiFi ===== ###

@webinterface.route("/api/wifi/status", methods=["GET"])
def wifi_status():
    is_hotspot = webinterface.platform.is_hotspot_running()
    is_connected, ssid, address = webinterface.platform.get_current_connections()

    return jsonify(
        success=True,
        connected=is_connected,
        hotspot_active=is_hotspot,
        ssid=ssid if is_connected else None,
        ip=address if is_connected else None,
        hotspot_name="ami"
    )

@webinterface.route("/api/wifi/scan", methods=["GET"])
def wifi_scan():
    networks = webinterface.platform.scan_wifi_networks()
    return jsonify(success=True, networks=networks)

@webinterface.route("/api/wifi/deep_scan", methods=["GET"])
def wifi_deep_scan():
    """Temporarily drops the hotspot to scan, then restarts it. Phone will briefly disconnect."""
    was_hotspot = webinterface.platform.is_hotspot_running()

    if was_hotspot:
        webinterface.platform.disable_hotspot()
        time.sleep(2)  #give the radio time to switch back to station mode

    networks = webinterface.platform.scan_wifi_networks()

    if was_hotspot:
        webinterface.platform.enable_hotspot()

    return jsonify(success=True, networks=networks)

@webinterface.route("/api/wifi/connect", methods=["POST"])
def wifi_connect():
    ssid = request.values.get("ssid")
    password = request.values.get("password", "")

    if not ssid:
        return jsonify(success=False, error="no SSID provided")

    result = webinterface.platform.connect_to_wifi(ssid, password, webinterface.usersettings)

    if result:
        return jsonify(success=True, message=f"Connected to {ssid}")

    return jsonify(success=False, message="Wrong password or network unavailable. Hotspot restarted — reconnect to ami and try again.")

@webinterface.route("/api/wifi/forget", methods=["POST"])
def wifi_forget():
    forgotten = webinterface.platform.forget_all_wifi()

    if forgotten:
        webinterface.platform.enable_hotspot()
        webinterface.usersettings.change_setting_value("is_hotspot_active", 1)

    return jsonify(success=True, forgotten=forgotten, count=len(forgotten))

@webinterface.route("/api/connect_to_wifi", methods=["POST"])
def connect_to_wifi():
    ssid = request.values.get("ssid")
    psk = request.values.get("psk")
    webinterface.platform.connect_to_wifi(ssid, psk, webinterface.usersettings)
    return jsonify(success=True)

@webinterface.route("/api/disconnect_from_wifi", methods=["POST"])
def disconnect_from_wifi():
    webinterface.platform.disconnect_from_wifi(webinterface.usersettings)
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

### ===== database: config table ===== ###

@webinterface.route("/api/get_config/<key>", methods=["GET"])
def get_config(key):
    if not key or not _SAFE_CONFIG_KEY.match(key):
        return jsonify(success=False, error="invalid key"), 400
    value = webinterface.appconfig.get_config(key)
    return jsonify(success=True, value=value)

@webinterface.route("/api/set_config/<key>", methods=["POST"])
def set_config(key):
    if not key or not _SAFE_CONFIG_KEY.match(key):
        return jsonify(success=False, error="invalid key"), 400
    value = request.values.get("value")
    if value is None:
        return jsonify(success=False, error="no value"), 400
    value = str(value)[:1000]  #cap length to prevent oversized entries
    webinterface.appconfig.set_config(key, value)
    return jsonify(success=True)

@webinterface.route("/api/delete_config/<key>", methods=["DELETE"])
def delete_config(key):
    if not key or not _SAFE_CONFIG_KEY.match(key):
        return jsonify(success=False, error="invalid key"), 400
    webinterface.appconfig.delete_config(key)
    return jsonify(success=True)

@webinterface.route("/api/get_config_dump", methods=["GET"])
def get_config_dump():
    dump = webinterface.appconfig.get_sqlite_dump()
    return jsonify(success=True, dump=dump)

@webinterface.route("/api/backup_config_file_and_reset_to_factory", methods=["POST"])
def backup_config_file_and_reset_to_factory():
    webinterface.appconfig.backup_config_file_and_reset_to_factory()
    return jsonify(success=True)

### ===== database: map table ===== ###

@webinterface.route("/api/get_row/<key>", methods=["GET"])
def get_row(key):
    value = webinterface.appmap.get_midi_led_row(key)
    return jsonify(success=True, value=value)

@webinterface.route("/api/set_row/<key>", methods=["POST"])
def set_row(key):
    if not key or not _SAFE_CONFIG_KEY.match(key):
        return jsonify(success=False, error="invalid key"), 400
    try:
        led_index = int(request.values.get("led_index"))
        r = int(request.values.get("r"))
        g = int(request.values.get("g"))
        b = int(request.values.get("b"))
        time_on = int(request.values.get("time_on"))
        time_off = int(request.values.get("time_off"))
    except (TypeError, ValueError):
        return jsonify(success=False, error="invalid values"), 400
    webinterface.appmap.set_midi_led_row(key, led_index, r, g, b, time_on, time_off)
    return jsonify(success=True)

@webinterface.route("/api/delete_row/<key>", methods=["DELETE"])
def delete_row(key):
    if not key or not _SAFE_CONFIG_KEY.match(key):
        return jsonify(success=False, error="invalid key"), 400
    webinterface.appmap.delete_midi_led_row(key)
    return jsonify(success=True)

@webinterface.route("/api/get_map", methods=["GET"])
def get_map():
    mappings = webinterface.appmap.get_midi_led_map()
    result = []
    for mapping in mappings:
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

@webinterface.route("/api/delete_all_maps", methods=["POST"])
def delete_all_maps():
    webinterface.appmap.delete_all_maps()
    return jsonify(success=True)

### ===== system / misc ===== ###

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
        "reinitialize_network_on_boot": webinterface.appconfig.reinitialize_network_on_boot(),
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

@webinterface.route("/api/update_to_release", methods=["POST"])
def update_to_release():
    release = request.values.get("release", default=None)
    if not release:
        return jsonify(success=False, error="no release specified")
    #validate release name — only allow safe filenames ending in .zip
    if not re.match(r'^[a-zA-Z0-9._-]+\.zip$', release):
        return jsonify(success=False, error="invalid release name"), 400
    if '..' in release or '/' in release or '\\' in release:
        return jsonify(success=False, error="invalid release name"), 400
    logger.info(f"updating to release {release}")
    import requests
    req = requests.get(f"https://rbvwhyry.github.io/key2play/{release}", timeout=60)
    if req.status_code != 200:
        return jsonify(success=False, error=f"download failed: HTTP {req.status_code}")
    with open(release, "wb") as fd:
        for chunk in req.iter_content(chunk_size=128):
            fd.write(chunk)
    logger.info(f"downloaded release to {release}")
    releasedir = release.removesuffix(".zip")
    subprocess.run(["unzip", "-o", release, "-d", releasedir])
    subprocess.run(["cp", "-R", f"{releasedir}/", "."])
    return jsonify(success=True)

@webinterface.route("/api/get_random_gif", methods=["GET"])
def get_random_gif():
    raw = request.args.get("folders", "")
    requested = [s.strip() for s in raw.split(",") if s.strip()]
    if not requested:
        return jsonify(success=False, error="no folders provided"), 400
    folders = [f for f in requested if _SAFE_NAME.match(f)]
    if not folders:
        return jsonify(success=False, error="no valid folder names"), 400
    pool = []
    for sub in folders:
        folder_path = os.path.join(webinterface.static_folder, sub)
        if not os.path.isdir(folder_path):
            continue
        for name in os.listdir(folder_path):
            if name.lower().endswith(".gif"):
                pool.append((sub, name))
    if not pool:
        return jsonify(success=False, error="no gifs found in requested folders"), 404
    sub, name = random.choice(pool)
    return jsonify(success=True, url=url_for("static", filename=f"{sub}/{name}"))

@webinterface.route("/static/js/listenWorker.js")
def serve_worker():
    return send_from_directory("static/js", "listenWorker.js", mimetype="application/javascript")

@webinterface.route("/api/get_logs", methods=["GET"])
def get_logs():
    last_logs = request.args.get("last_logs")
    return get_last_logs(last_logs)

@webinterface.route("/api/get_colormap_gradients", methods=["GET"])
def get_colormap_gradients():
    return jsonify(cmap.colormaps_preview)
