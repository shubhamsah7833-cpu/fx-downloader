FX Instagram & YouTube Downloader — deployment

LOCAL TEST
1. Install Python 3.11+ and FFmpeg.
2. In this folder run:
   pip install -r requirements.txt
   python app.py
3. Open http://127.0.0.1:5000

MAKE IT PUBLIC
1. Upload these project files to a GitHub repository.
2. Create a web service on Render and connect the repository.
3. Build command: pip install -r requirements.txt && apt-get update && apt-get install -y ffmpeg
4. Start command: gunicorn app:app
5. Deploy. Render will give you a public https://...onrender.com URL.

IMPORTANT
- This is a starter project, not a guaranteed always-on production service.
- Hosting providers may limit large/long downloads, CPU, storage, and bandwidth.
- Keep the service private or add rate limits/authentication before public launch.
- Download only media you own or are authorized to save; follow each platform's terms.
