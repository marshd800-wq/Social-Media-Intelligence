// POST /api/schedule — advance a Content Queue draft in NOVA (Notion).
// Body: { pageId, caption?, status, scheduledDate? }
//   status         one of the Content Queue Status options, e.g. "Approved" | "Scheduled"
//   scheduledDate  ISO date (YYYY-MM-DD), optional
//   caption        the improved caption to save back, optional
//
// This is the safe "send to post" action: it moves the card forward in NOVA's
// own workflow (Draft -> Approved/Scheduled) and stamps the date, so it flows
// into the existing production/publish process. It does NOT auto-publish to a
// network (that needs the media asset, handled downstream in Metricool).
//
// Requires NOTION_TOKEN (same integration as api/drafts).

const NOTION_VERSION = "2022-06-28";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const token = process.env.NOTION_TOKEN;
  if (!token) return res.status(200).json({ configured: false });

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch { body = {}; } }
  const { pageId, caption, status, scheduledDate } = body || {};
  if (!pageId || !status) return res.status(400).json({ error: "pageId and status are required" });

  const properties = { Status: { select: { name: status } } };
  if (scheduledDate) properties["Scheduled Date"] = { date: { start: scheduledDate } };
  if (caption) properties["Draft Caption"] = { rich_text: [{ text: { content: caption.slice(0, 1900) } }] };

  try {
    const r = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ properties }),
    });
    if (!r.ok) return res.status(500).json({ error: `Notion ${r.status}: ${await r.text()}` });
    return res.status(200).json({ ok: true, status, scheduledDate: scheduledDate || null });
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
}
