"""CLI: ML-Prognosemodell trainieren & bewerten.

Beispiel:
    uv run bs-model
"""

from __future__ import annotations

from ..ml import metadata_importances, train_model


def main() -> None:
    m = train_model()
    print(f"\n=== ML-Prognosemodell (Inhalt/Embeddings, {m['n']} Posts) ===")
    auc = m["cv_auc"]
    print(f"Vorhersage 'guter Post (Score≥0,5)' — AUC={auc if auc is not None else 'n/a'} "
          f"(0.5=Zufall, >0.65=brauchbar) · Basisrate guter Posts: {m['base_rate']:.0%}\n")

    diag = metadata_importances()
    print(f"Diagnose Metadaten-Features (R²={diag['cv_r2']} — schwache Vorhersagekraft, "
          f"nur richtungsweisend):")
    for f in diag["importances"][:8]:
        bar = "█" * int(round(f["importance"] * 40))
        print(f"  {f['feature']:16} {f['importance']:.3f} {bar}")


if __name__ == "__main__":
    main()
