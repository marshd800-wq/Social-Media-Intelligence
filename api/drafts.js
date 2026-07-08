// GET /api/drafts — live read of the NOVA Content Queue (Notion).
// Returns active drafts (Draft / Pending Review / Needs Revision) parsed into
// {pageId, name, hook, caption, platform, category, status, trigger}. The
// browser scores them with the same model used everywhere else.
//
// Requires env vars (see SETUP_LIVE.md):
//   NOTION_TOKEN         Notion internal integration secret (starts with "ntn_"/"secret_")
//   NOTION_DATABASE_ID   the Content Queue database id (or data source id)
//
// If the env vars are missing, responds 200 {configured:false} so the frontend
// silently falls back to the baked-in snapshot.

const NOTION_VERSION = "2022-06-28";
const ACTIVE = ["Draft", "Pending Review", "Needs Revision"];

function text(prop) {
  if (!prop) return "";
  const arr = prop.title || prop.rich_text || [];
  return arr.map((t) => t.plain_text).join("");
}
function sel(prop) { return (prop && prop.select && prop.select.name) || ""; }

function flattenDraftCaption(name, platform, category, status, hook, caption) {
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
  if (out.length === 0 && (dc || hook)) out.push({ hook: hook || "", caption: dc, trigger: "" });
  return out.map((v) => ({ name, platform, category, status, ...v }));
}

async function queryNotion(token, dbId) {
  const filter = { or: ACTIVE.map((s) => ({ property: "Status", select: { equals: s } })) };
  // Try the newer data-sources endpoint first, then fall back to databases.
  for (const url of [
    `https://api.notion.com/v1/data_sources/${dbId}/query`,
    `https://api.notion.com/v1/databases/${dbId}/query`,
  ]) {
    const r = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ filter, page_size: 100 }),
    });
    if (r.ok) return (await r.json()).results || [];
    if (r.status !== 404) throw new Error(`Notion ${r.status}: ${await r.text()}`);
  }
  throw new Error("Notion query failed on both data_sources and databases endpoints");
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
      flattenDraftCaption(
        text(pr.Name), sel(pr.Platform), sel(pr.Category), sel(pr.Status),
        text(pr.Hook), text(pr["Draft Caption"])
      ).forEach((d) => drafts.push({ pageId: p.id, ...d }));
    }
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ configured: true, count: drafts.length, drafts });
  } catch (e) {
    return res.status(500).json({ configured: true, error: String(e.message || e) });
  }
}
