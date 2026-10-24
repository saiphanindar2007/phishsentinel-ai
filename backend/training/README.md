# Training Guide — Upgrading From Heuristics to Trained Models

The backend runs completely out of the box using transparent, hand-tuned
heuristic scoring in `url_analyzer.py` and `nlp_classifier.py`. This
means you can demo the entire system — extension, dashboard, live feed,
feedback loop — before training a single model.

When you're ready to show "real ML" for the report/demo, train the two
core models here. Each script is a drop-in upgrade: no other file in the
project needs to change.

## 1. URL Classifier (XGBoost by default, real SHAP explanations included)

**No internet access yet, or just want to prove the pipeline works?**
Generate a synthetic bootstrap dataset first — fully offline, no
external downloads:
```bash
cd backend
python training/generate_bootstrap_dataset.py --n 4000 --out training/data/urls.csv
```
This is enough to run every step below and confirm everything wires up
correctly, but it's rule-generated, not real phishing data — swap it out
before citing accuracy numbers in your report (see the warning printed
by the script, and the docstring at the top of
`generate_bootstrap_dataset.py`).

**For your real submission**, build `training/data/urls.csv` with
columns `url,label` (1=phishing, 0=legit) from:
- PhishTank (https://phishtank.org/developer_info.php)
- OpenPhish (https://openphish.com/)
- Kaggle phishing URL datasets
- Tranco top-sites list (https://tranco-list.eu/) for legitimate examples

Then train:
```bash
pip install -r requirements.txt
python training/train_url_model.py --data training/data/urls.csv
# or: --model logreg for a lighter-weight alternative (still SHAP-explainable)
```

This saves `training/artifacts/url_model.pkl` (plus a small background
sample SHAP uses). **You don't need to restart the server** — either
restart it normally, or call the hot-reload endpoint to promote the new
model with zero downtime:
```bash
curl -X POST http://localhost:8000/admin/reload-models
```
`url_analyzer.py` picks it up automatically either way, and every
verdict it produces from then on comes with real per-feature SHAP
attributions instead of the heuristic engine's rule-based reasons.

## 2. NLP Content Classifier (DistilBERT fine-tune)

```bash
# Build training/data/emails.csv with columns: text,label (PHISHING/LEGITIMATE)
# Sources: Kaggle "Phishing Email Detection" datasets, Enron corpus
#          (legitimate class), Nazario phishing corpus.

python training/train_nlp_model.py --data training/data/emails.csv --epochs 3
```

This saves the fine-tuned model to `training/artifacts/nlp_model/`.
Restart the API — `nlp_classifier.py` loads it automatically.

CPU-only machines: this will run, just slowly. Reduce `--epochs` to 1 for
a quick demo-quality model, or use Google Colab's free GPU tier and copy
the resulting folder back into `training/artifacts/nlp_model/`.

## 3. Visual Detector Reference Set

No training needed — just add real screenshots:
```
backend/app/models/reference_logos/paypal.png
backend/app/models/reference_logos/sbi.png
backend/app/models/reference_logos/google.png
...
```
Take these from the real, verified login pages of brands relevant to
your users. The perceptual-hash comparison activates automatically once
files exist in that folder.

## 4. Explainability (SHAP) — Already Wired In

`app/models/shap_explainer.py` attaches a real `shap.TreeExplainer`
(XGBoost) or `LinearExplainer` (logreg) automatically the moment a
trained URL model loads — nothing further to do. Verdicts then report
genuine per-feature SHAP attributions (`"SHAP: HTTPS encryption present
pushed the verdict toward 'safe' (impact 0.31)"`, etc.) instead of the
heuristic engine's rule-based reasons. `SHAP_ENABLED=false` in `.env`
turns this off if you ever want to compare against the plain heuristic
explanations side by side.

To generate a standalone SHAP summary plot for your report/slides (not
required for the live API, just useful for a chart):
```python
import joblib, shap
from training.train_url_model import vectorize
model = joblib.load("training/artifacts/url_model.pkl")
background = joblib.load("training/artifacts/url_model_background.pkl")
explainer = shap.TreeExplainer(model)  # or shap.LinearExplainer(model, background) for logreg
# X_test = [vectorize(u) for u in your_test_urls]
# shap.summary_plot(explainer.shap_values(X_test), X_test, feature_names=FEATURE_ORDER)
```

## 5. Closing the Retraining Loop

The full loop, end to end:

1. **Collect corrections** — already happening automatically from two
   sources: the dashboard's Analyzer tab (thumbs up/down) and the Chrome
   extension's popup feedback buttons. Both write to the `feedback` table
   via the same `POST /feedback` endpoint.
2. **Export them into training format:**
   ```bash
   python training/export_feedback_for_retraining.py --out training/data/urls_corrected.csv
   ```
   This joins `feedback` against `verdicts` (feedback only stores a
   verdict_id; the original URL lives on the verdict record) and writes
   a ready-to-train `url,label` CSV.
3. **Merge and retrain:**
   ```bash
   cat training/data/urls.csv training/data/urls_corrected.csv > training/data/urls_v2.csv
   python training/train_url_model.py --data training/data/urls_v2.csv
   ```
4. **Promote the new model with zero downtime:**
   ```bash
   curl -X POST http://localhost:8000/admin/reload-models
   ```
   (Requires the `X-API-Key` header if you've set `API_KEY` in `.env`.)

Run steps 2–4 on a cadence that fits your demo (weekly cron, a GitHub
Action, or just manually before your review) — that's the full
"continuous feedback loop" from the project report, implemented with
tools you already have. `get_feedback_dataset()` in `app/db/crud.py`
exposes the same joined data programmatically if you want to build a
scheduled job around it instead of the CLI script.
