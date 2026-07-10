// GET /api/config — live read of NOVA (Notion) "intent" data that should be the
// single source of truth for the dashboard's editable strategy:
//   • Engagement Targets   (per-platform benchmarks)
//   • Content Matrix        (character × job coverage, tallied from the Queue)
//   • SOPs                  (standard operating procedures, read-only)
//
// Analytics (reach, ER, themes) intentionally stay on the weekly Metricool bake
// — Notion is the wrong store for 133 rows of metrics. This endpoint only serves
// the small, hand-edited config the user owns.
//
// Env vars (all optional — each block degrades to null so the dashboard falls
// back to its baked-in Phase 1 values; see SETUP_LIVE.md):
//   NOTION_TOKEN         Notion internal integration secret (required for any live data)
//   NOTION_DATABASE_ID   Content Queue db/data-source id (matrix coverage is tallied from it)
//   NOTION_TARGETS_DB    Engagement Targets db/data-source id
//   NOTION_SOPS_DB       SOPs db/data-source id
//
// If NOTION_TOKEN is missing, responds 200 {configured:false} so the frontend
// silently keeps its fallback. Cached ~60s at the edge (Notion rate limit safe).

const NOTION_VERSION = "2022-06-28";

// Canonical labels — MUST match the dashboard's viewMatrix()/viewTargets().
const CHARACTERS = ["REALTOR®", "Entrepreneur", "Soft Luxury Experience Curator", "Atlanta Native"];
const JOBS = ["Entertain", "Educate", "Encourage"];

function text(prop) {
  if (!prop) return "";
  const arr = prop.title || prop.rich_text || [];
  return arr.map((t) => t.plain_text).join("");
}
function sel(prop) { return (prop && prop.select && prop.select.name) || ""; }
function multi(prop) { return (prop && prop.multi_select ? prop.multi_select.map((s) => s.name) : []); }
function num(prop) { return prop && typeof prop.number === "number" ? prop.number : null; }

// Map a free-text Notion option onto a canonical label (case-insensitive keywords).
function canonChar(s) {
  const t = (s || "").toLowerCase();
  if (t.includes("realtor")) return "REALTOR®";
  if (t.includes("entrepreneur")) return "Entrepreneur";
  if (t.includes("curator") || t.includes("luxury") || t.includes("experience")) return "Soft Luxury Experience Curator";
  if (t.includes("atlanta") || t.includes("native") || t.includes("local")) return "Atlanta Native";
  return null;
}
function canonJob(s) {
  const t = (s || "").toLowerCase();
  if (t.includes("entertain")) return "Entertain";
  if (t.includes("educat")) return "Educate";
  if (t.includes("encourag")) return "Encourage";
  return null;
}

async function queryAll(token, dbId) {
  // Try the newer data-sources endpoint first, then fall back to databases.
  // Paginates through every page.
  const urls = [
    `https://api.notion.com/v1/data_sources/${dbId}/query`,
    `https://api.notion.com/v1/databases/${dbId}/query`,
  ];
  let lastErr;
  for (const url of urls) {
    const out = [];
    let cursor;
    try {
      do {
        const r = await fetch(url, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(cursor ? { page_size: 100, start_cursor: cursor } : { page_size: 100 }),
        });
        if (!r.ok) {
          if (r.status === 404) { lastErr = new Error("404"); out.length = 0; break; }
          throw new Error(`Notion ${r.status}: ${await r.text()}`);
        }
        const j = await r.json();
        out.push(...(j.results || []));
        cursor = j.has_more ? j.next_cursor : null;
      } while (cursor);
      if (out.length || lastErr === undefined) return out; // success (even if empty) unless it was a 404
    } catch (e) { lastErr = e; }
  }
  if (lastErr && String(lastErr.message) !== "404") throw lastErr;
  return [];
}

async function loadTargets(token, dbId) {
  if (!dbId) return null;
  const pages = await queryAll(token, dbId);
  const rows = [];
  for (const p of pages) {
    const pr = p.properties || {};
    const platform = text(pr.Platform || pr.Name) || sel(pr.Platform);
    if (!platform) continue;
    const lo = num(pr["Target Low"]) ?? num(pr.Target) ?? num(pr["Target %"]);
    const hi = num(pr["Target High"]) ?? lo;
    rows.push({ platform, lo, hi: hi ?? lo, note: text(pr.Notes) });
  }
  return rows.length ? rows : null;
}

async function loadMatrix(token, dbId) {
  if (!dbId) return null;
  const pages = await queryAll(token, dbId);
  const cells = {};
  let tagged = 0;
  for (const p of pages) {
    const pr = p.properties || {};
    // Character can be single- or multi-select; Job is single-select.
    const rawChars = multi(pr.Character).length ? multi(pr.Character) : [sel(pr.Character)];
    const job = canonJob(sel(pr.Job) || text(pr.Job));
    if (!job) continue;
    let counted = false;
    for (const rc of rawChars) {
      const ch = canonChar(rc);
      if (!ch) continue;
      cells[`${ch}|${job}`] = (cells[`${ch}|${job}`] || 0) + 1;
      counted = true;
    }
    if (counted) tagged++;
  }
  return Object.keys(cells).length ? { cells, tagged } : null;
}

async function loadSops(token, dbId) {
  if (!dbId) return null;
  const pages = await queryAll(token, dbId);
  const out = [];
  for (const p of pages) {
    const pr = p.properties || {};
    const title = text(pr.Name || pr.Title);
    if (!title) continue;
    out.push({ title, trigger: text(pr.Trigger) || sel(pr.Trigger), body: text(pr.Body || pr.Description) });
  }
  return out.length ? out : null;
}

export default async function handler(req, res) {
  const token = process.env.NOTION_TOKEN;
  if (!token) return res.status(200).json({ configured: false });
  try {
    const [targets, matrix, sops] = await Promise.all([
      loadTargets(token, process.env.NOTION_TARGETS_DB).catch(() => null),
      loadMatrix(token, process.env.NOTION_DATABASE_ID).catch(() => null),
      loadSops(token, process.env.NOTION_SOPS_DB).catch(() => null),
    ]);
    res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=120");
    return res.status(200).json({
      configured: true,
      characters: CHARACTERS,
      jobs: JOBS,
      targets, matrix, sops,
    });
  } catch (e) {
    return res.status(500).json({ configured: true, error: String(e.message || e) });
  }
}
