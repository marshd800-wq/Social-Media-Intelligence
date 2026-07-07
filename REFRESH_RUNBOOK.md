# Weekly Refresh Runbook

This is the exact procedure a scheduled session follows to refresh the Diana Marsh
content-intelligence dashboard with the latest Metricool data and redeploy it.
Everything is deterministic — same inputs produce the same output.

**Repo:** `marshd800-wq/Social-Media-Intelligence` · **Metricool brand id:** `3526631` · **Timezone:** `America/New_York`

---

## Step 1 — Pull fresh data from Metricool (MCP)

Use `mcp__Metricool__getAnalyticsDataByMetrics`, `brandId=3526631`,
`from=2024-04-01T00:00:00-05:00`, `to=<today>T23:59:59-05:00`. Save each result's
`{"rows":[...]}` JSON to the path shown. Column order MUST match exactly (the
ingest scripts map by position).

| File | metrics (in this order) |
|---|---|
| `data/raw/ig_posts_raw.txt` | `IGPO02,IGPO03,IGPO06,IGPO07,IGPO08,IGPO13,IGPO14,IGPO15,IGPO27,IGPO28,IGPO12` |
| `data/raw/ig_reels_raw.txt` | `IGRE02,IGRE03,IGRE06,IGRE07,IGRE10,IGRE11,IGRE12,IGRE21,IGRE23,IGRE24,IGRE27,IGRE28,IGRE29` |
| `data/raw/tiktok_raw.json`  | `TKPO02,TKPO05,TKPO03,TKPO22,TKPO07,TKPO08,TKPO09,TKPO10,TKPO11,TKPO13,TKPO15` |

- For the two IG files, save the raw `{"rows":[...]}` object as-is (the ingest strips to the first `{`).
- For TikTok, wrap as `{"cols":["date","caption","url","type","views","likes","comments","shares","reach","fullwatchrate","avgwatch"],"rows":[...]}`.
- If the MCP result is large it may persist to a tool-results file — copy that file to the path above.

**If the Metricool MCP is unavailable in this session:** skip Step 1, keep the
existing raw files, and continue — the dashboard still rebuilds + redeploys from
the last data. Note this in the completion report.

## Step 2 — Rebuild everything

```bash
cd <repo root>
bash refresh.sh
```

This runs ingest → analyze → multi-platform merge → cross-platform → platform
baselines → back-test → report → dashboard rebuild (regenerates `index.html`).

## Step 3 — Commit & deploy

```bash
git add -A
git commit -m "Weekly data refresh"      # skip if 'git status' shows no changes
git push origin claude/bold-galileo-170ew1
git branch -f main claude/bold-galileo-170ew1
git push origin main                      # main is the Vercel production branch → auto-deploys
```

Vercel auto-builds production from `main`; the live URL
(`social-media-intelligence-seven.vercel.app`) updates in ~1–2 min.

## Step 4 — Report

One short line: what changed (post counts, any notable movement), or "no new
posts since last run," plus the production URL. If Step 1 was skipped, say so.

---
*Do not change scoring weights or thresholds during a refresh — this job only
updates data. Model changes are a separate, deliberate task.*
