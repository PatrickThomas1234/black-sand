"""CLI: Backtesting/Kalibrierung des Prognosemodells.

Beispiel:
    uv run bs-backtest
"""

from __future__ import annotations

from ..backtest import evaluate


def main() -> None:
    r = evaluate()
    print(f"\n=== Backtesting (Inhalts-Modell, {r['n']} Posts, Out-of-Fold) ===")
    print(f"AUC={r['auc']} · Treffer={r['accuracy']:.0%} · Brier={r['brier']} "
          f"(niedriger=besser) · Basisrate={r['base_rate']:.0%}")
    if r.get("lift"):
        print(f"Lift: vorhergesagte 'gute' Posts sind {r['lift']}× häufiger wirklich gut als der Schnitt\n")

    print("Kalibrierung (vorhergesagt → tatsächlich):")
    for c in r["calibration"]:
        print(f"  {c['bin']:14} n={c['n']:3}  P̄={c['pred_mean']:.2f} → real {c['actual_rate']:.2f}")

    print("\nSignal-Vergleich:")
    for s in r["leaderboard"]:
        print(f"  {s['signal']:34} {s['metric']}={s['value']}")


if __name__ == "__main__":
    main()
