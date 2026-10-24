"""
PhishSentinel AI — Train the URL Classifier
-----------------------------------------------
Trains a real LogisticRegression (swap for XGBoost with one line change)
on a labelled URL dataset, and saves it so `app/models/url_analyzer.py`
picks it up automatically on next API restart.

Expected input CSV format (data/urls.csv):
    url,label
    http://paypa1-secure.com/login,1
    https://www.paypal.com,0
    ...
    (label: 1 = phishing, 0 = legitimate)

Good free datasets to build this CSV from:
  - PhishTank feed:       https://www.phishtank.com/developer_info.php
  - OpenPhish feed:       https://openphish.com/
  - Kaggle "Phishing Website Detector" / "Phishing URLs" datasets
  - Legitimate URLs: Tranco / Majestic Million top-sites lists (label 0)

Usage:
    cd backend
    python training/train_url_model.py --data training/data/urls.csv
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.models.url_analyzer import extract_features  # noqa: E402

FEATURE_ORDER = [
    "length", "num_dots", "num_hyphens", "num_digits", "num_subdomains",
    "has_ip_host", "has_at_symbol", "has_https", "suspicious_tld",
    "is_shortener", "suspicious_keyword_hits", "typosquat_distance",
]


def vectorize(url: str):
    f = extract_features(url)
    return [
        f.length, f.num_dots, f.num_hyphens, f.num_digits, f.num_subdomains,
        float(f.has_ip_host), float(f.has_at_symbol), float(f.has_https),
        float(f.suspicious_tld), float(f.is_shortener), f.suspicious_keyword_hits,
        f.typosquat_distance,
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="training/data/urls.csv")
    parser.add_argument("--out", default="training/artifacts/url_model.pkl")
    parser.add_argument(
        "--model", choices=["xgboost", "logreg"], default="xgboost",
        help="xgboost (default — matches the report's tech stack, and gives free "
             "SHAP TreeExplainer support with no background dataset needed) or "
             "logreg (lighter weight, still SHAP-explainable via LinearExplainer).",
    )
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"ERROR: {args.data} not found. See the docstring in this file for the expected format "
              f"and free dataset sources.")
        sys.exit(1)

    df = pd.read_csv(args.data)
    print(f"Loaded {len(df)} rows. Class balance:\n{df['label'].value_counts()}")

    X = [vectorize(u) for u in df["url"]]
    y = df["label"].tolist()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    if args.model == "xgboost":
        from xgboost import XGBClassifier
        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", random_state=42,
        )
    else:
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Evaluation on held-out test set ---")
    print(classification_report(y_test, y_pred, target_names=["legitimate", "phishing"]))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    joblib.dump(model, args.out)

    # Save a small background sample alongside the model. url_analyzer.py's
    # SHAP hookup uses this for LinearExplainer (logreg); TreeExplainer
    # (xgboost) doesn't need it but we save it either way for consistency.
    background_path = os.path.join(os.path.dirname(args.out), "url_model_background.pkl")
    background_sample = np.array(X_train[: min(100, len(X_train))])
    joblib.dump(background_sample, background_path)

    print(f"\nModel saved to {args.out}")
    print(f"Background sample saved to {background_path}")
    print("Restart the FastAPI server — url_analyzer.py will load it (and SHAP) automatically.")


if __name__ == "__main__":
    main()
