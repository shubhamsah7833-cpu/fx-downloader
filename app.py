import os
import re
import tempfile
import threading
import requests
import yt_dlp

from flask import Flask, render_template, request, send_file, jsonify

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

ALLOWED_HOSTS = (
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
    "instagram.com", "www.instagram.com"
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
MAX_TELEGRAM_FILE_SIZE = 49 * 1024 * 1024


def valid_media_url(url):
    match = re.match(r"^https?://([^/:?#]+)", url.strip(), re.I)
    if not match:
        return False
    host = match.group(1).lower()
    return any(
        host == allowed or host.endswith("." + allowed)
        for allowed in ALLOWED_HOSTS
    )


def download_video(url, temp_dir):
    output = os.path.join(temp_dir, "video.%(ext)s")
    options = {
        "outtmpl": output,
        "format": "best[ext=mp4][height<=720]/best[height<=720]/best",
        "noplaylist": True,
        "max_filesize": MAX_TELEGRAM_FILE_SIZE,
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 2,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    candidates = [
        os.path.join(temp_dir, name)
        for name in os.listdir(temp_dir)
        if os.path.isfile(os.path.join(temp_dir, name))
        and not name.endswith((".part", ".ytdl"))
    ]

    if not candidates:
        raise RuntimeError("Download file nahi mila.")

    path = max(candidates, key=os.path.getsize)

    if os.path.getsize(path) > MAX_TELEGRAM_FILE_SIZE:
        raise RuntimeError("Video Telegram upload limit se badi hai.")

    return path


def telegram_api(method):
    if not BOT_TOKEN:
        raise RuntimeError("Telegram bot token set nahi hai.")
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def send_message(chat_id, text):
    return requests.post(
        telegram_api("sendMessage"),
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )


def process_telegram_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        return

    if text.startswith("/start"):
        send_message(
            chat_id,
            "Welcome to FX Downloader!\n\n"
            "YouTube ya Instagram video link bhejein.\n"
            "Sirf wahi content download karein jise download karne ki permission ho."
        )
        return

    if text.startswith("/help"):
        send_message(chat_id, "YouTube ya Instagram ka supported video link bhejein.")
        return

    if not valid_media_url(text):
        send_message(
            chat_id,
            "❌ Valid YouTube ya Instagram link bhejein."
        )
        return

    send_message(chat_id, "⏳ Video process ho rahi hai. Thoda intezar karein.")

    try:
        with tempfile.TemporaryDirectory(prefix="fxbot_") as temp_dir:
            path = download_video(text, temp_dir)

            with open(path, "rb") as video:
                response = requests.post(
                    telegram_api("sendDocument"),
                    data={"chat_id": chat_id, "caption": "Downloaded by FX Downloader"},
                    files={"document": ("fx_download.mp4", video)},
                    timeout=(30, 180),
                )

            if not response.ok or not response.json().get("ok"):
                send_message(
                    chat_id,
                    "❌ Telegram video bhej nahi paya. File badi ho sakti hai."
                )

    except Exception:
        send_message(
            chat_id,
            "❌ Download nahi ho paya. Link check karein ya baad mein try karein."
        )


@app.get("/")
def home():
    return render_template("index.html", result_msg="")


@app.post("/")
def download():
    url = (request.form.get("url") or "").strip()
    format_type = request.form.get("format_type", "mp4")
    quality = request.form.get("quality", "best")

    if not valid_media_url(url):
        return render_template(
            "index.html",
            result_msg="❌ Valid YouTube ya Instagram link daalein."
        ), 400

    if format_type not in ("mp4", "mp3"):
        return render_template(
            "index.html",
            result_msg="❌ Format select sahi nahi hai."
        ), 400

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
            files = [
                os.path.join(temp_dir, name)
                for name in os.listdir(temp_dir)
                if name.lower().endswith("." + expected_ext)
            ]

            if not files:
                files = [
                    os.path.join(temp_dir, name)
                    for name in os.listdir(temp_dir)
                    if os.path.isfile(os.path.join(temp_dir, name))
                ]

            if not files:
                raise RuntimeError("Download file nahi mila.")

            path = files[0]
            return send_file(
                path,
                as_attachment=True,
                download_name="fx_download." + os.path.splitext(path)[1].lstrip(".")
            )

        except Exception:
            return render_template(
                "index.html",
                result_msg="❌ Download nahi ho paya. Link check karein ya baad mein try karein."
            ), 400


@app.post("/telegram-webhook")
def telegram_webhook():
    if WEBHOOK_SECRET:
        supplied_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if supplied_secret != WEBHOOK_SECRET:
            return jsonify({"ok": False}), 403

    update = request.get_json(silent=True) or {}
    message = update.get("message")

    if message:
        # Return quickly so Telegram doesn't wait for a long download.
        threading.Thread(
            target=process_telegram_message,
            args=(message,),
            daemon=True,
        ).start()

    return jsonify({"ok": True})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


def register_webhook():
    if not BOT_TOKEN:
        return

    base_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        return

    payload = {"url": base_url + "/telegram-webhook"}

    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET

    try:
        response = requests.post(
            telegram_api("setWebhook"),
            json=payload,
            timeout=15,
        )
        print("Telegram webhook registration:", response.status_code)
    except requests.RequestException as exc:
        print("Telegram webhook registration failed:", str(exc))


# Register the webhook when the service starts.
register_webhook()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
