"use client";

import { useEffect, useState, type FormEvent } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Trend = { id: string; title: string; summary: string | null; source_urls: string[]; article_urls: string[]; trend_score: number; published_at: string | null; first_seen_at: string };
type Discovery = { attempted_feeds: number; successful_feeds: number; items_added: number; items_updated: number; errors: string[] };
type ResearchPack = { version: number; content: { topic: string; rss_synopsis: string | null; synopsis_source_feed: string | null; references: string[]; observed_in_feeds: string[]; verification_status: string; note: string } };
type SavedDossier = { version: number; content: { topic: string; summary: string; claims: { statement: string; assessment: string; assessment_note: string | null; references: { source_url: string; source_title: string; excerpt: string | null }[] }[]; open_questions: string[]; note: string } };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function TrendsPage() {
  const [items, setItems] = useState<Trend[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pack, setPack] = useState<ResearchPack | null>(null);
  const [dossierTrend, setDossierTrend] = useState<Trend | null>(null);
  const [claim, setClaim] = useState("");
  const [summary, setSummary] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [assessment, setAssessment] = useState("unreviewed");
  const [assessmentNote, setAssessmentNote] = useState("");
  const [dossier, setDossier] = useState<SavedDossier | null>(null);

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

  async function saveDossier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dossierTrend) return;
    setError("");
    try {
      const response = await apiFetch(`${api}/research/trends/${dossierTrend.id}/dossiers`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary, claims: [{ statement: claim, assessment, assessment_note: assessmentNote || null, references: [{ source_title: sourceTitle, source_url: sourceUrl }] }], open_questions: [] }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.[0]?.msg ?? data.detail ?? "Could not save dossier");
      setDossier(data); setMessage(`Saved manual evidence dossier version ${data.version}. AYE has not independently verified it.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save dossier"); }
  }

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Trend Radar</h2><p className="muted">RSS headlines normalized and deduplicated across your configured feeds.</p></div><button className="primary" onClick={discover} disabled={busy}>{busy ? "Checking feeds…" : "↻  Discover trends"}</button></div>
    <p className="trend-method">Trend score uses source diversity (up to 60) and feed recency (up to 40). It is a simple heuristic, not a prediction of views.</p>
    {message && <p className="success-message">{message}</p>}{error && <p className="error-message">{error}</p>}
    {items.length ? <div className="trend-list">{items.map(item => <article className="trend-card" key={item.id}><div className="score-pill">{Math.round(item.trend_score)}<small>SCORE</small></div><div className="trend-body"><h3>{item.title}</h3>{item.summary && <p>{item.summary}</p>}<div className="trend-meta">{item.source_urls.length} source{item.source_urls.length === 1 ? "" : "s"} · {item.published_at ? new Date(item.published_at).toLocaleDateString() : "date unavailable"}</div>{item.article_urls.length > 0 && <div className="source-links">{item.article_urls.slice(0, 3).map((url, i) => <a href={url} target="_blank" rel="noreferrer" key={url}>Source {i + 1} ↗</a>)}</div>}<button className="source-pack-button" onClick={() => buildSourcePack(item.id)}>Save source pack</button> <button className="source-pack-button" onClick={() => { setDossierTrend(item); setDossier(null); setClaim(""); setSummary(""); }}>Build manual dossier</button></div></article>)}</div> : <article className="empty-card channel-empty"><div className="empty-icon">◉</div><h3>No trend items yet</h3><p>Configure trusted HTTPS RSS feeds with <code>AYE_RSS_FEED_URLS</code>, then run discovery.</p></article>}
    {dossierTrend && <article className="studio-panel source-pack"><h3>Manual evidence dossier: {dossierTrend.title}</h3><p>Record one claim and its citation. AYE stores your assessment but does not check the source.</p><form onSubmit={saveDossier}><label>Research summary<textarea required maxLength={4000} value={summary} onChange={e => setSummary(e.target.value)} /></label><label>Claim statement<textarea required maxLength={2000} value={claim} onChange={e => setClaim(e.target.value)} /></label><label>Source title<input required maxLength={300} value={sourceTitle} onChange={e => setSourceTitle(e.target.value)} /></label><label>Source URL (HTTPS)<input required type="url" value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} /></label><label>Human assessment<select value={assessment} onChange={e => setAssessment(e.target.value)}><option value="unreviewed">Unreviewed</option><option value="human_supports_cited_sources">Human: sources support claim</option><option value="human_found_conflict">Human: found conflicting sources</option><option value="human_found_insufficient_support">Human: insufficient support</option></select></label>{assessment !== "unreviewed" && <label>Assessment note (required)<textarea required maxLength={2000} value={assessmentNote} onChange={e => setAssessmentNote(e.target.value)} /></label>}<button className="primary" type="submit">Save dossier version</button></form></article>}
    {dossier && <article className="studio-panel source-pack"><div className="studio-panel-title"><h3>{dossier.content.topic}</h3><span>MANUAL DOSSIER v{dossier.version}</span></div><p>{dossier.content.summary}</p><p>{dossier.content.note}</p>{dossier.content.claims.map((c, i) => <div key={i}><strong>{c.statement}</strong><p>Assessment: {c.assessment}{c.assessment_note ? ` — ${c.assessment_note}` : ""}</p><div className="source-links">{c.references.map(ref => <a href={ref.source_url} target="_blank" rel="noreferrer" key={ref.source_url}>{ref.source_title} ↗</a>)}</div></div>)}</article>}
    {pack && <article className="studio-panel source-pack"><div className="studio-panel-title"><h3>{pack.content.topic}</h3><span>SOURCE PACK v{pack.version}</span></div><p>{pack.content.note}</p><strong>RSS synopsis</strong><p>{pack.content.rss_synopsis || "No synopsis in feed."}</p><small>Synopsis feed: {pack.content.synopsis_source_feed || "Unavailable"}</small><p>Verification: <b>{pack.content.verification_status}</b></p><div className="source-links">{pack.content.references.map((url, i) => <a href={url} target="_blank" rel="noreferrer" key={url}>Article {i + 1} ↗</a>)}</div></article>}
  </main>;
}
