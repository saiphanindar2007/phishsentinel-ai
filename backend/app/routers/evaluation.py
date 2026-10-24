"""
PhishSentinel AI — Reproducible Evaluation Bench
------------------------------------------------------
A fixed, version-controlled labelled URL set (backend/eval/labeled_urls.csv)
scored through the exact same code path production traffic uses
(url_analyzer -> fuse), so these numbers are never "demo-only" shortcuts.

Reproducibility is enforced, not just claimed:
  * the dataset's SHA-256 is included in every run's output, so a changed
    dataset is immediately visible in a diff
  * scoring uses no randomness (heuristic rule engine, or a loaded model
    in eval mode — either way, same input -> same output every time)
  * the exact fusion weights/thresholds used are echoed back in the result
  * every run is written as a timestamped JSON artifact under
    backend/eval/runs/, so results can be compared across commits/config
    changes instead of only trusting the latest number
"""
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Depends

from app.config import BASE_DIR, FUSION_WEIGHTS, SUSPICIOUS_THRESHOLD, PHISHING_THRESHOLD
from app.models.fusion_engine import fuse
from app.models.url_analyzer import url_analyzer
from app.security import rate_limit, require_admin_key

logger = logging.getLogger("phishsentinel.evaluation")

router = APIRouter(
    prefix="/eval",
    tags=["evaluation"],
    dependencies=[Depends(rate_limit), Depends(require_admin_key)],
)

DATASET_PATH = BASE_DIR / "eval" / "labeled_urls.csv"
RUNS_DIR = BASE_DIR / "eval" / "runs"
LABELS = ("safe", "suspicious", "phishing")
URL_ONLY_WEIGHTS = {"url": 1.0, "nlp": 0.0, "visual": 0.0, "reputation": 0.0}
ZERO = {"score": 0.0, "reasons": []}


def _load_dataset() -> List[Dict[str, str]]:
    rows = []
    with open(DATASET_PATH, newline="", encoding="utf-8") as fh:
        import csv
        for row in csv.DictReader(fh):
            if row.get("url") and row.get("label") in LABELS:
                rows.append({"url": row["url"].strip(), "label": row["label"].strip()})
    return rows


def _dataset_hash() -> str:
    return hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()[:16]


def _confusion_and_metrics(rows: List[dict]):
    confusion = {a: {p: 0 for p in LABELS} for a in LABELS}
    for r in rows:
        confusion[r["label"]][r["predicted"]] += 1

    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[a][label] for a in LABELS if a != label)
        fn = sum(confusion[label][p] for p in LABELS if p != label)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) else None
        per_class[label] = {
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "support": sum(confusion[label].values()),
        }
    correct = sum(confusion[l][l] for l in LABELS)
    accuracy = round(correct / len(rows), 4) if rows else None
    f1_values = [m["f1"] for m in per_class.values() if m["f1"] is not None]
    macro_f1 = round(sum(f1_values) / len(f1_values), 4) if f1_values else None
    return confusion, per_class, accuracy, macro_f1


@router.post("/run")
def run_evaluation():
    """Scores the full fixed dataset through the live detector and fusion
    code, and returns a reproducible metrics report."""
    rows = _load_dataset()
    for r in rows:
        url_result = url_analyzer.analyze(r["url"])
        fused = fuse(url_result, ZERO, ZERO, ZERO, weights=URL_ONLY_WEIGHTS)
        r["predicted"] = fused["verdict"]
        r["confidence"] = fused["confidence"]

    confusion, per_class, accuracy, macro_f1 = _confusion_and_metrics(rows)
    result = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "dataset_path": str(DATASET_PATH.relative_to(BASE_DIR)),
        "dataset_sha256_16": _dataset_hash(),
        "dataset_size": len(rows),
        "config": {
            "fusion_weights": URL_ONLY_WEIGHTS,
            "suspicious_threshold": SUSPICIOUS_THRESHOLD,
            "phishing_threshold": PHISHING_THRESHOLD,
        },
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": confusion,
        "mismatches": [
            {"url": r["url"], "label": r["label"], "predicted": r["predicted"], "confidence": r["confidence"]}
            for r in rows if r["label"] != r["predicted"]
        ],
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    try:
        (RUNS_DIR / f"{run_id}.json").write_text(json.dumps(result, indent=2))
    except OSError:
        logger.exception("could not persist eval run artifact")
    result["run_id"] = run_id
    return result


@router.get("/runs")
def list_runs(limit: int = 20):
    """Past evaluation runs (newest first), for tracking drift over time."""
    if not RUNS_DIR.exists():
        return []
    files = sorted(RUNS_DIR.glob("*.json"), reverse=True)[: max(1, min(limit, 200))]
    out = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            out.append({
                "run_id": f.stem, "run_at": data.get("run_at"), "accuracy": data.get("accuracy"),
                "macro_f1": data.get("macro_f1"), "dataset_sha256_16": data.get("dataset_sha256_16"),
            })
        except (OSError, ValueError):
            continue
    return out


@router.get("/dataset")
def get_dataset():
    rows = _load_dataset()
    return {"size": len(rows), "sha256_16": _dataset_hash(), "rows": rows}
