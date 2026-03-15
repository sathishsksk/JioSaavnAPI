""" 
jiosaavn.py
Unofficial JioSaavn API — exact same approach as cyberboysumanjay/JioSaavnAPI
+ album text search (album/?query=bigil)

Key facts confirmed from anxkhn/jiosaavn-api (working modern fork):
  - Uses pyDes for DES CBC decrypt of encrypted_media_url
  - Key: b"38346591", IV: 8 null bytes, PAD_PKCS5
  - ctx=wap6dot0 returns media_url + media_preview_url directly
  - Raw response is passed through with only media_url + image upgraded
"""

import re
import base64
import requests
from pyDes import des, CBC, PAD_PKCS5


# ─── Config ───────────────────────────────────────────────────────────────────
API = "https://www.jiosaavn.com/api.php"

BASE = {
    "_format":     "json",
    "_marker":     "0",
    "api_version": "4",
    "ctx":         "wap6dot0",
    "cc":          "in",
}

HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; SM-G991B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.jiosaavn.com/",
}


# ─── Decrypt ──────────────────────────────────────────────────────────────────
_DES = des(b"38346591", CBC, b"\x00\x00\x00\x00\x00\x00\x00\x00",
           pad=None, padmode=PAD_PKCS5)


def decrypt_url(enc: str) -> str:
    """Decrypt JioSaavn DES-encrypted media URL → direct CDN URL."""
    if not enc or not isinstance(enc, str):
        return ""
    try:
        # Fix base64 padding
        r = len(enc) % 4
        if r:
            enc += "=" * (4 - r)
        raw = base64.b64decode(enc)
        url = _DES.decrypt(raw, padmode=PAD_PKCS5).decode("utf-8")
        # Upgrade to 320 kbps
        for low in ("_96.mp4", "_160.mp4", "_48.mp4"):
            url = url.replace(low, "_320.mp4")
        return url.replace("http://", "https://")
    except Exception:
        return ""


def upgrade_image(url: str) -> str:
    if not url:
        return ""
    url = re.sub(r"-\d+x\d+\.(jpg|jpeg|png|webp)", r"-500x500.\1", url, flags=re.I)
    return url.replace("http://", "https://")


def clean(s) -> str:
    return re.sub(r"<[^>]+>", "", str(s or "")).strip()


