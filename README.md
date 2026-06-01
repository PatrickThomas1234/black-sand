# Black Sand

AI-gestütztes Social-Media-Analyse-System.

Ein Pipeline-System, das über **Apify**-Scraper ganze Social-Media-Profile abzieht,
die Daten (Posts, Likes, Comments, Views, Transkripte) in **Supabase** speichert,
inhaltlich analysiert und die Performance jedes Posts **relativ zur Kanal-Baseline**
bewertet — als Grundlage für datengetriebene Content-Tipps.

## Roadmap

| Phase | Inhalt | Status |
|-------|--------|--------|
| **1 — Foundation** | Projekt, Supabase-Schema, Apify-Instagram-Ingestion | ✅ in Arbeit |
| **2 — Enrichment** | Whisper-Transkription + LLM-Content-Analyse | geplant |
| **3 — Scoring** | Engagement-Metriken + baseline-relatives Rating | geplant |
| **4 — Insights** | Tipps/Empfehlungen ableiten | geplant |

## Setup

```bash
# Abhängigkeiten installieren (uv)
uv sync

# .env anlegen (Vorlage kopieren und ausfüllen)
cp .env.example .env
```

Trage in die `.env` deine Keys ein. `SUPABASE_*` sind bereits gesetzt;
für die Ingestion brauchst du noch einen **`APIFY_TOKEN`**
(https://console.apify.com/account/integrations).

## Nutzung

```bash
# Datenbank-Schema anwenden (einmalig / nach Schema-Änderungen)
uv run bs-apply-schema

# Ein Instagram-Profil scrapen und speichern
uv run bs-ingest natgeo --max-posts 100

# Performance-Scores berechnen (relativ zur Kanal-Baseline)
uv run bs-score natgeo

# Lokales Dashboard öffnen (Browser: http://localhost:8501)
uv run streamlit run src/blacksand/dashboard/app.py
```

## Architektur

```
Apify (IG-Scraper) → Ingestion (normalize) → Supabase (Postgres)
                                                    ↓
                          Enrichment (Whisper/LLM) → Scoring → Insights
```

### Datenmodell (`db/schema.sql`)

- **profiles** — Kanal/Account (Follower, Bio, …)
- **posts** — einzelne Posts (Caption, Typ, Hashtags, Media-URL, …)
- **metric_snapshots** — Zeitreihe der Engagement-Metriken pro Post
- **transcripts** — Video-/Reel-Transkripte (Phase 2)
- **content_analysis** — LLM-Verständnis des Inhalts (Phase 2)
- **performance_scores** — baseline-relatives Rating (Phase 3)
- **raw_payloads** — alle Roh-Scraper-Antworten (Reproduzierbarkeit)

## Projektstruktur

```
src/blacksand/
  config.py          # .env laden
  db.py              # Supabase-Client + Management-API SQL
  apify.py           # Apify-Scraper-Wrapper
  normalize.py       # Apify-Items → DB-Rows
  ingest.py          # Ingestion-Pipeline
  cli/
    apply_schema.py  # bs-apply-schema
    ingest.py        # bs-ingest
db/schema.sql        # DB-Schema
```
