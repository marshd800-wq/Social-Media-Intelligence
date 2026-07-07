# NOVA Social Media Intelligence Engine

An Instagram content-intelligence layer for **Diana Marsh — @dianatheatlrealtor**
(*Luxury With a Pulse*, Berkshire Hathaway HomeServices Georgia Properties, Metro Atlanta).

It ingests Diana's real Instagram performance history, finds what works, learns a
predictive scoring model, and produces a content brief formatted for the NOVA
Content Queue.

## What it does

1. **Ingest** — normalizes Metricool exports (posts + reels connectors) into one
   dataset with engagement metrics, themes, hooks, hashtags, and derived rates.
2. **Analyze** — content-type performance, theme performance, top/bottom hooks,
   winning-vs-losing language, posting-cadence (day & time), and the commonalities
   of the 10 best and 10 worst posts.
3. **Score** — a transparent, back-tested model that predicts the relative
   performance of a *proposed* hook + caption + format before you post.
4. **Brief** — `output/nova_content_brief.md`, ready to drop into NOVA.

## Data source

Pulled from **Metricool** (brand *Diana the ATL Realtor*, id `3526631`) via MCP —
an **authorized** read of Diana's own Instagram business account, not scraping.
Covers **133 posts, Apr 2024 – Jul 2026**.

> **Note on Apify & transcription:** the original brief specified the Apify MCP and
> reel-audio transcription. Apify is not available in this environment (and would
> require a paid token + scraping); Metricool is already connected and returns the
> same engagement data through Diana's own account, so it is used instead. Metricool
> does **not** expose reel audio, so spoken-word transcription (brief Step 3) is not
> included — analysis uses caption text, on-caption hooks, and full engagement data.

## Run it

Pure Python 3 standard library — no dependencies.

```bash
python3 src/run_all.py          # rebuild dataset + analysis + report

# score a draft before producing it
python3 src/score.py --type reel \
  --hook "The job offer was the easy part." \
  --caption "full caption ... Comment ATLANTA and I'll take it from there."
```

## Layout

```
data/raw/            raw Metricool exports (posts + reels)
data/processed/      dataset.json, dataset.csv, analysis.json, model_validation.json
src/ingest.py        raw -> normalized dataset
src/analyze.py       dataset -> analysis.json
src/score.py         predictive scoring model (+ CLI)
src/validate.py      back-test of the model against real history
src/build_report.py  analysis.json -> output/analysis_report.md
output/analysis_report.md    full deep-dive
output/nova_content_brief.md the NOVA-ready brief
```

## Headline findings

- **Reels** win reach (~250 avg); **carousels** win engagement (ER 0.14) & saves;
  **static images** trail everything (8 of the bottom 10).
- Best themes: **personal/BTS, market-education, humor, buyer/financing, relocation**.
- Worst themes: the **"Find Home Anywhere" global series** and **generic seasonal
  home-tips** — clear candidates to cut.
- **Fewer hashtags win**: top posts avg **1.4**, bottom posts avg **5.7**.
- **Lead-gen CTAs** ("Comment DEAL") earn **~2.3× the comments**.
- Best time to post: **5–8pm ET**; best days: **Wed, Fri, Sat**.
- Model back-test: predicted-top-quartile posts averaged **3.8× the reach** of
  predicted-bottom.
