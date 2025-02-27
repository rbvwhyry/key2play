from webinterface import webinterface
from flask import render_template, request, jsonify
import os

import time

ALLOWED_EXTENSIONS = {"mid", "musicxml", "mxl", "xml", "abc"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@webinterface.before_request
def before_request():
    excluded_routes = ["/api/get_homepage_data"]

    # Check if the current request path is in the excluded_routes list
    if request.path not in excluded_routes:
        webinterface.menu.last_activity = time.time()
        webinterface.menu.is_idle_animation_running = False


@webinterface.route("/newpage")
def newpage():
    return render_template("newpage.html")


@webinterface.route("/")
def index():
    return render_template("index.html")


@webinterface.route("/start")
def start():
    return render_template("start.html")


@webinterface.route("/home")
def home():
    return render_template("home.html")


@webinterface.route("/ledsettings")
def ledsettings():
    return render_template("ledsettings.html")


@webinterface.route("/ledanimations")
def ledanimations():
    return render_template("ledanimations.html")


@webinterface.route("/songs")
def songs():
    return render_template("songs.html")


@webinterface.route("/sequences")
def sequences():
    return render_template("sequences.html")


@webinterface.route("/ports")
def ports():
    return render_template("ports.html")


@webinterface.route("/network")
def network():
    return render_template("network.html")


@webinterface.route("/upload", methods=["POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify(success=False, error="no file")
        file = request.files["file"]
        filename = file.filename
        if os.path.exists("Songs/" + filename):
            return jsonify(
                success=False, error="file already exists", song_name=filename
            )
        if not allowed_file(file.filename):
            return jsonify(success=False, error="not a midi file", song_name=filename)

        filename = filename.replace("'", "")
        file.save(os.path.join(webinterface.config["UPLOAD_FOLDER"], filename))
        return jsonify(success=True, reload_songs=True, song_name=filename)


# Add new route to light up LEDs
@webinterface.route("/light-up", methods=["POST"])
def light_up():
    try:
        # Light up the 100th LED as green for 5 seconds
        light_up_led(99, (0, 255, 0), 5)  # Index 99, Green, 5 seconds
        return jsonify({"success": True, "message": "LED lit successfully!"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
