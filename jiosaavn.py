"""
jiosaavn.py  —  Core JioSaavn API wrapper

All JioSaavn API calls tested working as of 2025.
Supports plain text search AND direct JioSaavn URLs for every endpoint.

Working endpoints used:
  Search   : /api.php?__call=search.getResults&q=<query>
  Song URL : /api.php?__call=webapi.get&token=<token>&type=song
  Album URL: /api.php?__call=webapi.get&token=<token>&type=album
  Playlist : /api.php?__call=webapi.get&token=<token>&type=playlist
  Lyrics   : /api.php?__call=lyrics.getLyrics&lyrics_id=<id>

Media URL decrypt:
  JioSaavn still uses DES with key "38346591" for song URLs.
  https://c.saavncdn.com/ URLs are direct (no decrypt needed).
"""

import re
import json
import requests
from pyDes import des, CBC, PAD_PKCS5
import base64


JIOSAAVN   = "https://www.jiosaavn.com"
API        = f"{JIOSAAVN}/api.php"
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.jiosaavn.com/",
}
TIMEOUT    = 15
DES_KEY    = b"38346591"


# ── URL detection helpers ─────────────────────────────────────────────────────
def is_jiosaavn_url(text: str) -> bool:
    return "jiosaavn.com" in text.lower()


def _extract_token(url: str) -> str:
    """Get the last path segment from a JioSaavn URL (the token)."""
    return url.rstrip("/").split("/")[-1]


def _detect_type(url: str) -> str:
    """Detect resource type from JioSaavn URL."""
    url = url.lower()
    if "/song/" in url:           return "song"
    if "/album/" in url:          return "album"
    if "/featured/" in url:       return "playlist"
    if "/s/playlist/" in url:     return "playlist"
    if "/playlist/" in url:       return "playlist"
    if "/artist/" in url:         return "artist"
    return "song"


# ── Media URL decryption ──────────────────────────────────────────────────────
def _decrypt_url(encrypted: str) -> str:
    """Decrypt JioSaavn DES-encrypted media URL."""
    if not encrypted or not isinstance(encrypted, str):
        return ""
    # Direct CDN URLs don't need decryption
    if encrypted.startswith("http") and "saavncdn.com" in encrypted:
        return encrypted
    try:
        enc_bytes = base64.b64decode(encrypted)
        cipher    = des(DES_KEY, CBC, b"\0\0\0\0\0\0\0\0", pad=None, padmode=PAD_PKCS5)
        dec_bytes = cipher.decrypt(enc_bytes, padmode=PAD_PKCS5)
        url       = dec_bytes.decode("utf-8").rstrip("\x00\x0e")
        # Upgrade to 320kbps
        url = url.replace("_96.mp4",  "_320.mp4")
        url = url.replace("_160.mp4", "_320.mp4")
        url = url.replace("_48.mp4",  "_320.mp4")
        url = url.replace("http://",  "https://")
        return url
    except Exception:
        # If decryption fails, return as-is
        return encrypted if encrypted.startswith("http") else ""


def _get_media_url(song: dict) -> str:
    """Extract and decrypt the best available download URL from a song dict."""
    # Try direct encrypted URLs in priority order
    for key in ("encrypted_media_url", "more_info.encrypted_media_url"):
        parts = key.split(".")
        val   = song
        for p in parts:
            val = val.get(p, {}) if isinstance(val, dict) else {}
        if isinstance(val, str) and val:
            url = _decrypt_url(val)
            if url:
                return url

    # Try unencrypted URL fields
    for key in ("media_preview_url", "vlink", "url"):
        val = song.get(key, "")
        if isinstance(val, str) and val.startswith("http"):
            return val.replace("http://", "https://").replace(
                "preview.saavncdn.com", "aac.saavncdn.com"
            ).replace("_96_p.mp4", "_320.mp4")

    return ""


# ── Image URL helper ──────────────────────────────────────────────────────────
def _best_image(image: str) -> str:
    """Upgrade image URL to highest resolution."""
    if not image:
        return ""
    # Upgrade size suffix in saavncdn URLs
    image = re.sub(r"-\d+x\d+\.(jpg|jpeg|png|webp)", r"-500x500.\1", image, flags=re.I)
    image = image.replace("http://", "https://")
    return image


