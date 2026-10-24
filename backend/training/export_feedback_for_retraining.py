"""
PhishSentinel AI — Export Feedback for Retraining
--------------------------------------------------------
Closes the feedback loop: user corrections (from the dashboard's thumbs
up/down or the Chrome extension) should eventually retrain the models.

This script joins `feedback` against `verdicts` (feedback only stores a
verdict_id + correction; the original URL/input lives in the verdicts
table) and produces a CSV in the exact format `train_url_model.py`
expects: `url,label`.

Usage:
    python training/export_feedback_for_retraining.py --out training/data/urls_corrected.csv

Then combine it with your existing dataset and retrain:
    cat training/data/urls.csv training/data/urls_corrected.csv > training/data/urls_v2.csv
    python training/train_url_model.py --data training/data/urls_v2.csv

Only feedback with input_type == "url" is exported here (email feedback
would need the NLP model's own retraining pipeline, which is a separate,
larger effort involving re-running DistilBERT fine-tuning — this script
intentionally stays scoped to the URL model, which is the one with a
ready-to-run training script).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal, VerdictRecord, FeedbackRecord  # noqa: E402


def label_for(verdict: str) -> int:
    """Collapses the 3-way verdict (safe/suspicious/phishing) into the
    2-class label the URL model trains on. 'suspicious' is treated as
    phishing (label 1) — in a corrected-feedback context, a human has
    already told us the ORIGINAL verdict was wrong, so this only matters
    for picking the flipped label below."""
    return 0 if verdict == "safe" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="training/data/urls_corrected.csv")
    parser.add_argument(
        "--min-confidence-flip", type=float, default=0.0,
        help="Skip corrections where the original confidence was already very low "
             "(i.e. the model was barely sure) — optional noise filter.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = (
            db.query(FeedbackRecord, VerdictRecord)
            .join(VerdictRecord, FeedbackRecord.verdict_id == VerdictRecord.verdict_id)
            .filter(VerdictRecord.input_type == "url")
            .all()
        )
    finally:
        db.close()

    if not rows:
        print("No URL feedback found yet. Run some checks, correct a few via the "
              "dashboard or extension feedback button, then re-run this script.")
        return

    out_rows = []
    for feedback, verdict in rows:
        if verdict.confidence < args.min_confidence_flip:
            continue
        if feedback.is_correct:
            # Confirmation: the original verdict was right — reinforce it.
            label = label_for(verdict.verdict)
        elif feedback.actual_label:
            # Correction with an explicit corrected label (from the
            # dashboard or extension's thumbs-down).
            label = 1 if feedback.actual_label == "phishing" else 0
        else:
            # Correction with no explicit label — flip the original verdict.
            label = 0 if verdict.verdict != "safe" else 1
        out_rows.append((verdict.raw_input, label))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "label"])
        writer.writerows(out_rows)

    legit = sum(1 for _, l in out_rows if l == 0)
    phish = len(out_rows) - legit
    print(f"Exported {len(out_rows)} corrected rows ({legit} legit, {phish} phishing) to {args.out}")
    print("Combine with your existing training data and re-run train_url_model.py.")
    print("After retraining, call POST /admin/reload-models (see app/routers/admin.py) "
          "to hot-swap the running backend onto the new model without a restart.")


if __name__ == "__main__":
    main()
