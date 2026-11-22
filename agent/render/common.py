"""Shared helpers for the MarketMall Instagram renderer.

HTML pages are rendered with Playwright (Chromium), which shapes Arabic text
correctly. Fonts are embedded as base64 so no network access is needed.
"""
import base64
import pathlib
import tempfile

from PIL import Image

RENDER_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = RENDER_DIR.parent.parent
FONTS_DIR = RENDER_DIR / "fonts"

# Brand theme (papaya orange, deep green, warm cream).
THEME = {
    "bg": "#FFF6EC",
    "orange": "#F07D1A",
    "orange_dark": "#C95F07",
    "green": "#1E5B45",
    "green_dark": "#123B2C",
    "ink": "#1D1D1D",
    "muted": "#6B5E52",
    "white": "#FFFFFF",
}

ARABIC_RANGE = (
    "U+0600-06FF, U+0750-077F, U+0870-088E, U+0890-0891, U+0898-08E1, "
    "U+08E3-08FF, U+200C-200E, U+2010-2011, U+204F, U+2E41, U+FB50-FDFF, "
    "U+FE70-FE74, U+FE76-FEFC"
)
LATIN_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, "
    "U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2212, U+2215, "
    "U+FEFF, U+FFFD"
)


CONFIG_PATH = REPO_ROOT / "agent" / "config.json"
DEFAULT_CONFIG = {"brand": "MarketMall", "handle": "@marketmall002"}


def load_config() -> dict:
    """Page name and @handle shown on every visual (agent/config.json)."""
    import json

    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return cfg


def _b64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def font_css() -> str:
    """@font-face rules for Cairo 600/800/900, Arabic and Latin subsets."""
    rules = []
    for weight in (600, 800, 900):
        for subset, rng in (("arabic", ARABIC_RANGE), ("latin", LATIN_RANGE)):
            f = FONTS_DIR / f"cairo-{subset}-{weight}-normal.woff2"
            rules.append(
                "@font-face{font-family:'Cairo';font-style:normal;"
                f"font-weight:{weight};font-display:block;"
                f"src:url(data:font/woff2;base64,{_b64(f)}) format('woff2');"
                f"unicode-range:{rng};}}"
            )
    return "\n".join(rules)


def resolve_photo(p):
    """Return an absolute path for a photo given relative to the repo root."""
    if not p:
        return None
    path = pathlib.Path(p)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Photo not found: {path}")
    return path


def file_url(path) -> str:
    return pathlib.Path(path).resolve().as_uri()


# Shrinks every element under [data-fit-root] (via the --k CSS variable)
# until nothing overflows its box. Font sizes must use calc(var(--k)*Npx).
FIT_JS = """
() => {
  const roots = document.querySelectorAll('[data-fit-root]');
  for (const root of roots) {
    let k = 1.0;
    root.style.setProperty('--k', k);
    let guard = 0;
    while (root.scrollHeight > root.clientHeight + 1 && k > 0.45 && guard < 60) {
      k -= 0.03; guard++;
      root.style.setProperty('--k', k.toFixed(3));
    }
  }
  return true;
}
"""


def render_pages(jobs):
    """Render HTML strings to PNG files.

    jobs: list of dicts {html, width, height, out, transparent}
    """
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for i, job in enumerate(jobs):
                page = browser.new_page(
                    viewport={"width": job["width"], "height": job["height"]},
                    device_scale_factor=1,
                )
                html_path = pathlib.Path(tmp) / f"page_{i}.html"
                html_path.write_text(job["html"], encoding="utf-8")
                page.goto(html_path.as_uri())
                page.evaluate("document.fonts.ready.then(() => true)")
                page.wait_for_load_state("networkidle")
                page.evaluate(FIT_JS)
                page.screenshot(
                    path=str(job["out"]),
                    omit_background=bool(job.get("transparent")),
                    full_page=False,
                )
                page.close()
        finally:
            browser.close()


def png_to_jpeg(png_path, jpg_path, quality=90):
    img = Image.open(png_path).convert("RGB")
    img.save(jpg_path, "JPEG", quality=quality, optimize=True, progressive=True)
    return jpg_path


def esc(text) -> str:
    import html

    return html.escape(str(text or ""), quote=True)
