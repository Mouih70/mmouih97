#!/usr/bin/env python3
"""Render a short vertical reel (1080x1920 MP4, 30 fps) from a JSON spec.

Usage:  python3 agent/render/reel.py spec.json OUT_DIR

Spec:
{
  "tag": "ترند اليوم",                       (optional, shown on every scene)
  "scenes": [
    {"text": "...", "style": "orange", "seconds": 2.8, "photo": null},
    {"text": "...", "style": "cream"},
    {"text": "...", "style": "green"}
  ],
  "cta": {"title": "...", "points": ["..."], "seconds": 3.0}
}
style: orange | green | cream (rotates when missing). seconds: 1.5 to 6.
Optional: "audio": false for a silent reel; "seed": int to pick another beat.
Writes reel.mp4 and cover.jpg into OUT_DIR. The soundtrack (beat, whoosh,
pop, ding) is synthesized by sound.py, so it is original audio.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import zlib

from PIL import Image

from common import THEME, esc, file_url, font_css, load_config, png_to_jpeg, render_pages, resolve_photo

W, H, FPS = 1080, 1920, 30
FADE = 6          # crossfade frames between scenes
ZOOM = 0.045      # slow zoom-in over each scene
T = THEME
CFG = load_config()

STYLES = {
    "orange": (T["orange"], "#FFFFFF", "rgba(255,255,255,.22)", T["green_dark"]),
    "green": (T["green"], "#FFFFFF", "rgba(255,255,255,.16)", T["orange"]),
    "cream": (T["bg"], T["ink"], "rgba(0,0,0,.07)", T["orange"]),
}
ROTATION = ["orange", "cream", "green"]

CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;overflow:hidden}}
body{{font-family:'Cairo',sans-serif;-webkit-font-smoothing:antialiased}}
.f{{width:{W}px;height:{H}px;position:relative;display:flex;flex-direction:column;align-items:center}}
.head{{position:absolute;top:210px;left:0;right:0;display:flex;justify-content:center;gap:22px;align-items:center}}
.tag{{font-weight:900;font-size:44px;border-radius:999px;padding:8px 36px}}
.brand{{font-weight:900;font-size:40px;unicode-bidi:plaintext}}
.box{{position:absolute;top:380px;left:90px;right:150px;bottom:560px;display:flex;flex-direction:column;
      justify-content:center;align-items:center;gap:calc(var(--k)*40px);overflow:hidden;text-align:center}}
.txt{{font-weight:900;line-height:1.3;unicode-bidi:plaintext}}
.card{{background:#fff;border-radius:40px;padding:18px;box-shadow:0 18px 50px rgba(0,0,0,.18);
       display:flex;align-items:center;justify-content:center;overflow:hidden}}
.card img{{max-width:100%;max-height:100%;object-fit:contain;border-radius:28px;display:block}}
.handle{{position:absolute;top:1400px;left:0;right:0;text-align:center;font-weight:800;font-size:40px;direction:ltr;opacity:.85}}
ul{{list-style:none;display:flex;flex-direction:column;gap:calc(var(--k)*26px);align-items:stretch}}
li{{display:flex;gap:24px;align-items:flex-start;font-weight:800;line-height:1.45;text-align:right;unicode-bidi:plaintext}}
.check{{flex:none;width:calc(var(--k)*48px);height:calc(var(--k)*48px);border-radius:50%;position:relative;margin-top:calc(var(--k)*14px)}}
.check:after{{content:'';position:absolute;left:28%;top:22%;width:30%;height:45%;border-right:calc(var(--k)*7px) solid #fff;
              border-bottom:calc(var(--k)*7px) solid #fff;transform:rotate(45deg)}}
"""


def page(body: str) -> str:
    return (
        "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
        f"<style>{font_css()}\n{CSS}</style></head><body>{body}</body></html>"
    )


def head(tag, fg, chip, accent) -> str:
    tag_html = f"<div class='tag' style='background:{accent};color:#fff'>{esc(tag)}</div>" if tag else ""
    return f"<div class='head'>{tag_html}<div class='brand' style='color:{fg}'>{esc(CFG['brand'])}</div></div>"


