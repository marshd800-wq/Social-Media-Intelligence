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

---

## 5. (Phase 2) Make NOVA the source of truth for Targets / Matrix / SOPs

The **Engagement Targets**, **Content Matrix**, and **SOPs** views read live from
Notion via `/api/config`. Each block is independent and **degrades to the baked-in
fallback** if its database id isn't set — so you can wire them one at a time.

**Content Matrix coverage** (no new database — reuses the Content Queue):
1. In the **Content Queue**, add two properties:
   - `Character` — **Multi-select** (or Select) with options containing the words
     *REALTOR*, *Entrepreneur*, *Curator* (or *Luxury*), *Atlanta* (or *Native*).
   - `Job` — **Select** with options *Entertain*, *Educate*, *Encourage*.
2. Tag your posts. The matrix tallies coverage from these automatically — no extra
   env var needed (it reuses `NOTION_DATABASE_ID`). Matching is keyword-based and
   case-insensitive, so exact option names don't matter.

**Engagement Targets** (small new database):
1. New database **NOVA — Engagement Targets** with properties:
   `Platform` (title), `Target Low` (number), `Target High` (number, optional),
   `Notes` (text). One row per platform (TikTok, Instagram, LinkedIn, …).
2. Connect it to the `Pulse Dashboard` integration (⋯ → Connections).
3. Add env var **`NOTION_TARGETS_DB`** = that database's 32-char id.

**SOPs** (small new database):
1. New database **NOVA — SOPs** with properties:
   `Name` (title), `Trigger` (text/select, optional), `Body` (text).
2. Connect it to the `Pulse Dashboard` integration.
3. Add env var **`NOTION_SOPS_DB`** = that database's 32-char id.

Redeploy after adding env vars. The three views flip from "awaiting live data" to
live within ~60s (responses are edge-cached 60s to stay well under Notion's rate
limit). Analytics (reach, ER, themes) intentionally stay on the weekly Metricool
bake — Notion only serves the small, hand-edited config you own.

| New env var | Powers | If unset |
|---|---|---|
| `NOTION_TARGETS_DB` | Engagement Targets numbers | shows unverified fallback benchmarks |
| `NOTION_SOPS_DB` | SOPs view | shows "connect the SOPs database" |
| (reuses `NOTION_DATABASE_ID`) | Matrix coverage counts | cells show "awaiting live data" |
