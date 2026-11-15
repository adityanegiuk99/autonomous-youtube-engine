"use client";

import { FormEvent, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Channel = { id: string; name: string };
type Summary = { video_count: number; sample_size: string; data_window_start: string | null; latest_snapshot_at: string | null; views_total: number; impressions_total: number; weighted_ctr_percent: number | null; watch_time_minutes_total: number; average_view_duration_seconds: number | null; top_videos: { video_id: string; views: number; average_view_duration_seconds: number }[]; interpretation: string };
type Insights = { video_count: number; evidence_strength: string; basis: string; caveat: string; signals: { metric: string; top_view_group_median: number; lower_view_group_median: number; difference_percent: number | null; direction: string }[]; suggested_review: string | null };
type Experiment = { id: string; title: string; hypothesis: string; variable: string; control_description: string; treatment_description: string; metric: string; status: "planned" | "running" | "completed" | "cancelled"; control_video_ids: string[]; treatment_video_ids: string[]; notes: string | null; control_sample_size: number; treatment_sample_size: number; control_median: number | null; treatment_median: number | null; difference_percent: number | null; caveat: string };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const number = (value: number) => new Intl.NumberFormat().format(value);
const decimal = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
const experimentMetrics = ["views", "click_through_rate_percent", "average_view_duration_seconds", "watch_time_minutes", "likes", "comments", "subscribers_gained"] as const;
const metricLabel = (metric: string) => ({ views: "Views", click_through_rate_percent: "Click-through rate (%)", average_view_duration_seconds: "Average view duration (seconds)", watch_time_minutes: "Watch time (minutes)", likes: "Likes", comments: "Comments", subscribers_gained: "Subscribers gained" }[metric] ?? metric);

export default function AnalyticsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [channelId, setChannelId] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimentBusy, setExperimentBusy] = useState(false);
  const [experimentTitle, setExperimentTitle] = useState("");
  const [experimentHypothesis, setExperimentHypothesis] = useState("");
  const [experimentVariable, setExperimentVariable] = useState("title");
  const [controlDescription, setControlDescription] = useState("");
  const [treatmentDescription, setTreatmentDescription] = useState("");
  const [experimentMetric, setExperimentMetric] = useState<string>("click_through_rate_percent");
  const [controlVideoIds, setControlVideoIds] = useState("");
  const [treatmentVideoIds, setTreatmentVideoIds] = useState("");
  const [experimentNotes, setExperimentNotes] = useState("");

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

  async function loadExperiments(id: string) {
    if (!id) { setExperiments([]); return; }
    try {
      const response = await apiFetch(`${api}/analytics/channels/${id}/experiments`);
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not load experiments");
      setExperiments(data);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load experiments"); }
  }
  useEffect(() => { void loadExperiments(channelId); }, [channelId]);

  async function importCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!channelId) return;
    setBusy(true); setError(""); setMessage("");
    const form = event.currentTarget;
    try {
      const response = await apiFetch(`${api}/analytics/import?channel_id=${channelId}`, { method: "POST", body: new FormData(form) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Import failed");
      setMessage(`Imported ${data.rows_imported} new rows and updated ${data.rows_updated} existing rows from this CSV.`); form.reset(); await Promise.all([loadSummary(channelId), loadInsights(channelId), loadExperiments(channelId)]);
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

  async function createExperiment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!channelId) return;
    setExperimentBusy(true); setError(""); setMessage("");
    const parseIds = (value: string) => value.split(/[\s,]+/).map(item => item.trim()).filter(Boolean);
    try {
      const response = await apiFetch(`${api}/analytics/experiments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ channel_id: channelId, title: experimentTitle, hypothesis: experimentHypothesis, variable: experimentVariable, control_description: controlDescription, treatment_description: treatmentDescription, metric: experimentMetric, control_video_ids: parseIds(controlVideoIds), treatment_video_ids: parseIds(treatmentVideoIds), notes: experimentNotes || null }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not create experiment");
      setMessage("Experiment registered. Group outcomes update from imported snapshots; the comparison is descriptive.");
      setExperimentTitle(""); setExperimentHypothesis(""); setControlDescription(""); setTreatmentDescription(""); setControlVideoIds(""); setTreatmentVideoIds(""); setExperimentNotes("");
      await loadExperiments(channelId);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create experiment"); }
    finally { setExperimentBusy(false); }
  }

  async function updateExperiment(experiment: Experiment, status: Experiment["status"]) {
    setExperimentBusy(true); setError("");
    try {
      const response = await apiFetch(`${api}/analytics/experiments/${experiment.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not update experiment");
      await loadExperiments(channelId);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update experiment"); }
    finally { setExperimentBusy(false); }
  }

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Analytics</h2><p className="muted">Import a YouTube Analytics export to see descriptive channel totals.</p></div></div>
    <p className="trend-method">No live YouTube Analytics connection is configured. Imports are user-provided cumulative snapshots; summaries use the latest row for each video and do not infer causality.</p>
    <div className="analytics-controls"><label>Channel<select value={channelId} onChange={event => setChannelId(event.target.value)}><option value="">Choose a channel</option>{channels.map(channel => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></label><button className="secondary" onClick={downloadTemplate}>Download CSV template</button></div>
    <form className="asset-form analytics-upload" onSubmit={importCsv}><label>Analytics CSV<input type="file" name="file" accept=".csv,text/csv" required /></label><p>Use cumulative snapshots with one row per video and collection date. Maximum 5 MB and 5,000 rows.</p><button className="primary" disabled={!channelId || busy}>{busy ? "Importing…" : "Import analytics"}</button></form>
    {message && <p className="success-message">{message}</p>}{error && <p className="error-message">{error}</p>}
    {summary && summary.video_count > 0 && <><div className="stats-grid analytics-stats">{[["VIDEOS IN SAMPLE", number(summary.video_count)], ["LATEST VIEWS TOTAL", number(summary.views_total)], ["IMPRESSION TOTAL", number(summary.impressions_total)], ["WEIGHTED CTR", summary.weighted_ctr_percent === null ? "—" : `${summary.weighted_ctr_percent.toFixed(2)}%`], ["WATCH TIME", `${(summary.watch_time_minutes_total / 60).toFixed(1)} hrs`], ["AVG VIEW DURATION", summary.average_view_duration_seconds === null ? "—" : `${summary.average_view_duration_seconds.toFixed(1)} sec`]].map(([label, value]) => <article className="stat-card" key={label}><div className="stat-title">{label}</div><div className="stat-value">{value}</div></article>)}</div><article className="analytics-note"><strong>Sample: {summary.sample_size}</strong><p>{summary.interpretation}</p><small>Snapshot window: {summary.data_window_start ? new Date(summary.data_window_start).toLocaleDateString() : "—"} to {summary.latest_snapshot_at ? new Date(summary.latest_snapshot_at).toLocaleDateString() : "—"}</small></article><div className="section-heading"><div><h2>Top imported videos</h2><p className="muted">Sorted by latest imported view count.</p></div></div><div className="channel-list">{summary.top_videos.map((item, index) => <article className="channel-row" key={item.video_id}><span className="video-rank">{String(index + 1).padStart(2, "0")}</span><div><strong>{number(item.views)} views</strong><p>{item.average_view_duration_seconds.toFixed(1)} sec average view duration · ID {item.video_id}</p></div><a className="text-button" href={`https://www.youtube.com/watch?v=${encodeURIComponent(item.video_id)}`} target="_blank" rel="noreferrer">Open video ↗</a></article>)}</div></>}
    {insights && <section className="learning-panel"><div className="section-heading"><div><h2>Learning hypotheses</h2><p className="muted">Descriptive signals from imported history, not automated strategy changes.</p></div><span className="learning-strength">{insights.evidence_strength} evidence · {insights.video_count} videos</span></div><p className="trend-method">{insights.caveat}</p>{insights.signals.length ? <><p className="muted">{insights.basis}</p><div className="learning-signals">{insights.signals.map(signal => <article className="analytics-note" key={signal.metric}><strong>{signal.metric}: {signal.direction} in higher-view group</strong><p>Median {decimal(signal.top_view_group_median)} for the highest-view group vs {decimal(signal.lower_view_group_median)} for the lowest-view group{signal.difference_percent === null ? " (lower group median is zero)" : ` (${Math.abs(signal.difference_percent)}% ${signal.direction})`}.</p></article>)}</div>{insights.suggested_review && <p className="learning-suggestion">{insights.suggested_review}</p>}</> : <p className="muted">{insights.video_count < 10 ? "Import at least 10 videos before this page offers exploratory comparisons." : "No difference was observed in the compared metrics for these groups."}</p>}</section>}
    <section className="learning-panel"><div className="section-heading"><div><h2>Content experiments</h2><p className="muted">Register one variable, describe both groups, then compare imported outcomes. This log never changes channel strategy automatically.</p></div></div>
      <form className="asset-form analytics-upload" onSubmit={createExperiment}><label>Experiment name<input required maxLength={120} value={experimentTitle} onChange={event => setExperimentTitle(event.target.value)} /></label><label>Hypothesis<textarea required maxLength={5000} value={experimentHypothesis} onChange={event => setExperimentHypothesis(event.target.value)} placeholder="What do you expect to change, and why?" /></label><label>Variable<input required maxLength={80} value={experimentVariable} onChange={event => setExperimentVariable(event.target.value)} placeholder="Title, thumbnail, hook, format…" /></label><label>Control group description<input required maxLength={500} value={controlDescription} onChange={event => setControlDescription(event.target.value)} /></label><label>Treatment group description<input required maxLength={500} value={treatmentDescription} onChange={event => setTreatmentDescription(event.target.value)} /></label><label>Outcome metric<select value={experimentMetric} onChange={event => setExperimentMetric(event.target.value)}>{experimentMetrics.map(metric => <option key={metric} value={metric}>{metricLabel(metric)}</option>)}</select></label><label>Control video IDs<textarea required value={controlVideoIds} onChange={event => setControlVideoIds(event.target.value)} placeholder="One YouTube video ID per line" /></label><label>Treatment video IDs<textarea required value={treatmentVideoIds} onChange={event => setTreatmentVideoIds(event.target.value)} placeholder="One YouTube video ID per line" /></label><label>Notes<textarea maxLength={5000} value={experimentNotes} onChange={event => setExperimentNotes(event.target.value)} placeholder="Planning notes or known confounders" /></label><button className="primary" disabled={!channelId || experimentBusy}>{experimentBusy ? "Saving…" : "Register experiment"}</button></form>
      {!experiments.length ? <p className="muted">No experiments registered for this channel.</p> : <div className="channel-list">{experiments.map(experiment => <article className="channel-row" key={experiment.id}><div><strong>{experiment.title} · {experiment.status}</strong><p>{experiment.hypothesis}</p><small>Variable: {experiment.variable} · {metricLabel(experiment.metric)}</small><p>Control median: {experiment.control_median === null ? "not imported" : decimal(experiment.control_median)} (n={experiment.control_sample_size}) · Treatment median: {experiment.treatment_median === null ? "not imported" : decimal(experiment.treatment_median)} (n={experiment.treatment_sample_size}){experiment.difference_percent === null ? "" : ` · ${experiment.difference_percent >= 0 ? "+" : ""}${experiment.difference_percent}%`}</p><small>{experiment.control_description} → {experiment.treatment_description}</small>{experiment.notes && <p>{experiment.notes}</p>}<p className="trend-method">{experiment.caveat}</p></div><div className="studio-actions">{experiment.status === "planned" && <><button type="button" className="secondary" disabled={experimentBusy} onClick={() => void updateExperiment(experiment, "running")}>Start</button><button type="button" className="secondary" disabled={experimentBusy} onClick={() => void updateExperiment(experiment, "cancelled")}>Cancel</button></>}{experiment.status === "running" && <><button type="button" className="secondary" disabled={experimentBusy} onClick={() => void updateExperiment(experiment, "completed")}>Complete</button><button type="button" className="secondary" disabled={experimentBusy} onClick={() => void updateExperiment(experiment, "cancelled")}>Cancel</button></>}</div></article>)}</div>}
    </section>
    {summary && summary.video_count === 0 && <article className="empty-card channel-empty"><div className="empty-icon">▥</div><h3>No analytics imported for this channel</h3><p>Upload a normalized YouTube Analytics CSV export to build a snapshot summary.</p></article>}
  </main>;
}
