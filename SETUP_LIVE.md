# Turn on the live Content-Queue cockpit

The **Score a Draft** page reads your NOVA Content Queue live and can send a draft
forward — once two API tokens are set. Until then it safely shows the baked-in
snapshot. This is a one-time, ~10-minute setup you do in Notion + Vercel.

## 1. Create a Notion integration (gives the read/write token)

1. Go to **notion.so/my-integrations** → **New integration**.
2. Name it e.g. `Pulse Dashboard`. Capabilities: **Read content** + **Update content**.
3. Copy the **Internal Integration Secret** (starts with `ntn_` or `secret_`).
4. Open your **NOVA — Content Queue** database in Notion → **⋯ menu → Connections →
   Connect to → Pulse Dashboard**. (This shares the DB with the integration —
   without it the API returns nothing.)

## 2. Get the Content Queue database id

Open the Content Queue as a full page. The URL looks like:
`notion.so/<workspace>/<32-char-id>?v=...` — the **32-char id before `?v=`** is your
database id. (Our data-source id is `02c8afc9bc4c4ac6ac3e2559d5350ba7`; the code
tries both the data-source and database endpoints, so either id works.)

## 3. Add the two env vars in Vercel

Vercel → project **social-media-intelligence** → **Settings → Environment
Variables** → add (Production + Preview):

| Name | Value |
|---|---|
| `NOTION_TOKEN` | the integration secret from step 1 |
| `NOTION_DATABASE_ID` | the id from step 2 |

Then **redeploy** (Deployments → ⋯ → Redeploy, or just push any commit).

## 4. Done

Reload **Score a Draft**. The idea list badge flips to **● Live from Notion**,
each draft shows a `live` pill, and **Send to NOVA** is enabled — pick a status
(Approve / Schedule / Send for review) + date and it updates the draft's card in
your Content Queue.

---

### What "Send to post" does (and doesn't)
It advances the draft inside **NOVA's own workflow** (sets Status → Approved/
Scheduled and stamps the date, saving your improved caption). It does **not**
auto-publish to Instagram/TikTok, because a real post needs the media asset
(image/reel video) attached — that final hop stays in your existing Metricool
flow. If you later want a true "publish to Metricool" button, that's a follow-up
using a Metricool API token + the media URL.

### Security
Tokens live only in Vercel env vars (server-side). They are never sent to the
browser and never committed to git. The `/api/*` functions read them at runtime.
