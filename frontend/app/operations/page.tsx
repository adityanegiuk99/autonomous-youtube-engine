"use client";

import { useEffect, useState } from "react";
import "../channels.css";
import "./operations.css";
import { apiFetch } from "../lib/api";

type Usage = {
  period_days: number; starts_at: string; ends_at: string; attempts: number; measured_attempts: number; unmeasured_attempts: number;
  technical_qa_passes: number; technical_qa_failures: number; render_failures: number; render_seconds_total: number;
  render_seconds_average: number | null; source_media_bytes: number; rendered_video_bytes: number; monetary_cost_available: boolean; note: string;
};
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const integer = (value: number) => new Intl.NumberFormat().format(value);
const bytes = (value: number) => value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / (1024 * 1024)).toFixed(2)} MB`;
const duration = (value: number | null) => value === null ? "—" : value < 60 ? `${value.toFixed(1)} sec` : `${(value / 60).toFixed(1)} min`;

export default function OperationsPage() {
  const [days, setDays] = useState(30);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setBusy(true); setError("");
    apiFetch(`${api}/operations/render-usage?days=${days}`)
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail ?? "Could not load render usage");
        if (!cancelled) setUsage(data);
      })
      .catch(reason => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load render usage"); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [days]);

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Operations and cost monitor</h2><p className="muted">Observed local production resources and render outcomes.</p></div><label className="period-select">Window<select value={days} onChange={event => setDays(Number(event.target.value))}><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={365}>Last 365 days</option></select></label></div>
    <article className="operations-note"><strong>Financial cost is unavailable</strong><p>No paid provider or cloud usage is connected. These measurements cover local FFmpeg render time and file volume only; they are not rupee estimates.</p></article>
    {busy && <p className="muted">Loading operational usage…</p>}{error && <p className="error-message">{error}</p>}
    {usage && <>
      <div className="stats-grid operations-stats">
        {[["PRODUCTION ATTEMPTS", integer(usage.attempts)], ["TECHNICAL QA PASSES", integer(usage.technical_qa_passes)], ["QA FAILURES", integer(usage.technical_qa_failures)], ["RENDER FAILURES", integer(usage.render_failures)], ["TOTAL RENDER TIME", duration(usage.render_seconds_total)], ["AVERAGE PER MEASURED ATTEMPT", duration(usage.render_seconds_average)], ["SOURCE MEDIA READ", bytes(usage.source_media_bytes)], ["VIDEO OUTPUT WRITTEN", bytes(usage.rendered_video_bytes)]].map(([label, value]) => <article className="stat-card" key={label}><div className="stat-title">{label}</div><div className="stat-value">{value}</div></article>)}
      </div>
      <article className="analytics-note"><strong>Measurement coverage</strong><p>{integer(usage.measured_attempts)} of {integer(usage.attempts)} production attempts include resource measurements. Older workflow events may predate this instrumentation.</p><small>Window: {new Date(usage.starts_at).toLocaleString()} to {new Date(usage.ends_at).toLocaleString()}</small></article>
      <p className="trend-method">{usage.note}</p>
    </>}
    {!busy && usage?.attempts === 0 && <article className="empty-card channel-empty"><div className="empty-icon">◷</div><h3>No production attempts in this window</h3><p>Render usage will appear here after a production attempt completes.</p><a className="secondary" href="/studio">Open Video Studio</a></article>}
  </main>;
}
