"""Wendet db/schema.sql über die Supabase Management-API an."""

from __future__ import annotations

from pathlib import Path

from ..db import run_sql

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "db" / "schema.sql"


def main() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    print(f"→ Wende Schema an: {SCHEMA_PATH}")
    run_sql(sql)
    print("✓ Schema angewendet.")


if __name__ == "__main__":
    main()
