"""
jiosaavn.py — JioSaavn API core (Python 3)

Exact same approach as cyberboysumanjay/JioSaavnAPI + album/artist text search.

Endpoints used:
  search.getResults  — search by name
  webapi.get         — fetch by token (song/album/playlist)
  lyrics.getLyrics   — fetch lyrics by id

DES decrypt:
  Uses pycryptodome (reliable on all platforms).
  Key: b"38346591", Mode: CBC, IV: 8 null bytes, PKCS5 padding.
  Decrypts encrypted_media_url → aac.saavncdn.com URL.
"""

import re
import base64
import requests
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad


# ── Constants ─────────────────────────────────────────────────────────────────
JIOSAAVN    = "https://www.jiosaavn.com"
API         = f"{JIOSAAVN}/api.php"
DES_KEY     = b"38346591"
DES_IV      = b"\x00" * 8

PARAMS      = {
    "_format":     "json",
    "_marker":     "0",
    "api_version": "4",
    "ctx":         "wap6dot0",
    "cc":          "in",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.jiosaavn.com/",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _clean(s):
    """Strip HTML tags and extra whitespace."""
    return re.sub(r"<[^>]+>", "", str(s or "")).strip()


def _img(url):
    """Upgrade image URL to 500×500."""
    if not url:
        return ""
    url = re.sub(r"-\d+x\d+\.(jpg|jpeg|png|webp)", r"-500x500.\1", str(url), flags=re.I)
    return url.replace("http://", "https://")


def _decrypt(enc_url: str) -> str:
    """
    Decrypt JioSaavn DES-encrypted media URL.
    Uses pycryptodome — reliable on all platforms.
    """
    if not enc_url or not isinstance(enc_url, str):
        return ""
    try:
        # Fix base64 padding if needed
        pad = len(enc_url) % 4
        if pad:
            enc_url += "=" * (4 - pad)
        enc_bytes = base64.b64decode(enc_url)
        cipher    = DES.new(DES_KEY, DES.MODE_CBC, DES_IV)
        dec_bytes = unpad(cipher.decrypt(enc_bytes), DES.block_size)
        url       = dec_bytes.decode("utf-8").strip()
        # Upgrade to 320 kbps
        for low in ("_96.mp4", "_160.mp4", "_48.mp4", "_96.mp3", "_160.mp3"):
            url = url.replace(low, "_320.mp4")
        return url.replace("http://", "https://")
    except Exception:
        return ""


def _is_url(text: str) -> bool:
    return "jiosaavn.com" in text.lower()


def _token(url: str) -> str:
    """Extract last path segment from JioSaavn URL."""
    return url.rstrip("/").split("/")[-1]


def _type(url: str) -> str:
    u = url.lower()
    if "/song/" in u:                        return "song"
    if "/album/" in u:                       return "album"
    if "/featured/" in u or "/s/playlist/" in u or "/playlist/" in u:
                                             return "playlist"
    if "/artist/" in u:                      return "artist"
    return "song"


# ── API call ──────────────────────────────────────────────────────────────────
def _call(extra: dict) -> dict | list | None:
    p = {**PARAMS, **extra}
    try:
        r = requests.get(API, params=p, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ── Song parser ───────────────────────────────────────────────────────────────
def _parse(raw: dict, lyrics: bool = False) -> dict | None:
    """
    Parse a raw JioSaavn song dict.
    Preserves ALL original fields + adds normalised fields on top.
    """
    if not isinstance(raw, dict):
        return None

    # Flatten more_info into top level
    more   = raw.get("more_info") or {}
    merged = {**more, **raw}
    merged.pop("more_info", None)

    title = merged.get("title") or merged.get("song") or ""
    if not title:
        return None

    # ── media_url ─────────────────────────────────────────────────────────────
    # Priority 1: direct media_url (present in wap6dot0 responses)
    media_url = merged.get("media_url") or ""
    if media_url and not media_url.startswith("http"):
        media_url = ""

    # Priority 2: decrypt encrypted_media_url
    if not media_url:
        enc = merged.get("encrypted_media_url") or ""
        if enc:
            media_url = _decrypt(enc)

    # Priority 3: upgrade preview URL
    preview = merged.get("media_preview_url") or ""
    if not media_url and preview and preview.startswith("http"):
        media_url = (preview
                     .replace("preview.saavncdn.com", "aac.saavncdn.com")
                     .replace("_96_p.mp4", "_320.mp4")
                     .replace("http://", "https://"))

    # Ensure preview URL
    if not preview and media_url and "aac.saavncdn.com" in media_url:
        preview = (media_url
                   .replace("aac.saavncdn.com", "preview.saavncdn.com")
                   .replace("_320.mp4", "_96_p.mp4"))

    # ── lyrics ────────────────────────────────────────────────────────────────
    lyr = merged.get("lyrics") or ""
    if lyrics and not lyr:
        lid = merged.get("lyrics_id") or ""
        if lid:
            lyr = get_lyrics(lid)

    # ── year ──────────────────────────────────────────────────────────────────
    year = str(merged.get("year") or "")
    rd   = merged.get("release_date") or ""
    if not year and rd:
        year = rd[:4]

    # singers
    singers = _clean(
        merged.get("singers") or merged.get("primary_artists") or
        merged.get("music") or ""
    )

    # Build result: all original fields + normalised overrides
    result = dict(merged)
    result.update({
        "title":             _clean(title),
        "song":              _clean(title),
        "singers":           singers,
        "primary_artists":   singers,
        "album":             _clean(merged.get("album") or ""),
        "album_url":         merged.get("album_url") or "",
        "image":             _img(merged.get("image") or merged.get("image_url") or ""),
        "image_url":         _img(merged.get("image") or merged.get("image_url") or ""),
        "media_url":         media_url,
        "url":               media_url,
        "media_preview_url": preview.replace("http://", "https://") if preview else "",
        "duration":          str(merged.get("duration") or "0"),
        "year":              year,
        "release_date":      rd,
        "language":          merged.get("language") or "",
        "perma_url":         merged.get("perma_url") or "",
        "has_lyrics":        merged.get("has_lyrics") or "false",
        "lyrics":            lyr,
        "320kbps":           merged.get("320kbps") or "true",
        "id":                merged.get("id") or merged.get("songid") or "",
    })
    return result


# ── Extract songs list from any API response ──────────────────────────────────
def _songs_from(data) -> list[dict]:
    """Extract raw song dicts from any JioSaavn API response shape."""
    if data is None:
        return []
    if isinstance(data, list):
        # List of songs directly
        if data and isinstance(data[0], dict) and (data[0].get("title") or data[0].get("song")):
            return data
        # List of {song: {...}} wrappers
        out = []
        for item in data:
            if isinstance(item, dict):
                s = item.get("song") if isinstance(item.get("song"), dict) else item
                out.append(s)
        return out
    if isinstance(data, dict):
        # {"songs": [...]} or {"list": [...]}
        for key in ("songs", "list", "results", "data", "tracks"):
            val = data.get(key)
            if isinstance(val, list) and val:
                return _songs_from(val)
        # Single song
        if data.get("title") or data.get("song"):
            return [data]
    return []


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def search(query: str, n: int = 10, lyrics: bool = False) -> list[dict]:
    """Search JioSaavn by plain text. Returns list of song dicts."""
    data = _call({"__call": "search.getResults", "q": query, "p": "1", "n": str(n)})
    raws = _songs_from(data)
    return [p for p in (_parse(r, lyrics) for r in raws) if p]


def get_song(query: str, lyrics: bool = False) -> list[dict]:
    """
    Fetch song by JioSaavn URL or plain text.
    query: jiosaavn.com/song/... URL  OR  song name
    """
    if _is_url(query):
        data = _call({"__call": "webapi.get", "token": _token(query), "type": "song", "n": "1"})
        songs = [p for p in (_parse(r, lyrics) for r in _songs_from(data)) if p]
        if songs:
            return songs
    return search(query, n=5, lyrics=lyrics)


def get_album(query: str, lyrics: bool = False) -> list[dict]:
    """
    Fetch all songs in album by JioSaavn URL or album name text.
    query: jiosaavn.com/album/... URL  OR  album name
    """
    if _is_url(query):
        data = _call({"__call": "webapi.get", "token": _token(query), "type": "album", "n": "500"})
        songs = [p for p in (_parse(r, lyrics) for r in _songs_from(data)) if p]
        if songs:
            return songs

    # Text search — find songs, group by top album match
    results = search(query, n=20, lyrics=lyrics)
    if not results:
        return []
    top_album = results[0].get("album", "").lower()
    if top_album:
        matched = [s for s in results if s.get("album", "").lower() == top_album]
        return matched if matched else results
    return results


def get_playlist(query: str, lyrics: bool = False) -> list[dict]:
    """
    Fetch all songs in playlist by JioSaavn URL or name text.
    query: jiosaavn.com/featured/... URL  OR  playlist name
    """
    if _is_url(query):
        data = _call({"__call": "webapi.get", "token": _token(query), "type": "playlist", "n": "500"})
        songs = [p for p in (_parse(r, lyrics) for r in _songs_from(data)) if p]
        if songs:
            return songs
    return search(query, n=10, lyrics=lyrics)


def get_result(query: str, lyrics: bool = False) -> list[dict]:
    """
    Universal endpoint — auto-detects type from URL, or does text search.
    Supports: song URL, album URL, playlist URL, or any plain text.
    """
    if _is_url(query):
        t = _type(query)
        if t == "song":     return get_song(query, lyrics)
        if t == "album":    return get_album(query, lyrics)
        if t == "playlist": return get_playlist(query, lyrics)
    return search(query, n=10, lyrics=lyrics)


def get_lyrics(query: str) -> str:
    """
    Fetch lyrics.
    query: lyrics_id string  OR  jiosaavn song URL
    """
    if _is_url(query):
        songs = get_song(query, lyrics=True)
        if songs:
            return songs[0].get("lyrics") or ""
        return ""
    # Direct lyrics_id
    data = _call({"__call": "lyrics.getLyrics", "lyrics_id": query})
    if isinstance(data, dict):
        return _clean(data.get("lyrics") or "")
    return ""
