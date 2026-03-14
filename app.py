"""
app.py  —  JioSaavn API Flask application

Endpoints:
  GET /result/?query=<url-or-text>&lyrics=true   ← universal (auto-detects type)
  GET /song/?query=<url-or-text>&lyrics=true
  GET /album/?query=<url-or-text>&lyrics=true
  GET /playlist/?query=<url-or-text>&lyrics=true
  GET /lyrics/?query=<song-url-or-lyrics-id>

All endpoints accept:
  - Full JioSaavn URL  (jiosaavn.com/song/..., /album/..., /featured/..., etc.)
  - Plain text search  (song name, album name, artist name)
"""

from flask import Flask, jsonify, request, render_template_string
from jiosaavn import get_result, get_song, get_album, get_playlist, get_lyrics

app = Flask(__name__)


def _q() -> str:
    return (request.args.get("query") or "").strip()


def _lyrics() -> bool:
    return request.args.get("lyrics", "").lower() in ("true", "1", "yes")


def _respond(data):
    if not data:
        return jsonify({"error": "No results found"}), 404
    # Return list if multiple, single dict if one
    return jsonify(data[0] if len(data) == 1 else data)


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JioSaavn API</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
    h1   { color: #1db954; }
    code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }
    pre  { background: #f4f4f4; padding: 16px; border-radius: 8px; overflow-x: auto; }
    a    { color: #1db954; }
    .endpoint { margin: 20px 0; padding: 16px; border-left: 3px solid #1db954; background: #f9f9f9; }
  </style>
</head>
<body>
  <h1>🎵 JioSaavn API</h1>
  <p>Unofficial JioSaavn API — supports both direct URLs and plain text search.</p>
  <hr>

  <div class="endpoint">
    <b>Universal Search / URL</b><br>
    <code>/result/?query=bigil</code><br>
    <code>/result/?query=https://www.jiosaavn.com/album/bigil/...</code><br>
    <code>/result/?query=bigil&lyrics=true</code>
  </div>

  <div class="endpoint">
    <b>Song</b><br>
    <code>/song/?query=kannaana+kanney</code><br>
    <code>/song/?query=https://www.jiosaavn.com/song/...</code>
  </div>

  <div class="endpoint">
    <b>Album</b><br>
    <code>/album/?query=bigil</code><br>
    <code>/album/?query=https://www.jiosaavn.com/album/bigil/...</code>
  </div>

  <div class="endpoint">
    <b>Playlist</b><br>
    <code>/playlist/?query=tamil hits</code><br>
    <code>/playlist/?query=https://www.jiosaavn.com/featured/...</code>
  </div>

  <div class="endpoint">
    <b>Lyrics</b><br>
    <code>/lyrics/?query=https://www.jiosaavn.com/song/...</code>
  </div>

  <hr>
  <p>Add <code>&amp;lyrics=true</code> to any endpoint to include lyrics. Takes slightly longer.</p>
</body>
</html>
""")


@app.route("/result/")
def result():
    q = _q()
    if not q:
        return jsonify({"error": "query parameter is required"}), 400
    return _respond(get_result(q, _lyrics()))


@app.route("/song/")
def song():
    q = _q()
    if not q:
        return jsonify({"error": "query parameter is required"}), 400
    return _respond(get_song(q, _lyrics()))


@app.route("/album/")
def album():
    q = _q()
    if not q:
        return jsonify({"error": "query parameter is required"}), 400
    data = get_album(q, _lyrics())
    if not data:
        return jsonify({"error": "Album not found"}), 404
    return jsonify(data)


@app.route("/playlist/")
def playlist():
    q = _q()
    if not q:
        return jsonify({"error": "query parameter is required"}), 400
    data = get_playlist(q, _lyrics())
    if not data:
        return jsonify({"error": "Playlist not found"}), 404
    return jsonify(data)


@app.route("/lyrics/")
def lyrics():
    q = _q()
    if not q:
        return jsonify({"error": "query parameter is required"}), 400
    # Accept song URL → get lyrics_id from song first
    from jiosaavn import get_song, is_jiosaavn_url
    if is_jiosaavn_url(q):
        songs = get_song(q, fetch_lyrics=True)
        if songs and songs[0].get("lyrics"):
            return jsonify({"lyrics": songs[0]["lyrics"]})
        return jsonify({"lyrics": ""}), 200
    # Plain lyrics_id
    from jiosaavn import get_lyrics as _get
    return jsonify({"lyrics": _get(q)})


# ── Error handlers ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
