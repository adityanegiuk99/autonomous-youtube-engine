"use client";

import { FormEvent, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Channel = { id: string; name: string };
type Summary = { video_count: number; sample_size: string; data_window_start: string | null; latest_snapshot_at: string | null; views_total: number; impressions_total: number; weighted_ctr_percent: number | null; watch_time_minutes_total: number; average_view_duration_seconds: number | null; top_videos: { video_id: string; views: number; average_view_duration_seconds: number }[]; interpretation: string };
type Insights = { video_count: number; evidence_strength: string; basis: string; caveat: string; signals: { metric: string; top_view_group_median: number; lower_view_group_median: number; difference_percent: number | null; direction: string }[]; suggested_review: string | null };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const number = (value: number) => new Intl.NumberFormat().format(value);
const decimal = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);

export default function AnalyticsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [channelId, setChannelId] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadChannels() {
    try {
      const response = await apiFetch(`${api}/channels`);
      if (!response.ok) throw new Error("Could not load channels");
      const items: Channel[] = await response.json(); setChannels(items);
      setChannelId(current => current || items[0]?.id || "");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load channels"); }
  }
  useEffect(() => { void loadChannels(); }, []);

  async function loadSummary(id: string) {
    if (!id) { setSummary(null); return; }
    try {
      const response = await apiFetch(`${api}/analytics/channels/${id}`);
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not load analytics");
      setSummary(data); setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load analytics"); }
  }
  useEffect(() => { void loadSummary(channelId); }, [channelId]);

  async function loadInsights(id: string) {
    if (!id) { setInsights(null); return; }
    try {
      const response = await apiFetch(`${api}/analytics/channels/${id}/insights`);
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not load learning insights");
      setInsights(data);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load learning insights"); }
  }
  useEffect(() => { void loadInsights(channelId); }, [channelId]);

  async function importCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!channelId) return;
    setBusy(true); setError(""); setMessage("");
    const form = event.currentTarget;
    try {
      const response = await apiFetch(`${api}/analytics/import?channel_id=${channelId}`, { method: "POST", body: new FormData(form) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Import failed");
      setMessage(`Imported ${data.rows_imported} new rows and updated ${data.rows_updated} existing rows from this CSV.`); form.reset(); await Promise.all([loadSummary(channelId), loadInsights(channelId)]);
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed"); }
    finally { setBusy(false); }
  }

  async function downloadTemplate() {
    try {
      const response = await apiFetch(`${api}/analytics/csv-template`);
      if (!response.ok) throw new Error("Could not download the template");
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = objectUrl; link.download = "aye-analytics-template.csv"; link.click(); window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not download template"); }
  }

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Analytics</h2><p className="muted">Import a YouTube Analytics export to see descriptive channel totals.</p></div></div>
    <p className="trend-method">No live YouTube Analytics connection is configured. Imports are user-provided cumulative snapshots; summaries use the latest row for each video and do not infer causality.</p>
    <div className="analytics-controls"><label>Channel<select value={channelId} onChange={event => setChannelId(event.target.value)}><option value="">Choose a channel</option>{channels.map(channel => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></label><button className="secondary" onClick={downloadTemplate}>Download CSV template</button></div>
    <form className="asset-form analytics-upload" onSubmit={importCsv}><label>Analytics CSV<input type="file" name="file" accept=".csv,text/csv" required /></label><p>Use cumulative snapshots with one row per video and collection date. Maximum 5 MB and 5,000 rows.</p><button className="primary" disabled={!channelId || busy}>{busy ? "Importing…" : "Import analytics"}</button></form>
    {message && <p className="success-message">{message}</p>}{error && <p className="error-message">{error}</p>}
    {summary && summary.video_count > 0 && <><div className="stats-grid analytics-stats">{[["VIDEOS IN SAMPLE", number(summary.video_count)], ["LATEST VIEWS TOTAL", number(summary.views_total)], ["IMPRESSION TOTAL", number(summary.impressions_total)], ["WEIGHTED CTR", summary.weighted_ctr_percent === null ? "—" : `${summary.weighted_ctr_percent.toFixed(2)}%`], ["WATCH TIME", `${(summary.watch_time_minutes_total / 60).toFixed(1)} hrs`], ["AVG VIEW DURATION", summary.average_view_duration_seconds === null ? "—" : `${summary.average_view_duration_seconds.toFixed(1)} sec`]].map(([label, value]) => <article className="stat-card" key={label}><div className="stat-title">{label}</div><div className="stat-value">{value}</div></article>)}</div><article className="analytics-note"><strong>Sample: {summary.sample_size}</strong><p>{summary.interpretation}</p><small>Snapshot window: {summary.data_window_start ? new Date(summary.data_window_start).toLocaleDateString() : "—"} to {summary.latest_snapshot_at ? new Date(summary.latest_snapshot_at).toLocaleDateString() : "—"}</small></article><div className="section-heading"><div><h2>Top imported videos</h2><p className="muted">Sorted by latest imported view count.</p></div></div><div className="channel-list">{summary.top_videos.map((item, index) => <article className="channel-row" key={item.video_id}><span className="video-rank">{String(index + 1).padStart(2, "0")}</span><div><strong>{number(item.views)} views</strong><p>{item.average_view_duration_seconds.toFixed(1)} sec average view duration · ID {item.video_id}</p></div><a className="text-button" href={`https://www.youtube.com/watch?v=${encodeURIComponent(item.video_id)}`} target="_blank" rel="noreferrer">Open video ↗</a></article>)}</div></>}
    {insights && <section className="learning-panel"><div className="section-heading"><div><h2>Learning hypotheses</h2><p className="muted">Descriptive signals from imported history, not automated strategy changes.</p></div><span className="learning-strength">{insights.evidence_strength} evidence · {insights.video_count} videos</span></div><p className="trend-method">{insights.caveat}</p>{insights.signals.length ? <><p className="muted">{insights.basis}</p><div className="learning-signals">{insights.signals.map(signal => <article className="analytics-note" key={signal.metric}><strong>{signal.metric}: {signal.direction} in higher-view group</strong><p>Median {decimal(signal.top_view_group_median)} for the highest-view group vs {decimal(signal.lower_view_group_median)} for the lowest-view group{signal.difference_percent === null ? " (lower group median is zero)" : ` (${Math.abs(signal.difference_percent)}% ${signal.direction})`}.</p></article>)}</div>{insights.suggested_review && <p className="learning-suggestion">{insights.suggested_review}</p>}</> : <p className="muted">{insights.video_count < 10 ? "Import at least 10 videos before this page offers exploratory comparisons." : "No difference was observed in the compared metrics for these groups."}</p>}</section>}
    {summary && summary.video_count === 0 && <article className="empty-card channel-empty"><div className="empty-icon">▥</div><h3>No analytics imported for this channel</h3><p>Upload a normalized YouTube Analytics CSV export to build a snapshot summary.</p></article>}
  </main>;
}
