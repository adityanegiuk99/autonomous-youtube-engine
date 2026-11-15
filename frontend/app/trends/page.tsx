"use client";

import { useEffect, useState, type FormEvent } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Trend = { id: string; title: string; summary: string | null; source_urls: string[]; article_urls: string[]; trend_score: number; published_at: string | null; first_seen_at: string };
type Discovery = { attempted_feeds: number; successful_feeds: number; items_added: number; items_updated: number; errors: string[] };
type ResearchPack = { version: number; content: { topic: string; rss_synopsis: string | null; synopsis_source_feed: string | null; references: string[]; observed_in_feeds: string[]; verification_status: string; note: string } };
type ClaimDraft = { statement: string; assessment: string; assessment_note: string; references: { source_title: string; source_url: string; excerpt: string }[] };
type SavedDossier = { id: string; version: number; document_type: string; created_at: string; content: { topic: string; summary?: string; claims?: { statement: string; assessment: string; assessment_note: string | null; references: { source_url: string; source_title: string; excerpt: string | null }[] }[]; open_questions?: string[]; note: string } };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

function draftFromDossier(doc: SavedDossier) {
  return {
    summary: doc.content.summary ?? "",
    claims: (doc.content.claims ?? []).map(c => ({
      statement: c.statement,
      assessment: c.assessment,
      assessment_note: c.assessment_note ?? "",
      references: c.references.map(r => ({ source_title: r.source_title, source_url: r.source_url, excerpt: r.excerpt ?? "" })),
    })),
    openQuestions: (doc.content.open_questions ?? []).join("\n"),
  };
}