# ─── API call ─────────────────────────────────────────────────────────────────
def _call(extra: dict):
    try:
        r = requests.get(API, params={**BASE, **extra}, headers=HDR, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ─── Build one song dict (pass through raw + add media_url / image) ───────────
def _build(raw: dict, get_lyrics: bool = False) -> dict | None:
    if not isinstance(raw, dict):
        return None

    # Flatten more_info
    more   = raw.get("more_info") or {}
    song   = {**more, **raw}
    song.pop("more_info", None)

    if not (song.get("title") or song.get("song")):
        return None

    # ── media_url ─────────────────────────────────────────────────────────────
    # wap6dot0 returns media_url directly for most songs.
    # If empty, decrypt encrypted_media_url.
    media_url = song.get("media_url") or ""
    if not (media_url and media_url.startswith("http")):
        enc = song.get("encrypted_media_url") or ""
        media_url = decrypt_url(enc) if enc else ""

    # ── media_preview_url ─────────────────────────────────────────────────────
    preview = song.get("media_preview_url") or ""
    if preview:
        preview = preview.replace("http://", "https://")
    elif media_url and "aac.saavncdn.com" in media_url:
        # Reconstruct preview from 320 URL
        preview = (media_url
                   .replace("aac.saavncdn.com", "preview.saavncdn.com")
                   .replace("_320.mp4", "_96_p.mp4"))

    # ── lyrics ────────────────────────────────────────────────────────────────
    lyr = song.get("lyrics") or ""
    if get_lyrics and not lyr:
        lid = song.get("lyrics_id") or ""
        if lid:
            lyr = fetch_lyrics(lid)

    # ── image ─────────────────────────────────────────────────────────────────
    img = upgrade_image(song.get("image") or song.get("image_url") or "")

    # ── year from release_date ────────────────────────────────────────────────
    year = str(song.get("year") or "")
    rd   = song.get("release_date") or ""
    if not year and rd:
        year = rd[:4]

    # Return everything — all original fields + overrides
    out = dict(song)
    out.update({
        "title":             clean(song.get("title") or song.get("song") or ""),
        "song":              clean(song.get("title") or song.get("song") or ""),
        "singers":           clean(song.get("singers") or song.get("primary_artists") or song.get("music") or ""),
        "primary_artists":   clean(song.get("primary_artists") or song.get("singers") or ""),
        "album":             clean(song.get("album") or ""),
        "album_url":         song.get("album_url") or "",
        "image":             img,
        "image_url":         img,
        "media_url":         media_url,
        "url":               media_url,
        "media_preview_url": preview,
        "duration":          str(song.get("duration") or "0"),
        "year":              year,
        "release_date":      rd,
        "language":          song.get("language") or "",
        "perma_url":         song.get("perma_url") or "",
        "has_lyrics":        song.get("has_lyrics") or "false",
        "lyrics":            lyr,
        "320kbps":           song.get("320kbps") or "true",
        "id":                song.get("id") or song.get("songid") or "",
    })
    return out


def _songs(data) -> list[dict]:
    """Extract raw song dicts from any JioSaavn response shape."""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("list", "songs", "results", "data"):
            v = data.get(k)
            if isinstance(v, list) and v:
                return v
        if data.get("title") or data.get("song"):
            return [data]
    return []


def _parse_all(data, get_lyrics=False) -> list[dict]:
    return [b for b in (_build(r, get_lyrics) for r in _songs(data)) if b]


# ─── URL helpers ──────────────────────────────────────────────────────────────
def _is_url(s: str) -> bool:
    return "jiosaavn.com" in s.lower()


def _token(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _kind(url: str) -> str:
    u = url.lower()
    if "/song/"    in u: return "song"
    if "/album/"   in u: return "album"
    if "/featured/" in u or "/s/playlist/" in u or "/playlist/" in u: return "playlist"
    return "song"


# ─── Public functions ─────────────────────────────────────────────────────────
def search(query: str, n: int = 10, get_lyrics: bool = False) -> list[dict]:
    """Search by song name or any text."""
    data = _call({"__call": "search.getResults", "q": query, "p": "1", "n": str(n)})
    return _parse_all(data, get_lyrics)


def get_song(query: str, get_lyrics: bool = False) -> list[dict]:
    """Fetch by JioSaavn song URL or plain text search."""
    if _is_url(query):
        data = _call({"__call": "webapi.get", "token": _token(query), "type": "song", "n": "1"})
        res  = _parse_all(data, get_lyrics)
        if res:
            return res
    return search(query, n=5, get_lyrics=get_lyrics)


def get_album(query: str, get_lyrics: bool = False) -> list[dict]:
    """
    Fetch album songs by JioSaavn URL  OR  plain album name.
    e.g. /album/?query=bigil  OR  /album/?query=https://jiosaavn.com/album/bigil/...
    """
    if _is_url(query):
        data = _call({"__call": "webapi.get", "token": _token(query), "type": "album", "n": "500"})
        res  = _parse_all(data, get_lyrics)
        if res:
            return res

    # Text search — fetch songs, group by top album
    results = search(query, n=20, get_lyrics=get_lyrics)
    if not results:
        return []
    top = results[0].get("album", "").lower()
    if top:
        matched = [s for s in results if s.get("album", "").lower() == top]
        return matched or results
    return results


def get_playlist(query: str, get_lyrics: bool = False) -> list[dict]:
    """Fetch playlist songs by JioSaavn URL or text search."""
    if _is_url(query):
        data = _call({"__call": "webapi.get", "token": _token(query), "type": "playlist", "n": "500"})
        res  = _parse_all(data, get_lyrics)
        if res:
            return res
    return search(query, n=10, get_lyrics=get_lyrics)


def get_result(query: str, get_lyrics: bool = False) -> list[dict]:
    """Universal — auto-detect type from URL, or text search."""
    if _is_url(query):
        k = _kind(query)
        if k == "song":     return get_song(query, get_lyrics)
        if k == "album":    return get_album(query, get_lyrics)
        if k == "playlist": return get_playlist(query, get_lyrics)
    return search(query, n=10, get_lyrics=get_lyrics)


def fetch_lyrics(query: str) -> str:
    """Fetch lyrics by lyrics_id or song URL."""
    if _is_url(query):
        songs = get_song(query, get_lyrics=True)
        return songs[0].get("lyrics", "") if songs else ""
    data = _call({"__call": "lyrics.getLyrics", "lyrics_id": query})
    if isinstance(data, dict):
        return clean(data.get("lyrics") or "")
    return ""
