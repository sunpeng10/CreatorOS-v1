"""Canonical types for validated uploads, independent of the Windows registry."""
from pathlib import PurePath

MEDIA_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp',
               '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.txt': 'text/plain', '.md': 'text/markdown',
               '.srt': 'text/plain', '.vtt': 'text/vtt'}


def asset_mime(name, fallback='application/octet-stream'):
    return MEDIA_TYPES.get(PurePath(str(name)).suffix.lower(), fallback)