def scene_html(scene, style_name, tag) -> str:
    bg, fg, chip, accent = STYLES[style_name]
    photo = resolve_photo(scene.get("photo"))
    text_px = 84 if photo else 104
    card = (
        f"<div class='card' style='height:calc(var(--k)*560px);max-width:100%'><img src='{file_url(photo)}'></div>"
        if photo else ""
    )
    body = f"""
<div class='f' style='background:{bg};color:{fg}'>
  {head(tag, fg, chip, accent)}
  <div class='box' data-fit-root>
    <div class='txt' style='font-size:calc(var(--k)*{text_px}px)'>{esc(scene.get('text'))}</div>
    {card}
  </div>
  <div class='handle' style='color:{fg}'>{esc(CFG['handle'])}</div>
</div>"""
    return page(body)


def cta_html(cta, tag) -> str:
    bg, fg, chip, accent = STYLES["green"]
    pts = "".join(
        f"<li style='font-size:calc(var(--k)*54px)'><span class='check' style='background:{T['orange']}'></span><span>{esc(p)}</span></li>"
        for p in (cta.get("points") or [])
    )
    body = f"""
<div class='f' style='background:{bg};color:{fg}'>
  {head(tag, fg, chip, accent)}
  <div class='box' data-fit-root>
    <div class='txt' style='font-size:calc(var(--k)*100px)'>{esc(cta.get('title'))}</div>
    <ul>{pts}</ul>
  </div>
  <div class='handle' style='color:{fg}'>{esc(CFG['handle'])}</div>
</div>"""
    return page(body)


def zoom_frame(img: Image.Image, z: float) -> Image.Image:
    """Crop the centre by factor z (>=1) and scale back to full size (sub-pixel smooth)."""
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    scenes = spec.get("scenes") or []
    if not 1 <= len(scenes) <= 8:
        sys.exit("A reel needs 1 to 8 scenes.")
    tag = spec.get("tag")

    with tempfile.TemporaryDirectory() as tmp:
        jobs, durations = [], []
        for i, sc in enumerate(scenes):
            style = sc.get("style") or ROTATION[i % len(ROTATION)]
            if style not in STYLES:
                sys.exit(f"Unknown style: {style}")
            secs = float(sc.get("seconds", 2.8))
            if not 1.5 <= secs <= 6:
                sys.exit("Scene seconds must be between 1.5 and 6.")
            jobs.append({"html": scene_html(sc, style, tag), "width": W, "height": H,
                         "out": pathlib.Path(tmp) / f"sc{i:02d}.png"})
            durations.append(secs)
        if spec.get("cta"):
            secs = float(spec["cta"].get("seconds", 3.0))
            jobs.append({"html": cta_html(spec["cta"], tag), "width": W, "height": H,
                         "out": pathlib.Path(tmp) / "cta.png"})
            durations.append(secs)
        render_pages(jobs)
        frames = [Image.open(j["out"]).convert("RGB") for j in jobs]

        # Soundtrack: our own synthesized beat + whoosh/pop/ding effects.
        if spec.get("audio", True):
            from sound import make_soundtrack

            seed = spec.get("seed")
            if seed is None:
                seed = zlib.crc32("|".join(s.get("text", "") for s in scenes).encode("utf-8"))
            wav = pathlib.Path(tmp) / "sound.wav"
            make_soundtrack(durations, wav, seed=seed,
                            cta_index=len(scenes) if spec.get("cta") else None)
            audio_in = ["-i", str(wav)]
            audio_filter = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100"]
        else:
            audio_in = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
            audio_filter = []

        mp4 = out / "reel.mp4"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            *audio_in, "-map", "0:v", "-map", "1:a", *audio_filter,
            "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(mp4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        prev_last = None
        for idx, (img, secs) in enumerate(zip(frames, durations)):
            n = max(1, round(secs * FPS))
            for f in range(n):
                fr = zoom_frame(img, 1.0 + ZOOM * f / n)
                if prev_last is not None and f < FADE:
                    fr = Image.blend(prev_last, fr, (f + 1) / (FADE + 1))
                proc.stdin.write(fr.tobytes())
                if f == n - 1:
                    prev_last = fr
        proc.stdin.close()
        if proc.wait() != 0:
            sys.exit("ffmpeg failed")
        png_to_jpeg(jobs[0]["out"], out / "cover.jpg")
    print(json.dumps({"video": str(mp4), "cover": str(out / "cover.jpg"),
                      "seconds": round(sum(durations), 2)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