export default function TrendsPage() {
  const [items, setItems] = useState<Trend[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pack, setPack] = useState<ResearchPack | null>(null);
  const [dossierTrend, setDossierTrend] = useState<Trend | null>(null);
  const [summary, setSummary] = useState("");
  const [claims, setClaims] = useState<ClaimDraft[]>([{ statement: "", assessment: "unreviewed", assessment_note: "", references: [{ source_title: "", source_url: "", excerpt: "" }] }]);
  const [openQuestions, setOpenQuestions] = useState("");
  const [savedDossiers, setSavedDossiers] = useState<SavedDossier[]>([]);
  const [selectedDossier, setSelectedDossier] = useState<SavedDossier | null>(null);

  async function load() {
    try {
      const response = await apiFetch(`${api}/trends`);
      if (!response.ok) throw new Error();
      setItems(await response.json());
    } catch { setError("Could not load trends. Check that the API is running."); }
  }
  useEffect(() => { void load(); }, []);

  async function discover() {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/trends/discover`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Discovery failed");
      const result = data as Discovery;
      setMessage(`Checked ${result.successful_feeds} of ${result.attempted_feeds} feeds · ${result.items_added} new · ${result.items_updated} updated`);
      if (result.errors.length) setError(result.errors.join("; "));
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Discovery failed"); }
    finally { setBusy(false); }
  }

  async function buildSourcePack(id: string) {
    setError(""); setPack(null);
    try {
      const response = await apiFetch(`${api}/research/trends/${id}/source-packs`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not create source pack");
      setPack(data); setMessage(`Saved source pack version ${data.version}. RSS claims have not been independently verified.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create source pack"); }
  }

  async function openDossierEditor(item: Trend) {
    setDossierTrend(item); setSummary(""); setOpenQuestions("");
    setClaims([{ statement: "", assessment: "unreviewed", assessment_note: "", references: [{ source_title: "", source_url: "", excerpt: "" }] }]);
    setSelectedDossier(null); setSavedDossiers([]); setError("");
    try {
      const response = await apiFetch(`${api}/research/trends/${item.id}`);
      if (!response.ok) throw new Error("Could not load saved research versions");
      const docs = (await response.json()) as SavedDossier[];
      const dossiers = docs.filter(doc => doc.document_type === "manual_research_dossier");
      setSavedDossiers(dossiers);
      if (dossiers.length) {
        setSelectedDossier(dossiers[0]);
        const draft = draftFromDossier(dossiers[0]);
        setSummary(draft.summary); setClaims(draft.claims); setOpenQuestions(draft.openQuestions);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load saved research versions"); }
  }

  async function saveDossier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dossierTrend) return;
    setError("");
    try {
      const response = await apiFetch(`${api}/research/trends/${dossierTrend.id}/dossiers`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary, claims: claims.map(c => ({ ...c, assessment_note: c.assessment_note || null, references: c.references.map(r => ({ ...r, excerpt: r.excerpt || null })) })), open_questions: openQuestions.split("\n").map(q => q.trim()).filter(Boolean) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(Array.isArray(data.detail) ? data.detail[0]?.msg ?? "Invalid dossier" : data.detail ?? "Could not save dossier");
      setSavedDossiers(current => [data, ...current]); setSelectedDossier(data); setMessage(`Saved manual evidence dossier version ${data.version}. AYE has not independently verified it.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save dossier"); }
  }

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Trend Radar</h2><p className="muted">RSS headlines normalized and deduplicated across your configured feeds.</p></div><button className="primary" onClick={discover} disabled={busy}>{busy ? "Checking feeds…" : "↻  Discover trends"}</button></div>
    <p className="trend-method">Trend score uses source diversity (up to 60) and feed recency (up to 40). It is a simple heuristic, not a prediction of views.</p>
    {message && <p className="success-message">{message}</p>}{error && <p className="error-message">{error}</p>}
    {items.length ? <div className="trend-list">{items.map(item => <article className="trend-card" key={item.id}><div className="score-pill">{Math.round(item.trend_score)}<small>SCORE</small></div><div className="trend-body"><h3>{item.title}</h3>{item.summary && <p>{item.summary}</p>}<div className="trend-meta">{item.source_urls.length} source{item.source_urls.length === 1 ? "" : "s"} · {item.published_at ? new Date(item.published_at).toLocaleDateString() : "date unavailable"}</div>{item.article_urls.length > 0 && <div className="source-links">{item.article_urls.slice(0, 3).map((url, i) => <a href={url} target="_blank" rel="noreferrer" key={url}>Source {i + 1} ↗</a>)}</div>}<button className="source-pack-button" onClick={() => buildSourcePack(item.id)}>Save source pack</button> <button className="source-pack-button" onClick={() => void openDossierEditor(item)}>Research dossier</button></div></article>)}</div> : <article className="empty-card channel-empty"><div className="empty-icon">◉</div><h3>No trend items yet</h3><p>Configure trusted HTTPS RSS feeds with <code>AYE_RSS_FEED_URLS</code>, then run discovery.</p></article>}
    {dossierTrend && <article className="studio-panel source-pack"><h3>Manual evidence dossier: {dossierTrend.title}</h3><p>Record claims and their citations. AYE stores your assessment but does not check the source.</p>{savedDossiers.length > 0 && <label>Saved version<select value={selectedDossier?.id ?? ""} onChange={e => { const doc = savedDossiers.find(d => d.id === e.target.value); setSelectedDossier(doc ?? null); if (doc) { const draft = draftFromDossier(doc); setSummary(draft.summary); setClaims(draft.claims); setOpenQuestions(draft.openQuestions); } }}>{savedDossiers.map(d => <option value={d.id} key={d.id}>Version {d.version} · {new Date(d.created_at).toLocaleString()}</option>)}</select></label>}<form onSubmit={saveDossier}><label>Research summary<textarea required maxLength={4000} value={summary} onChange={e => setSummary(e.target.value)} /></label>{claims.map((c, ci) => <div className="scene-editor" key={ci}><div className="studio-panel-title"><strong>Claim {ci + 1}</strong>{claims.length > 1 && <button type="button" className="remove-scene" onClick={() => setClaims(current => current.filter((_, i) => i !== ci))}>Remove</button>}</div><label>Claim statement<textarea required maxLength={2000} value={c.statement} onChange={e => setClaims(current => current.map((x, i) => i === ci ? { ...x, statement: e.target.value } : x))} /></label><label>Human assessment<select value={c.assessment} onChange={e => setClaims(current => current.map((x, i) => i === ci ? { ...x, assessment: e.target.value, assessment_note: e.target.value === "unreviewed" ? "" : x.assessment_note } : x))}><option value="unreviewed">Unreviewed</option><option value="human_supports_cited_sources">Human: sources support claim</option><option value="human_found_conflict">Human: found conflicting sources</option><option value="human_found_insufficient_support">Human: insufficient support</option></select></label>{c.assessment !== "unreviewed" && <label>Assessment note (required)<textarea required maxLength={2000} value={c.assessment_note} onChange={e => setClaims(current => current.map((x, i) => i === ci ? { ...x, assessment_note: e.target.value } : x))} /></label>}{c.references.map((ref, ri) => <div key={ri}><label>Source title<input required maxLength={300} value={ref.source_title} onChange={e => setClaims(current => current.map((x, i) => i === ci ? { ...x, references: x.references.map((r, j) => j === ri ? { ...r, source_title: e.target.value } : r) } : x))} /></label><label>Source URL (HTTPS)<input required type="url" value={ref.source_url} onChange={e => setClaims(current => current.map((x, i) => i === ci ? { ...x, references: x.references.map((r, j) => j === ri ? { ...r, source_url: e.target.value } : r) } : x))} /></label><label>Relevant excerpt (optional)<textarea maxLength={2000} value={ref.excerpt} onChange={e => setClaims(current => current.map((x, i) => i === ci ? { ...x, references: x.references.map((r, j) => j === ri ? { ...r, excerpt: e.target.value } : r) } : x))} /></label>{c.references.length > 1 && <button type="button" className="remove-scene" onClick={() => setClaims(current => current.map((x, i) => i === ci ? { ...x, references: x.references.filter((_, j) => j !== ri) } : x))}>Remove citation</button>}</div>)}<button type="button" className="secondary" disabled={c.references.length >= 8} onClick={() => setClaims(current => current.map((x, i) => i === ci ? { ...x, references: [...x.references, { source_title: "", source_url: "", excerpt: "" }] } : x))}>Add citation</button></div>)}<button type="button" className="secondary" disabled={claims.length >= 50} onClick={() => setClaims(current => [...current, { statement: "", assessment: "unreviewed", assessment_note: "", references: [{ source_title: "", source_url: "", excerpt: "" }] }])}>Add claim</button><label>Open questions (one per line)<textarea maxLength={15000} value={openQuestions} onChange={e => setOpenQuestions(e.target.value)} /></label>{openQuestions.split("\n").filter(q => q.trim()).length > 30 && <p className="error-message">Keep open questions to 30 or fewer.</p>}<button className="primary" type="submit" disabled={openQuestions.split("\n").filter(q => q.trim()).length > 30}>Save new dossier version</button></form></article>}
    {selectedDossier && <article className="studio-panel source-pack"><div className="studio-panel-title"><h3>{selectedDossier.content.topic}</h3><span>MANUAL DOSSIER v{selectedDossier.version}</span></div><p>{selectedDossier.content.summary}</p><p>{selectedDossier.content.note}</p>{selectedDossier.content.claims?.map((c, i) => <div className="scene-editor" key={i}><strong>{c.statement}</strong><p>Assessment: {c.assessment}{c.assessment_note ? ` — ${c.assessment_note}` : ""}</p>{c.references.map(ref => <div key={ref.source_url}><div className="source-links"><a href={ref.source_url} target="_blank" rel="noreferrer">{ref.source_title} ↗</a></div>{ref.excerpt && <small>{ref.excerpt}</small>}</div>)}</div>)}{selectedDossier.content.open_questions?.length ? <><strong>Open questions</strong><ul>{selectedDossier.content.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul></> : null}</article>}
    {pack && <article className="studio-panel source-pack"><div className="studio-panel-title"><h3>{pack.content.topic}</h3><span>SOURCE PACK v{pack.version}</span></div><p>{pack.content.note}</p><strong>RSS synopsis</strong><p>{pack.content.rss_synopsis || "No synopsis in feed."}</p><small>Synopsis feed: {pack.content.synopsis_source_feed || "Unavailable"}</small><p>Verification: <b>{pack.content.verification_status}</b></p><div className="source-links">{pack.content.references.map((url, i) => <a href={url} target="_blank" rel="noreferrer" key={url}>Article {i + 1} ↗</a>)}</div></article>}
  </main>;
}
