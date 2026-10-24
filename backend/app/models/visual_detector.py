"""
PhishSentinel AI — Visual Brand-Impersonation Detector
---------------------------------------------------------
Compares a screenshot of a login/landing page against known reference
screenshots of trusted brand login pages using perceptual hashing
(imagehash). This is a lightweight, CPU-only stand-in for the CNN
described in the project report — it genuinely works with zero GPU and
zero training data, and can be swapped for a fine-tuned CNN later without
touching any other module (same `analyze()` signature).

Setup:
1. Save reference screenshots of real brand login pages into
   `backend/app/models/reference_logos/<brand>.png`
   (e.g. reference_logos/paypal.png, reference_logos/sbi.png)
2. On first run, `_build_reference_hashes()` hashes every image in that
   folder and caches the result in memory.
3. When a request includes a `claimed_brand` and a `screenshot_base64`,
   we hash the screenshot and compare it to that brand's reference hash.
   A LOW hash distance to a DIFFERENT brand than claimed, or a HIGH
   distance to the CLAIMED brand's real page, both indicate a clone.
"""
import base64
import io
import os
from pathlib import Path
from typing import Optional

try:
    import imagehash
    from PIL import Image
except ImportError:
    imagehash = None
    Image = None

REFERENCE_DIR = Path(__file__).resolve().parent / "reference_logos"


def _build_reference_hashes() -> dict:
    hashes = {}
    if imagehash is None or not REFERENCE_DIR.exists():
        return hashes
    for file in REFERENCE_DIR.glob("*.png"):
        try:
            img = Image.open(file)
            hashes[file.stem.lower()] = imagehash.phash(img)
        except Exception:
            continue
    return hashes


class VisualDetector:
    def __init__(self):
        self.reference_hashes = _build_reference_hashes()

    def analyze(self, screenshot_base64: Optional[str], claimed_brand: Optional[str]) -> dict:
        # No screenshot supplied -> neutral score, not a false positive/negative
        if not screenshot_base64 or imagehash is None:
            return {
                "score": 0.0,
                "method": "skipped",
                "reasons": [] if not claimed_brand else ["No screenshot supplied for visual comparison"],
            }

        try:
            img_bytes = base64.b64decode(screenshot_base64)
            img = Image.open(io.BytesIO(img_bytes))
            page_hash = imagehash.phash(img)
        except Exception:
            return {"score": 0.0, "method": "error", "reasons": ["Could not decode screenshot"]}

        if not self.reference_hashes:
            return {"score": 0.0, "method": "no_reference_set", "reasons": []}

        # Find the closest known brand by hash distance
        best_brand, best_distance = None, 999
        for brand, ref_hash in self.reference_hashes.items():
            distance = page_hash - ref_hash  # Hamming distance; 0 = identical
            if distance < best_distance:
                best_distance = distance
                best_brand = brand

        reasons = []
        score = 0.0
        claimed = (claimed_brand or "").lower().strip()

        if claimed and claimed in self.reference_hashes:
            claimed_distance = page_hash - self.reference_hashes[claimed]
            if claimed_distance > 12:  # visually different from the REAL claimed brand page
                score = min(1.0, claimed_distance / 32)
                reasons.append(
                    f"Page claims to be '{claimed}' but looks visually different from the real "
                    f"{claimed} page (hash distance {claimed_distance})"
                )
            if best_brand and best_brand != claimed and best_distance <= 8:
                score = max(score, 0.85)
                reasons.append(f"Page visually matches '{best_brand}' branding while claiming to be '{claimed}'")
        elif best_brand and best_distance <= 6:
            # No claimed brand given, but page closely matches a known brand's
            # look-and-feel on an unexpected/unverified domain
            score = 0.5
            reasons.append(f"Page closely resembles known '{best_brand}' branding")

        return {"score": score, "method": "phash", "reasons": reasons, "closest_brand": best_brand}


visual_detector = VisualDetector()
