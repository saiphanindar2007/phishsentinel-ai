"""
PhishSentinel AI — Fine-tune the NLP Content Classifier
-------------------------------------------------------------
Fine-tunes DistilBERT on a labelled phishing-email/SMS dataset and saves
it so `app/models/nlp_classifier.py` loads it automatically.

Expected input CSV format (data/emails.csv):
    text,label
    "Dear customer, verify your account within 24 hours...",PHISHING
    "Hi John, attached is the report you asked for.",LEGITIMATE
    ...

Good free datasets:
  - Kaggle "Phishing Email Detection" datasets
  - Enron email dataset (as the legitimate/negative class)
  - Nazario phishing corpus

Usage (needs a GPU for reasonable speed, but will run on CPU for a small
sample too — just slower):
    cd backend
    pip install transformers torch datasets accelerate
    python training/train_nlp_model.py --data training/data/emails.csv --epochs 3
"""
import argparse
import os
import sys

import pandas as pd
from datasets import Dataset
from sklearn.model_selection import train_test_split
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
)
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

MODEL_NAME = "distilbert-base-uncased"
LABELS = ["LEGITIMATE", "PHISHING"]


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="training/data/emails.csv")
    parser.add_argument("--out", default="training/artifacts/nlp_model")
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"ERROR: {args.data} not found. See the docstring in this file for the expected "
              f"format and free dataset sources.")
        sys.exit(1)

    df = pd.read_csv(args.data)
    df["label_id"] = df["label"].apply(lambda x: LABELS.index(x.upper()))
    print(f"Loaded {len(df)} rows. Class balance:\n{df['label'].value_counts()}")

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label_id"])
    train_ds = Dataset.from_pandas(train_df[["text", "label_id"]].rename(columns={"label_id": "label"}))
    test_ds = Dataset.from_pandas(test_df[["text", "label_id"]].rename(columns={"label_id": "label"}))

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=256)

    train_ds = train_ds.map(tokenize, batched=True)
    test_ds = test_ds.map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=2, id2label={0: "LEGITIMATE", 1: "PHISHING"}, label2id={"LEGITIMATE": 0, "PHISHING": 1}
    )

    training_args = TrainingArguments(
        output_dir="training/checkpoints",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_steps=20,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=test_ds,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    print("\n--- Final evaluation ---")
    print(trainer.evaluate())

    os.makedirs(args.out, exist_ok=True)
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"\nModel saved to {args.out}")
    print("Restart the FastAPI server — nlp_classifier.py will load it automatically.")


if __name__ == "__main__":
    main()
