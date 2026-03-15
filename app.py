"""
app.py — JioSaavn API (Flask)

Endpoints identical to cyberboysumanjay/JioSaavnAPI + text search for album/artist.

Routes:
  GET /result/?query=<url-or-text>&lyrics=true   ← universal
  GET /song/?query=<url-or-text>&lyrics=true
  GET /album/?query=<url-or-text>&lyrics=true
  GET /playlist/?query=<url-or-text>&lyrics=true
  GET /lyrics/?query=<url-or-lyrics-id>

All endpoints accept both direct JioSaavn URLs and plain text search.
"""

from flask import Flask, jsonify, request, render_template_string
from jiosaavn import get_result, get_song, get_album, get_playlist, get_lyrics

app = Flask(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────
def q():
    return (request.args.get("query") or "").strip()


def use_lyrics():
    return request.args.get("lyrics", "").lower() in ("true", "1", "yes")


def respond(data):
    if not data:
        return jsonify({"error": "No results found"}), 404
    return jsonify(data[0] if len(data) == 1 else data)


# ── routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string("""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JioSaavn API</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:780px;margin:50px auto;padding:0 20px;color:#222;line-height:1.6}
  h1{color:#1db954;margin-bottom:4px}
  h2{margin-top:32px;margin-bottom:8px;font-size:1rem;color:#555}
  code{background:#f0f0f0;padding:2px 7px;border-radius:4px;font-size:.9em}
  .e{background:#f9f9f9;border-left:3px solid #1db954;padding:12px 16px;margin:8px 0;border-radius:0 6px 6px 0}
  a{color:#1db954}
</style>
</head><body>
<h1>🎵 JioSaavn API</h1>
<p>Unofficial API — supports JioSaavn URLs and plain text search on all endpoints.</p>
<hr>

<h2>Universal (auto-detects song/album/playlist or searches by name)</h2>
<div class="e">
  <code>/result/?query=bigil</code><br>
  <code>/result/?query=https://www.jiosaavn.com/album/bigil/-ZHywILiMS4_</code><br>
  <code>/result/?query=kannaana+kanney&amp;lyrics=true</code>
</div>

<h2>Song</h2>
<div class="e">
  <code>/song/?query=bigil+bigil+bigiluma</code><br>
  <code>/song/?query=https://www.jiosaavn.com/song/...</code>
</div>

<h2>Album</h2>
<div class="e">
  <code>/album/?query=bigil</code><br>
  <code>/album/?query=https://www.jiosaavn.com/album/bigil/-ZHywILiMS4_</code>
</div>

<h2>Playlist</h2>
<div class="e">
  <code>/playlist/?query=tamil hits 2024</code><br>
  <code>/playlist/?query=https://www.jiosaavn.com/featured/...</code>
</div>

<h2>Lyrics</h2>
<div class="e">
  <code>/lyrics/?query=https://www.jiosaavn.com/song/...</code>
</div>

<hr>
<p>Add <code>&amp;lyrics=true</code> to any endpoint to include lyrics (slower).</p>
</body></html>""")


@app.route("/result/")
def result():
    v = q()
    if not v:
        return jsonify({"error": "query parameter required"}), 400
    return respond(get_result(v, use_lyrics()))


@app.route("/song/")
def song():
    v = q()
    if not v:
        return jsonify({"error": "query parameter required"}), 400
    return respond(get_song(v, use_lyrics()))


@app.route("/album/")
def album():
    v = q()
    if not v:
        return jsonify({"error": "query parameter required"}), 400
    data = get_album(v, use_lyrics())
    if not data:
        return jsonify({"error": "Album not found"}), 404
    return jsonify(data)


@app.route("/playlist/")
def playlist():
    v = q()
    if not v:
        return jsonify({"error": "query parameter required"}), 400
    data = get_playlist(v, use_lyrics())
    if not data:
        return jsonify({"error": "Playlist not found"}), 404
    return jsonify(data)


@app.route("/lyrics/")
def lyrics():
    v = q()
    if not v:
        return jsonify({"error": "query parameter required"}), 400
    return jsonify({"lyrics": get_lyrics(v)})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
