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


@webinterface.route("/")
def index():
    return render_template("index.html")


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

