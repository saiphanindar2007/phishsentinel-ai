import base64
import io
import os
import shutil

import pytest

pytest.importorskip("imagehash")
from PIL import Image  # noqa: E402


@pytest.fixture()
def temp_reference_set(tmp_path, monkeypatch):
    """Builds a tiny, isolated reference-logo set for this test only —
    doesn't touch the real app/models/reference_logos/ folder.

    Uses STRUCTURALLY distinct layouts (not just different flat colors)
    for each "brand", because pHash hashes the low-frequency DCT of a
    grayscale-reduced image — two solid, textureless color blocks of
    different colors can hash IDENTICALLY (there's no structure for the
    DCT to differentiate), which would make this test pass for the wrong
    reason. Different rectangle positions/orientations give the hash
    something real to distinguish, closer to how two different real login
    pages actually differ."""
    from app.models import visual_detector as vd_module
    from PIL import ImageDraw

    ref_dir = tmp_path / "reference_logos"
    ref_dir.mkdir()

    def make(name, bar_side, bg, fg):
        img = Image.new("RGB", (200, 200), color=bg)
        draw = ImageDraw.Draw(img)
        if bar_side == "left":
            draw.rectangle([0, 0, 80, 200], fill=fg)
        else:
            draw.rectangle([0, 0, 200, 80], fill=fg)
        img.save(ref_dir / f"{name}.png")

    make("paypal", "left", (0, 48, 135), (255, 255, 255))
    make("realbank", "top", (0, 107, 63), (20, 20, 20))

    monkeypatch.setattr(vd_module, "REFERENCE_DIR", ref_dir)
    detector = vd_module.VisualDetector()
    return detector, ref_dir


def _b64_of(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_page_matching_its_claimed_brand_scores_low(temp_reference_set):
    detector, ref_dir = temp_reference_set
    # A page that looks like paypal's real reference image, claiming to be paypal
    same_as_paypal = Image.open(ref_dir / "paypal.png")
    result = detector.analyze(_b64_of(same_as_paypal), claimed_brand="paypal")
    assert result["score"] < 0.3


def test_page_matching_a_different_brand_than_claimed_is_flagged(temp_reference_set):
    detector, ref_dir = temp_reference_set
    # A page that visually matches "realbank" but claims to be "paypal" —
    # the classic brand-impersonation pattern this module exists to catch.
    looks_like_realbank = Image.open(ref_dir / "realbank.png")
    result = detector.analyze(_b64_of(looks_like_realbank), claimed_brand="paypal")
    assert result["score"] > 0.5
    assert result["closest_brand"] == "realbank"


def test_no_screenshot_returns_neutral_score(temp_reference_set):
    detector, _ = temp_reference_set
    result = detector.analyze(None, claimed_brand="paypal")
    assert result["score"] == 0.0
    assert result["method"] == "skipped"


def test_unparseable_screenshot_fails_safe(temp_reference_set):
    detector, _ = temp_reference_set
    result = detector.analyze("not-valid-base64-image-data", claimed_brand="paypal")
    assert result["score"] == 0.0
    assert result["method"] == "error"