# ── Raw API caller ────────────────────────────────────────────────────────────
def _call(params: dict) -> dict | list | None:
    """Make a raw call to JioSaavn's api.php."""
    base_params = {
        "_format":     "json",
        "_marker":     "0",
        "api_version": "4",
        "ctx":         "web6dot0",
        "cc":          "in",
    }
    base_params.update(params)
    try:
        r = requests.get(API, params=base_params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


# ── Song parser ───────────────────────────────────────────────────────────────
def _parse_song(raw: dict, fetch_lyrics: bool = False) -> dict | None:
    """Parse a raw song dict into our clean response format."""
    if not isinstance(raw, dict):
        return None

    more    = raw.get("more_info") or {}
    title   = raw.get("title") or raw.get("song") or ""
    if not title:
        return None

    singers     = more.get("singers") or more.get("primary_artists") or raw.get("singers") or raw.get("primary_artists") or ""
    album       = more.get("album") or raw.get("album") or ""
    album_url   = more.get("album_url") or raw.get("album_url") or ""
    image       = more.get("image") or raw.get("image") or ""
    duration    = more.get("duration") or raw.get("duration") or "0"
    year        = more.get("release_date", "")[:4] if more.get("release_date") else (raw.get("year") or "")
    language    = more.get("language") or raw.get("language") or ""
    perma_url   = raw.get("perma_url") or more.get("perma_url") or ""
    song_id     = raw.get("id") or raw.get("songid") or ""
    lyrics_id   = more.get("lyrics_id") or ""

    media_url = _get_media_url({**raw, "more_info": more})

    lyrics = ""
    if fetch_lyrics and lyrics_id:
        lyrics = get_lyrics(lyrics_id)

    return {
        "title":      _clean(title),
        "song":       _clean(title),
        "singers":    _clean(singers),
        "album":      _clean(album),
        "album_url":  album_url,
        "image_url":  _best_image(image),
        "image":      _best_image(image),
        "url":        media_url,
        "duration":   str(duration),
        "year":       year,
        "language":   language,
        "perma_url":  perma_url,
        "songid":     song_id,
        "lyrics":     lyrics,
    }


def _clean(s: str) -> str:
    """Strip HTML tags."""
    return re.sub(r"<[^>]+>", "", str(s)).strip()


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def search(query: str, n: int = 10, fetch_lyrics: bool = False) -> list[dict]:
    """
    Search JioSaavn by song name or any text.
    Returns a list of parsed song dicts.
    """
    data = _call({
        "__call": "search.getResults",
        "p":      "1",
        "q":      query,
        "n":      str(n),
    })
    if not data:
        return []

    # Response is either a list directly or {"results": [...]}
    songs_raw = []
    if isinstance(data, list):
        songs_raw = data
    elif isinstance(data, dict):
        for key in ("results", "songs", "data"):
            if isinstance(data.get(key), list):
                songs_raw = data[key]
                break
        if not songs_raw and data.get("title"):
            songs_raw = [data]

    results = []
    for raw in songs_raw:
        parsed = _parse_song(raw, fetch_lyrics)
        if parsed:
            results.append(parsed)
    return results


def get_song(query: str, fetch_lyrics: bool = False) -> list[dict]:
    """
    Get song(s) by JioSaavn URL or plain text search.
    query can be: jiosaavn.com/song/... URL  OR  plain song name
    """
    if is_jiosaavn_url(query):
        token = _extract_token(query)
        data  = _call({"__call": "webapi.get", "token": token, "type": "song", "n": "1"})
        if data:
            songs_raw = data if isinstance(data, list) else [data]
            results   = [_parse_song(r, fetch_lyrics) for r in songs_raw]
            results   = [r for r in results if r]
            if results:
                return results
    # Fallback to search
    return search(query, n=5, fetch_lyrics=fetch_lyrics)


def get_album(query: str, fetch_lyrics: bool = False) -> list[dict]:
    """
    Get all songs in an album by JioSaavn URL or plain text search.
    query can be: jiosaavn.com/album/... URL  OR  plain album name
    """
    songs_raw = []

    if is_jiosaavn_url(query):
        token = _extract_token(query)
        data  = _call({"__call": "webapi.get", "token": token, "type": "album", "n": "500"})
        if data:
            songs_raw = _extract_songs_from_album(data)

    if not songs_raw:
        # Search for it
        results = search(query, n=20, fetch_lyrics=fetch_lyrics)
        # Group by album: return all songs that share the same album as the top result
        if results:
            top_album = results[0].get("album", "")
            if top_album:
                return [s for s in results if s.get("album","").lower() == top_album.lower()]
            return results[:1]

    parsed = [_parse_song(r, fetch_lyrics) for r in songs_raw]
    return [p for p in parsed if p]


def _extract_songs_from_album(data) -> list[dict]:
    """Extract raw song list from album API response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "songs", "tracks", "data"):
            val = data.get(key)
            if isinstance(val, list) and val:
                return val
        # Sometimes nested under more_info
        more = data.get("more_info") or {}
        for key in ("list", "songs"):
            val = more.get(key)
            if isinstance(val, list) and val:
                return val
    return []


def get_playlist(query: str, fetch_lyrics: bool = False) -> list[dict]:
    """
    Get all songs in a playlist by JioSaavn URL or plain text search.
    """
    songs_raw = []

    if is_jiosaavn_url(query):
        token = _extract_token(query)
        data  = _call({"__call": "webapi.get", "token": token, "type": "playlist", "n": "500"})
        if data:
            songs_raw = _extract_songs_from_album(data)

    if not songs_raw:
        return search(query, n=10, fetch_lyrics=fetch_lyrics)

    parsed = [_parse_song(r, fetch_lyrics) for r in songs_raw]
    return [p for p in parsed if p]


def get_lyrics(lyrics_id: str) -> str:
    """Fetch lyrics by lyrics_id."""
    if not lyrics_id:
        return ""
    data = _call({"__call": "lyrics.getLyrics", "lyrics_id": lyrics_id})
    if isinstance(data, dict):
        return _clean(data.get("lyrics", ""))
    return ""


def get_result(query: str, fetch_lyrics: bool = False) -> list[dict]:
    """
    Universal endpoint: works with any query or JioSaavn URL.
    Auto-detects type from URL, falls back to text search.
    """
    if is_jiosaavn_url(query):
        kind = _detect_type(query)
        if kind == "song":
            return get_song(query, fetch_lyrics)
        if kind == "album":
            return get_album(query, fetch_lyrics)
        if kind == "playlist":
            return get_playlist(query, fetch_lyrics)
    return search(query, n=10, fetch_lyrics=fetch_lyrics)
