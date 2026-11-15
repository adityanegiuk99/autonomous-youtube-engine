"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../lib/api";

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type Video = { id: string; content_idea_id: string; storyboard_version_id: string; status: string; created_at: string; duration_seconds: number; width: number; height: number; video_type: string; content_hash: string | null; preview_url: string; thumbnail_url: string | null; qa_report: { status?: string } | null };
type Approval = { id: string; video_id: string; content_hash: string; reviewer: string; decision: "approve" | "reject" | "request_changes"; review_checks: Record<string, boolean>; notes: string | null; created_at: string };
type ReviewItem = { video: Video; approval: Approval | null; mediaUrl: string; title: string };

export default function ApprovalsPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [checks, setChecks] = useState<Record<string, Record<string, boolean>>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState("");
  const mediaUrls = useRef<string[]>([]);

  const refresh = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [videoResponse, ideaResponse] = await Promise.all([apiFetch(`${api}/videos?limit=200`), apiFetch(`${api}/ideas`)]);
      const videoData = await videoResponse.json(); const ideaData = await ideaResponse.json();
      if (!videoResponse.ok) throw new Error(videoData.detail ?? "Could not load renders");
      if (!ideaResponse.ok) throw new Error(ideaData.detail ?? "Could not load content ideas");
      const production: Video[] = videoData.filter((video: Video) => video.video_type === "production");
      const ideaTitles = new Map(ideaData.map((idea: { id: string; title: string }) => [idea.id, idea.title]));
      const loaded = await Promise.all(production.map(async video => {
        const [approvalResponse, mediaResponse] = await Promise.all([
          apiFetch(`${api}/videos/${video.id}/approvals`), apiFetch(`${api}${video.preview_url.replace("/api/v1", "")}`),
        ]);
        const approvalData = approvalResponse.ok ? await approvalResponse.json() : [];
        const mediaUrl = mediaResponse.ok ? URL.createObjectURL(await mediaResponse.blob()) : "";
        return { video, approval: (approvalData as Approval[])[0] ?? null, mediaUrl, title: ideaTitles.get(video.content_idea_id) ?? "Untitled idea" };
      }));
      mediaUrls.current.forEach(URL.revokeObjectURL);
      mediaUrls.current = loaded.map(item => item.mediaUrl).filter(Boolean);
      setItems(loaded);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load approvals"); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { void refresh(); return () => { mediaUrls.current.forEach(URL.revokeObjectURL); }; }, [refresh]);

  async function decide(item: ReviewItem, decision: Approval["decision"]) {
    const videoId = item.video.id; setSaving(videoId); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/videos/${videoId}/approvals`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, review_checks: checks[videoId] ?? {}, notes: notes[videoId] || null }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Approval action failed");
      setMessage(`Decision recorded for ${item.title} · ${data.decision} · ${data.content_hash.slice(0, 12)}…`);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Approval action failed"); }
    finally { setSaving(""); }
  }

  const reviewItems = [
    ["editorial_accuracy_reviewed", "I reviewed factual claims and editorial accuracy."],
    ["sources_reviewed", "I reviewed source links and attribution."],
    ["media_rights_reviewed", "I reviewed asset rights and license terms."],
    ["disclosures_reviewed", "I reviewed required synthetic-content disclosures."],
  ] as const;

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Approval Center</h2><p className="muted">Review saved production renders and their immutable human decisions.</p></div><button className="secondary" onClick={() => void refresh()} disabled={busy}>Refresh</button></div>
    <p className="trend-method">Technical QA is not editorial approval. Decisions apply to one exact content hash; changing content requires a new render and review.</p>
    {busy && <p className="muted">Loading production renders…</p>}{error && <p className="error-message">{error}</p>}{message && <p className="success-message">{message}</p>}
    {!busy && !items.length && <article className="empty-card channel-empty"><h3>No production renders yet</h3><p>Render a production video in Studio to make it available for review here.</p><a className="secondary" href="/studio">Open Video Studio</a></article>}
    <div className="approval-list">{items.map(item => {
      const id = item.video.id; const decision = item.approval;
      const passed = item.video.qa_report?.status === "TECHNICAL_QA_PASSED";
      const complete = Object.values(checks[id] ?? {}).length === 4 && Object.values(checks[id] ?? {}).every(Boolean);
      return <article className="studio-panel approval-card" key={id}>
        <div className="studio-panel-title"><div><h3>{item.title}</h3><span>{new Date(item.video.created_at).toLocaleString()} · {item.video.duration_seconds.toFixed(1)} sec · {item.video.width}×{item.video.height}</span></div><strong className="approval-state">{decision?.decision ?? item.video.status}</strong></div>
        {item.mediaUrl ? <video controls preload="metadata" src={item.mediaUrl} /> : <p className="error-message">Rendered media is unavailable for review.</p>}
        {item.video.content_hash && <small className="content-fingerprint">Content fingerprint: {item.video.content_hash}</small>}
        {decision ? <div className="approval-record"><strong>Final decision: {decision.decision}</strong><p>Recorded {new Date(decision.created_at).toLocaleString()} · reviewer {decision.reviewer}</p>{decision.notes && <p>Notes: {decision.notes}</p>}<small>Decision hash: {decision.content_hash}</small></div> : <>
          {!passed && <p className="error-message">Technical QA did not pass. This render cannot be approved.</p>}
          <div className="approval-panel"><h4>Human approval</h4><p>Review the rendered video, source links, asset provenance, and disclosure requirements.</p>
            {reviewItems.map(([key, label]) => <label className="review-check" key={key}><input type="checkbox" checked={Boolean(checks[id]?.[key])} onChange={event => setChecks(current => ({ ...current, [id]: { ...current[id], [key]: event.target.checked } }))} />{label}</label>)}
            <label className="review-notes">Notes<textarea value={notes[id] ?? ""} onChange={event => setNotes(current => ({ ...current, [id]: event.target.value }))} placeholder="Required if rejecting or requesting changes" /></label>
            <div className="studio-actions"><button className="secondary" disabled={!passed || saving === id || !(notes[id] ?? "").trim()} onClick={() => void decide(item, "request_changes")}>Request changes</button><button className="secondary reject-button" disabled={!passed || saving === id || !(notes[id] ?? "").trim()} onClick={() => void decide(item, "reject")}>Reject</button><button className="primary" disabled={!passed || !complete || saving === id} onClick={() => void decide(item, "approve")}>{saving === id ? "Saving…" : "Approve this version"}</button></div>
          </div>
        </>}
      </article>;
    })}</div>
  </main>;
}
