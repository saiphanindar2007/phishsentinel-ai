"""
PhishSentinel AI — Placeholder Reference Logo Generator
--------------------------------------------------------
IMPORTANT — same caveat as the bootstrap URL dataset: this generates
SYNTHETIC placeholder images (solid color blocks + brand-name text), not
real screenshots of real login pages. It exists purely so you can prove
the pHash comparison pipeline (`visual_detector.py`) works end-to-end —
load reference images, hash them, compare a "clone" against them, get a
plausible score — before you've captured real screenshots.

Do NOT leave these in for your final submission/demo — a synthetic block
of color will not meaningfully detect a real cloned login page. Replace
them with real screenshots before Phase 3 is actually done (see the
step-by-step in the README / the chat guide for how to capture those).

Usage:
    python training/generate_placeholder_reference_logos.py

Writes to app/models/reference_logos/<brand>.png for a handful of demo
brands. Re-run any time to regenerate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow isn't installed. Run: pip install Pillow")
    sys.exit(1)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "models", "reference_logos")

# (brand, background color, accent color) — distinct colors so pHash
# distances between different "brands" are meaningfully large, proving
# the comparison logic actually discriminates between them.
DEMO_BRANDS = [
    ("paypal", (0, 48, 135), (255, 255, 255)),
    ("sbi", (0, 107, 63), (255, 255, 255)),
    ("icicibank", (242, 101, 34), (255, 255, 255)),
    ("google", (66, 133, 244), (255, 255, 255)),
    ("amazon", (35, 47, 62), (255, 153, 0)),
]


def make_placeholder(brand: str, bg, accent, size=(320, 240)):
    img = Image.new("RGB", size, color=bg)
    draw = ImageDraw.Draw(img)
    # A simple "login card" layout: header bar + two input-like rectangles
    # + a button-like rectangle — enough visual structure that pHash
    # (which looks at overall luminance/gradient patterns, not text) has
    # something non-trivial to hash, closer to a real page's layout than
    # a flat color block.
    draw.rectangle([0, 0, size[0], 40], fill=accent)
    draw.text((10, 10), brand.upper(), fill=bg)
    draw.rectangle([40, 80, size[0] - 40, 110], outline=accent, width=2)
    draw.rectangle([40, 130, size[0] - 40, 160], outline=accent, width=2)
    draw.rectangle([40, 180, size[0] - 40, 210], fill=accent)
    draw.text((size[0] // 2 - 20, 188), "LOGIN", fill=bg)
    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for brand, bg, accent in DEMO_BRANDS:
        path = os.path.join(OUT_DIR, f"{brand}.png")
        make_placeholder(brand, bg, accent).save(path)
        print(f"Wrote {path}")
    print(f"\n{len(DEMO_BRANDS)} placeholder reference images written to {OUT_DIR}")
    print("These are SYNTHETIC placeholders for pipeline testing only.")
    print("Replace with real login-page screenshots before your final submission —")
    print("see training/README.md section 3 for how to capture those.")


if __name__ == "__main__":
    main()
