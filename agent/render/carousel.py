#!/usr/bin/env python3
"""Render an Instagram carousel (1080x1350 JPEG slides) from a JSON spec.

Usage:  python3 agent/render/carousel.py spec.json OUT_DIR

Spec:
{
  "slides": [
    {"kind": "cover",   "tag": "ترند اليوم", "title": "...", "subtitle": "...", "photo": null},
    {"kind": "content", "title": "...", "points": ["...", "..."], "source": "المصدر: ...", "photo": null},
    {"kind": "cta",     "title": "...", "points": ["...", "..."], "footer": "..."}
  ]
}
2 to 10 slides. "tag", "subtitle", "source" and "photo" are optional.
Photos are paths relative to the repo root. Page name and @handle come
from agent/config.json.
Writes slide-01.jpg, slide-02.jpg, ... into OUT_DIR.
"""
import json
import pathlib
import sys
import tempfile

from common import THEME, esc, file_url, font_css, load_config, png_to_jpeg, render_pages, resolve_photo

W, H = 1080, 1350
T = THEME
CFG = load_config()

BASE_CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;overflow:hidden}}
body{{font-family:'Cairo',sans-serif;background:{T['bg']};color:{T['ink']};
     -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}
.slide{{width:{W}px;height:{H}px;padding:64px 76px 56px;display:flex;flex-direction:column;position:relative}}
.top{{display:flex;justify-content:space-between;align-items:center;height:64px}}
.brand{{font-weight:900;font-size:40px;letter-spacing:.5px;color:{T['orange']};unicode-bidi:plaintext}}
.tag{{align-self:flex-start;background:{T['orange']};color:#fff;font-weight:900;border-radius:999px;
      padding:calc(var(--k)*8px) calc(var(--k)*30px);font-size:calc(var(--k)*38px)}}
.src{{font-weight:600;color:{T['muted']};font-size:calc(var(--k)*30px);unicode-bidi:plaintext;
      border-top:3px solid rgba(0,0,0,.08);padding-top:calc(var(--k)*16px)}}
.count{{font-weight:800;font-size:30px;color:{T['muted']};direction:ltr;
        background:#fff;border-radius:999px;padding:4px 22px;box-shadow:0 2px 10px rgba(0,0,0,.06)}}
.main{{flex:1;overflow:hidden;display:flex;flex-direction:column;justify-content:center;gap:calc(var(--k)*34px);padding:24px 0}}
.bottom{{height:60px;display:flex;justify-content:space-between;align-items:center;
         font-weight:800;font-size:28px;color:{T['muted']}}}
.site{{direction:ltr}}
.title{{font-weight:900;line-height:1.28;unicode-bidi:plaintext}}
.sub{{font-weight:600;line-height:1.5;color:{T['muted']};unicode-bidi:plaintext}}
.bar{{width:120px;height:12px;border-radius:12px;background:{T['orange']}}}
.card{{background:#fff;border-radius:40px;box-shadow:0 18px 50px rgba(30,91,69,.14);
       padding:22px;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.card img{{max-width:100%;max-height:100%;object-fit:contain;border-radius:26px;display:block}}
ul{{list-style:none;display:flex;flex-direction:column;gap:calc(var(--k)*26px)}}
li{{display:flex;gap:26px;align-items:flex-start;font-weight:600;line-height:1.5;unicode-bidi:plaintext}}
.dot{{flex:none;width:calc(var(--k)*26px);height:calc(var(--k)*26px);border-radius:50%;
      background:{T['orange']};margin-top:calc(var(--k)*22px)}}
.swipe{{display:flex;align-items:center;gap:14px;color:{T['green']};font-weight:900;font-size:34px}}
.chev{{width:22px;height:22px;border-left:6px solid {T['green']};border-bottom:6px solid {T['green']};transform:rotate(45deg)}}
.cta{{background:{T['green']};color:#fff}}
.cta .count{{background:rgba(255,255,255,.14);color:#fff;box-shadow:none}}
.cta .brand{{color:#fff}} .cta .bottom{{color:rgba(255,255,255,.75)}}
.check{{flex:none;width:calc(var(--k)*46px);height:calc(var(--k)*46px);border-radius:50%;background:{T['orange']};
        position:relative;margin-top:calc(var(--k)*16px)}}
.check:after{{content:'';position:absolute;left:28%;top:22%;width:30%;height:45%;
              border-right:calc(var(--k)*7px) solid #fff;border-bottom:calc(var(--k)*7px) solid #fff;transform:rotate(45deg)}}
.pill{{align-self:flex-start;background:{T['orange']};color:#fff;font-weight:900;border-radius:999px;
       padding:calc(var(--k)*14px) calc(var(--k)*46px);box-shadow:0 10px 30px rgba(0,0,0,.18)}}
"""


def page(body: str) -> str:
    return (
        "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
        f"<style>{font_css()}\n{BASE_CSS}</style></head><body>{body}</body></html>"
    )


def top(idx: int, total: int) -> str:
    return (
        f"<div class='top'><div class='brand'>{esc(CFG['brand'])}</div>"
        f"<div class='count'>{idx}/{total}</div></div>"
    )


def bottom(left: str = "<div></div>") -> str:
    return f"<div class='bottom'>{left}<div class='site'>{esc(CFG['handle'])}</div></div>"


def photo_card(photo, max_h: int) -> str:
    path = resolve_photo(photo)
    if not path:
        return ""
    return (
        f"<div class='card' style='height:calc(var(--k)*{max_h}px)'>"
        f"<img src='{file_url(path)}'></div>"
    )


def cover(s, idx, total):
    sub = f"<div class='sub' style='font-size:calc(var(--k)*52px)'>{esc(s.get('subtitle'))}</div>" if s.get("subtitle") else ""
    has_photo = bool(s.get("photo"))
    title_px = 92 if has_photo else 118
    tag = f"<div class='tag'>{esc(s.get('tag'))}</div>" if s.get("tag") else "<div class='bar'></div>"
    body = f"""
<div class='slide'>{top(idx, total)}
  <div class='main' data-fit-root>
    {tag}
    <div class='title' style='font-size:calc(var(--k)*{title_px}px)'>{esc(s.get('title'))}</div>
    {sub}
    {photo_card(s.get('photo'), 600) if has_photo else ''}
  </div>
  {bottom("<div class='swipe'>سوايبي <span class='chev'></span></div>")}
</div>"""
    return page(body)


def content(s, idx, total):
    pts = "".join(
        f"<li style='font-size:calc(var(--k)*56px)'><span class='dot'></span><span>{esc(p)}</span></li>"
        for p in (s.get("points") or [])
    )
    has_photo = bool(s.get("photo"))
    src = f"<div class='src'>{esc(s.get('source'))}</div>" if s.get("source") else ""
    body = f"""
<div class='slide'>{top(idx, total)}
  <div class='main' data-fit-root>
    <div class='title' style='font-size:calc(var(--k)*84px);color:{T['green']}'>{esc(s.get('title'))}</div>
    <ul>{pts}</ul>
    {photo_card(s.get('photo'), 460) if has_photo else ''}
    {src}
  </div>
  {bottom()}
</div>"""
    return page(body)


def cta(s, idx, total):
    pts = "".join(
        f"<li style='font-size:calc(var(--k)*58px)'><span class='check'></span><span>{esc(p)}</span></li>"
        for p in (s.get("points") or [])
    )
    footer = f"<div class='pill' style='font-size:calc(var(--k)*52px)'>{esc(s.get('footer'))}</div>" if s.get("footer") else ""
    body = f"""
<div class='slide cta'>{top(idx, total)}
  <div class='main' data-fit-root>
    <div class='title' style='font-size:calc(var(--k)*104px)'>{esc(s.get('title'))}</div>
    <ul>{pts}</ul>
    {footer}
  </div>
  {bottom()}
</div>"""
    return page(body)


BUILDERS = {"cover": cover, "content": content, "cta": cta}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    slides = spec.get("slides") or []
    if not 2 <= len(slides) <= 10:
        sys.exit("A carousel needs 2 to 10 slides.")
    for s in slides:
        if s.get("kind") not in BUILDERS:
            sys.exit(f"Unknown slide kind: {s.get('kind')}")
    total = len(slides)
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        for i, s in enumerate(slides, 1):
            png = pathlib.Path(tmp) / f"s{i:02d}.png"
            jobs.append({"html": BUILDERS[s["kind"]](s, i, total), "width": W, "height": H, "out": png})
        render_pages(jobs)
        files = []
        for i, job in enumerate(jobs, 1):
            jpg = out / f"slide-{i:02d}.jpg"
            png_to_jpeg(job["out"], jpg)
            files.append(str(jpg))
    print(json.dumps({"slides": files}, ensure_ascii=False))


if __name__ == "__main__":
    main()
