#!/usr/bin/env python3
"""Check rendered files against Instagram limits before publishing.

Usage:  python3 agent/render/check_media.py FILE [FILE ...]

JPEG feed images: JPEG, <= 8 MB, aspect ratio 4:5 to 1.91:1
  (files whose name contains "story" may be 9:16).
MP4 reels: H.264, 3 s to 15 min, <= 20 MB (jsDelivr serves up to 20 MB).
Prints one JSON line per file; exits 1 if any file fails.
"""
import json
import pathlib
import subprocess
import sys

from PIL import Image


def check_jpeg(p: pathlib.Path):
    errs = []
    im = Image.open(p)
    if im.format != "JPEG":
        errs.append("not a JPEG")
    size = p.stat().st_size
    if size > 8 * 1024 * 1024:
        errs.append("over 8 MB")
    w, h = im.size
    ratio = w / h
    if "story" not in p.name and not (0.8 - 1e-3 <= ratio <= 1.91 + 1e-3):
        errs.append(f"aspect ratio {ratio:.3f} outside 4:5..1.91:1")
    return errs, {"width": w, "height": h, "bytes": size}


def check_mp4(p: pathlib.Path):
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height", "-of", "json", str(p)],
        capture_output=True, text=True,
    )
    info = json.loads(res.stdout or "{}")
    errs = []
    dur = float(info.get("format", {}).get("duration", 0))
    if not 3 <= dur <= 900:
        errs.append(f"duration {dur:.1f}s outside 3s..15min")
    size = p.stat().st_size
    if size > 20 * 1024 * 1024:
        errs.append("over 20 MB")
    video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not video or video[0].get("codec_name") != "h264":
        errs.append("video codec is not H.264")
    meta = {"seconds": round(dur, 2), "bytes": size}
    if video:
        meta.update(width=video[0].get("width"), height=video[0].get("height"))
    return errs, meta


def main():
    files = [pathlib.Path(a) for a in sys.argv[1:]]
    if not files:
        sys.exit(__doc__)
    ok = True
    for f in files:
        if not f.exists():
            errs, meta = ["file not found"], {}
        elif f.suffix.lower() in (".jpg", ".jpeg"):
            errs, meta = check_jpeg(f)
        elif f.suffix.lower() in (".mp4", ".mov"):
            errs, meta = check_mp4(f)
        else:
            errs, meta = ["unsupported type (use .jpg or .mp4)"], {}
        ok &= not errs
        print(json.dumps({"file": str(f), "ok": not errs, "errors": errs, **meta}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
