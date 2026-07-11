// GET /api/drafts — live read of the NOVA Content Queue (Notion).
// Returns every planning-stage item parsed into
// {pageId, name, hook, caption, platform, category, status, trigger,
//  character[], job, series, format, disposition, perf, brand}. The browser
// scores drafts (Score a Draft) and renders the Content Matrix from this feed.
//
// Requires env vars (see SETUP_LIVE.md):
//   NOTION_TOKEN         Notion internal integration secret (starts with "ntn_"/"secret_")
//   NOTION_DATABASE_ID   the Content Queue database id (or data source id)
//
// If the env vars are missing, responds 200 {configured:false} so the frontend
// silently falls back to the baked-in snapshot.

const NOTION_VERSION = "2022-06-28";
// All planning stages, idea through scheduled. Score a Draft filters to active
// drafts with a caption; the Content Matrix uses every row.
const ACTIVE = ["Idea", "Draft", "Pending Review", "Needs Revision", "Approved", "Scheduled"];

function text(prop) {
  if (!prop) return "";
  const arr = prop.title || prop.rich_text || [];
  return arr.map((t) => t.plain_text).join("");
}
function sel(prop) { return (prop && prop.select && prop.select.name) || ""; }
function multi(prop) { return (prop && prop.multi_select ? prop.multi_select.map((o) => o.name) : []); }
function num(prop) { return (prop && typeof prop.number === "number") ? prop.number : null; }

function flattenDraftCaption(base, hook, caption) {
  const out = [];
  const dc = (caption || "").trim();
  if (dc.startsWith("[")) {
    try {
      for (const it of JSON.parse(dc)) {
        if (it && it.caption)
          out.push({ hook: it.hook || "", caption: it.caption, trigger: it.suggestedTrigger || "" });
      }
    } catch (_) { /* fall through */ }
  }
  // Always emit at least one row per page (idea rows have no caption yet).
  if (out.length === 0) out.push({ hook: hook || "", caption: dc, trigger: "" });
  return out.map((v) => ({ ...base, ...v }));
}

async function queryNotion(token, dbId) {
  const filter = { or: ACTIVE.map((s) => ({ property: "Status", select: { equals: s } })) };
  const headers = { Authorization: `Bearer ${token}`, "Notion-Version": NOTION_VERSION, "Content-Type": "application/json" };
  const endpoints = [
    `https://api.notion.com/v1/data_sources/${dbId}/query`,
    `https://api.notion.com/v1/databases/${dbId}/query`,
  ];
  // Find a working endpoint, then page through all results.
  let base = null;
  for (const url of endpoints) {
    const r = await fetch(url, { method: "POST", headers, body: JSON.stringify({ filter, page_size: 100 }) });
    if (r.ok) { base = { url, first: await r.json() }; break; }
    if (r.status !== 404) throw new Error(`Notion ${r.status}: ${await r.text()}`);
  }
  if (!base) throw new Error("Notion query failed on both data_sources and databases endpoints");
  let results = base.first.results || [];
  let cursor = base.first.has_more ? base.first.next_cursor : null;
  while (cursor) {
    const r = await fetch(base.url, { method: "POST", headers, body: JSON.stringify({ filter, page_size: 100, start_cursor: cursor }) });
    if (!r.ok) break;
    const j = await r.json();
    results = results.concat(j.results || []);
    cursor = j.has_more ? j.next_cursor : null;
  }
  return results;
}

export default async function handler(req, res) {
  const token = process.env.NOTION_TOKEN;
  const dbId = process.env.NOTION_DATABASE_ID;
  if (!token || !dbId) return res.status(200).json({ configured: false });
  try {
    const pages = await queryNotion(token, dbId);
    const drafts = [];
    for (const p of pages) {
      const pr = p.properties || {};
      const base = {
        pageId: p.id,
        name: text(pr.Name),
        platform: sel(pr.Platform),
        category: sel(pr.Category),
        status: sel(pr.Status),
        character: multi(pr.Character),
        job: sel(pr.Job),
        series: sel(pr["Series / Lane"]),
        format: sel(pr.Format),
        disposition: sel(pr.Disposition),
        perf: num(pr["Perf Score"]),
        brand: num(pr["Brand Score"]),
      };
      flattenDraftCaption(base, text(pr.Hook), text(pr["Draft Caption"])).forEach((d) => drafts.push(d));
    }
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ configured: true, count: drafts.length, drafts });
  } catch (e) {
    return res.status(500).json({ configured: true, error: String(e.message || e) });
  }
}
