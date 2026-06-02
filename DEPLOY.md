# Deployment — Black Sand Dashboard

> **Wichtig:** Das Dashboard ist eine **Streamlit**-App (dauerhaft laufender Python-Server
> mit WebSockets). **Vercel ist dafür nicht geeignet** (nur Serverless/Next.js). Nutze eine
> Streamlit-fähige Plattform.

## Empfohlen: Streamlit Community Cloud (gratis)

1. Repo zu GitHub pushen (öffentlich oder privat).
2. Auf https://share.streamlit.io einloggen → **New app**.
3. Repo wählen, **Main file**: `src/blacksand/dashboard/app.py`, Python 3.12.
4. **Settings → Secrets**: Inhalt aus `.streamlit/secrets.toml.example` einfügen und mit
   echten Werten füllen (Supabase, Anthropic, Apify, `DASHBOARD_PASSWORD`).
5. Deploy. Streamlit Cloud installiert automatisch aus `requirements.txt`.

→ Login-Gate ist aktiv, sobald `DASHBOARD_PASSWORD` gesetzt ist.

## Alternative: Container-Host (Render / Railway / Fly.io / HF Spaces)

Start-Command:
```
streamlit run src/blacksand/dashboard/app.py --server.port $PORT --server.address 0.0.0.0
```
Secrets als Environment-Variablen setzen (gleiche Namen wie in `.env`).
`requirements.txt` als Build-Quelle.

## Architektur-Hinweis (Trennung Web vs. Pipeline)

- **Dashboard (gehostet)** liest aus Supabase + macht On-Demand-LLM-Calls
  (Playbook/Forecast/Generator) + Embedding-Ähnlichkeit. Deps: `requirements.txt`.
- **Pipeline-CLIs (lokal/Worker)** — Scraping, Transkription (Whisper+ffmpeg),
  visuelle Analyse, Embeddings-Indexierung — laufen NICHT auf dem Web-Host,
  sondern lokal (volle Deps via `uv sync`). So bleibt der Web-Deploy schlank.
