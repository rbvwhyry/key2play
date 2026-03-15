import os
import time
import shutil

from flask import jsonify, render_template, request, send_from_directory

from webinterface import webinterface

ALLOWED_EXTENSIONS = {"mid", "midi", "musicxml", "mxl", "xml", "abc"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@webinterface.before_request
def before_request():
    excluded_routes = ["/api/get_homepage_data"]


@webinterface.route("/")
def index():
    return render_template("index.html")


@webinterface.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(webinterface.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@webinterface.route("/upload", methods=["POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify(success=False, error="no file")
        file = request.files["file"]
        filename = file.filename
        
        if os.path.exists(os.path.join("Songs_User_Upload", filename)):
            return jsonify(
                success=False, error="file already exists", song_name=filename
            )
        
        usage = shutil.disk_usage("Songs_User_Upload")
        avg_size = 30000  # 30KB conservative estimate
        songs_dir = "Songs_User_Upload"
        if os.path.isdir(songs_dir):
            sizes = [os.path.getsize(os.path.join(songs_dir, f)) for f in os.listdir(songs_dir) if f.lower().endswith((".mid", ".midi"))]
            if sizes:
                avg_size = sum(sizes) / len(sizes)
        remaining = int(usage.free / avg_size)
        
        if remaining <= 5:  # safety buffer — user sees "no space" but we actually have ~5 songs of headroom
            return jsonify(success=False, error="no space", song_name=filename)
            
        if not allowed_file(file.filename):
            return jsonify(success=False, error="not a midi file", song_name=filename)

        filename = filename.replace("'", "")
        file.save(os.path.join(webinterface.config["UPLOAD_FOLDER"], filename))
        return jsonify(success=True, reload_songs=True, song_name=filename)
