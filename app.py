from flask import Flask, jsonify, request, render_template_string
from jiosaavn import get_result, get_song, get_album, get_playlist, fetch_lyrics

app = Flask(__name__)

def _q():    return (request.args.get("query") or "").strip()
def _lyr():  return request.args.get("lyrics", "").lower() in ("true", "1")
def _ok(d):
    if not d: return jsonify({"error": "No results found"}), 404
    return jsonify(d[0] if len(d) == 1 else d)

@app.route("/")
def index():
    return render_template_string("""<!DOCTYPE html><html><head>
<title>JioSaavn API</title>
<style>body{font-family:system-ui;max-width:700px;margin:40px auto;padding:0 20px}
h1{color:#1db954}code{background:#f0f0f0;padding:2px 6px;border-radius:4px}
.e{border-left:3px solid #1db954;padding:10px 14px;margin:10px 0;background:#f9f9f9}</style>
</head><body>
<h1>🎵 JioSaavn API</h1>
<p>All endpoints accept a JioSaavn URL <em>or</em> plain text.</p>
<div class="e"><code>/result/?query=bigil</code><br>
<code>/result/?query=https://www.jiosaavn.com/song/.../...</code></div>
<div class="e"><code>/song/?query=kannaana+kanney</code></div>
<div class="e"><code>/album/?query=bigil</code><br>
<code>/album/?query=https://www.jiosaavn.com/album/bigil/...</code></div>
<div class="e"><code>/playlist/?query=https://www.jiosaavn.com/featured/...</code></div>
<div class="e"><code>/lyrics/?query=https://www.jiosaavn.com/song/.../...</code></div>
<p>Add <code>&amp;lyrics=true</code> to include lyrics.</p>
</body></html>""")

@app.route("/result/")
def result():
    q = _q()
    if not q: return jsonify({"error": "query required"}), 400
    return _ok(get_result(q, _lyr()))

@app.route("/song/")
def song():
    q = _q()
    if not q: return jsonify({"error": "query required"}), 400
    return _ok(get_song(q, _lyr()))

@app.route("/album/")
def album():
    q = _q()
    if not q: return jsonify({"error": "query required"}), 400
    data = get_album(q, _lyr())
    if not data: return jsonify({"error": "Album not found"}), 404
    return jsonify(data)

@app.route("/playlist/")
def playlist():
    q = _q()
    if not q: return jsonify({"error": "query required"}), 400
    data = get_playlist(q, _lyr())
    if not data: return jsonify({"error": "Playlist not found"}), 404
    return jsonify(data)

@app.route("/lyrics/")
def lyrics():
    q = _q()
    if not q: return jsonify({"error": "query required"}), 400
    return jsonify({"lyrics": fetch_lyrics(q)})

@app.errorhandler(404)
def e404(e): return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def e500(e): return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
