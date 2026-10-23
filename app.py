import os
import re
import tempfile
from flask import Flask, render_template, request, send_file
import yt_dlp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # Limit form requests, not media downloads

ALLOWED_HOSTS = (
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
    "instagram.com", "www.instagram.com"
)



def valid_media_url(url):
    # Restrict URLs to the services this app is intended to support.
    match = re.match(r"^https?://([^/:?#]+)", url.strip(), re.I)
    if not match:
        return False
    host = match.group(1).lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)

@app.get("/")
def home():
    return render_template("index.html", result_msg="")

@app.post("/")
def download():
    url = (request.form.get("url") or "").strip()
    format_type = request.form.get("format_type", "mp4")
    quality = request.form.get("quality", "best")

    if not valid_media_url(url):
        return render_template("index.html", result_msg="❌ Valid YouTube ya Instagram link daalein."), 400
    if format_type not in ("mp4", "mp3"):
        return render_template("index.html", result_msg="❌ Format select sahi nahi hai."), 400

    # Each request gets its own temporary folder to avoid filename collisions.
    with tempfile.TemporaryDirectory(prefix="fxdl_") as temp_dir:
        outtmpl = os.path.join(temp_dir, "download.%(ext)s")
        if format_type == "mp3":
            ydl_opts = {
                "outtmpl": outtmpl,
                "format": "bestaudio/best",
                "noplaylist": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
        else:
            fmt = {
                "best": "best",
                "720": "best[height<=720]/best",
                "480": "best[height<=480]/best",
            }.get(quality, "best")
            ydl_opts = {
                "outtmpl": outtmpl,
                "format": fmt,
                "noplaylist": True,
                "merge_output_format": "mp4",
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)

            expected_ext = "mp3" if format_type == "mp3" else "mp4"
            files = [os.path.join(temp_dir, name) for name in os.listdir(temp_dir)
                     if name.lower().endswith("." + expected_ext)]
            if not files:
                # Some videos may be downloaded in another container format.
                files = [os.path.join(temp_dir, name) for name in os.listdir(temp_dir)
                         if os.path.isfile(os.path.join(temp_dir, name))]
            if not files:
                raise RuntimeError("Download file nahi mila. Dusra link try karein.")

            path = files[0]
            return send_file(path, as_attachment=True,
                             download_name="fx_download." + os.path.splitext(path)[1].lstrip("."))
        except Exception:
            # Avoid exposing server internals in the public response.
            return render_template("index.html",
                result_msg="❌ Download nahi ho paya. Link check karein ya kuch der baad try karein."), 400

if __name__ == "__main__":
    # Local development only. Production hosting uses its own server command.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
