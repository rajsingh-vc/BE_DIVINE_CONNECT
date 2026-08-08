"""Tiny helper used only by the Live Darshan status endpoint to turn a
YouTube URL (any of the shapes below) into a bare video ID, so we can
build a https://www.youtube.com/embed/<id> URL for the player.

Supported input shapes:
    https://www.youtube.com/live/VIDEO_ID
    https://www.youtube.com/live/VIDEO_ID?si=...
    https://www.youtube.com/watch?v=VIDEO_ID
    https://youtu.be/VIDEO_ID
"""
import re

_PATTERNS = [
    re.compile(r"youtube\.com/live/([A-Za-z0-9_-]+)"),
    re.compile(r"youtube\.com/watch\?.*[?&]?v=([A-Za-z0-9_-]+)"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]+)"),
]


def extract_youtube_id(url: str) -> str | None:
    if not url:
        return None
    for pattern in _PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None