"""Build #22 — Backtesting / Kalibrierung des Prognosemodells.

Bewertet das Inhalts-Modell (Embeddings → P(guter Post)) ehrlich per
Out-of-Fold-Kreuzvalidierung:
  * AUC, Treffergenauigkeit, Brier-Score (Kalibrierungsgüte)
  * Kalibrierungstabelle: vorhergesagte vs. tatsächliche „gut"-Rate je Wahrscheinlichkeits-Bin
  * Signal-Vergleich: Inhalt/Embeddings vs. Metadaten vs. Basisrate

So wissen wir, WORAUF man sich verlassen kann — und wie gut kalibriert die
Wahrscheinlichkeiten sind.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .ml import _embedding_dataset, metadata_importances


def evaluate() -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
    from sklearn.model_selection import cross_val_predict

    X, y = _embedding_dataset()
    n = len(X)
    if n < 40 or len(set(y)) < 2:
        raise RuntimeError(f"Zu wenig/ungeeignete Daten ({n}).")

    base_rate = float(y.mean())
    clf = LogisticRegression(max_iter=1000, C=0.5)
    proba = cross_val_predict(clf, X, y, cv=5, method="predict_proba")[:, 1]

    auc = float(roc_auc_score(y, proba))
    acc = float(accuracy_score(y, (proba >= 0.5).astype(int)))
    brier = float(brier_score_loss(y, proba))

    dfc = pd.DataFrame({"p": proba, "y": y})
    dfc["bin"] = pd.cut(dfc["p"], [0, 0.1, 0.2, 0.3, 0.5, 1.0], include_lowest=True)
    calibration = [
        {"bin": str(b), "n": int(g.shape[0]),
         "pred_mean": round(float(g["p"].mean()), 3),
         "actual_rate": round(float(g["y"].mean()), 3)}
        for b, g in dfc.groupby("bin", observed=True)
    ]

    meta = metadata_importances()
    leaderboard = [
        {"signal": "Inhalt / Embeddings", "metric": "AUC", "value": round(auc, 3)},
        {"signal": "Metadaten (Länge/Hashtags/Zeit)", "metric": "R²",
         "value": meta.get("cv_r2")},
        {"signal": "Basisrate (immer 'gut' raten)", "metric": "AUC", "value": 0.5},
    ]

    return {
        "n": n, "base_rate": round(base_rate, 3),
        "auc": round(auc, 3), "accuracy": round(acc, 3), "brier": round(brier, 3),
        "calibration": calibration, "leaderboard": leaderboard,
        "lift": round((np.mean(y[proba >= 0.5]) / base_rate), 2)
        if (proba >= 0.5).any() and base_rate > 0 else None,
    }
