"use client";

import { useCallback, useEffect, useState } from "react";
import "../channels.css";
import "./operations.css";
import { apiFetch } from "../lib/api";

type Usage = {
  period_days: number; starts_at: string; ends_at: string; attempts: number; measured_attempts: number; unmeasured_attempts: number;
  technical_qa_passes: number; technical_qa_failures: number; render_failures: number; render_seconds_total: number;
  render_seconds_average: number | null; source_media_bytes: number; rendered_video_bytes: number; monetary_cost_available: boolean; note: string;
};
type IntegrityIssue = { category: string; record_type: string; record_id: string | null; storage_key: string };
type IntegrityReport = { checked_at: string; storage_root_available: boolean; referenced_files_checked: number; issues: IntegrityIssue[]; orphan_files_truncated: boolean; note: string };
type WorkerHealth = { worker_id: string; started_at: string; last_seen_at: string; current_attempt_id: string | null; status: "online" | "stale"; age_seconds: number };
type ProductionAttempt = { id: string; content_idea_id: string; storyboard_version_id: string; attempt_number: number; status: "queued" | "running" | "completed" | "failed"; started_at: string; finished_at: string | null; video_id: string | null; render_duration_seconds: number | null; source_bytes: number | null; output_bytes: number | null; failure_class: string | null; is_stale: boolean; age_seconds: number };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const integer = (value: number) => new Intl.NumberFormat().format(value);
const bytes = (value: number) => value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / (1024 * 1024)).toFixed(2)} MB`;
const duration = (value: number | null) => value === null ? "—" : value < 60 ? `${value.toFixed(1)} sec` : `${(value / 60).toFixed(1)} min`;

export default function OperationsPage() {
  const [days, setDays] = useState(30);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [integrityBusy, setIntegrityBusy] = useState(false);
  const [integrityError, setIntegrityError] = useState("");
  const [attempts, setAttempts] = useState<ProductionAttempt[]>([]);
  const [attemptError, setAttemptError] = useState("");
  const [recovering, setRecovering] = useState("");
  const [workers, setWorkers] = useState<WorkerHealth[]>([]);
  const [workerError, setWorkerError] = useState("");

  const loadAttempts = useCallback(async () => {
    setAttemptError("");
    try {
      const response = await apiFetch(`${api}/operations/production-attempts?limit=50`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not load production attempts");
      setAttempts(data);
    } catch (reason) { setAttemptError(reason instanceof Error ? reason.message : "Could not load production attempts"); }
  }, []);

  const loadWorkers = useCallback(async () => {
    setWorkerError("");
    try {
      const response = await apiFetch(`${api}/operations/workers`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not load worker health");
      setWorkers(data);
    } catch (reason) { setWorkerError(reason instanceof Error ? reason.message : "Could not load worker health"); }
  }, []);

  async function recoverAttempt(attempt: ProductionAttempt) {
    setRecovering(attempt.id); setAttemptError("");
    try {
      const response = await apiFetch(`${api}/operations/production-attempts/${attempt.id}/recover`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not recover production attempt");
      await loadAttempts();
    } catch (reason) { setAttemptError(reason instanceof Error ? reason.message : "Could not recover production attempt"); }
    finally { setRecovering(""); }
  }

  useEffect(() => { void loadAttempts(); void loadWorkers(); }, [loadAttempts, loadWorkers]);
  useEffect(() => {
    const timer = window.setInterval(() => { void loadWorkers(); }, 10000);
    return () => window.clearInterval(timer);
  }, [loadWorkers]);

  async function auditMedia() {
    setIntegrityBusy(true); setIntegrityError("");
    try {
      const response = await apiFetch(`${api}/operations/media-integrity`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not audit media storage");
      setIntegrity(data);
    } catch (reason) {
      setIntegrityError(reason instanceof Error ? reason.message : "Could not audit media storage");
    } finally { setIntegrityBusy(false); }
  }

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
    <section className="production-attempts">
      <div className="section-heading"><div><h3>Background workers</h3><p className="muted">Heartbeat is refreshed while the worker is idle and during long renders.</p></div><button className="secondary" onClick={() => void loadWorkers()}>Refresh workers</button></div>
      {workerError && <p className="error-message">{workerError}</p>}
      {!workers.length && !workerError && <p className="muted">No worker heartbeat has been recorded. Start the Compose worker to process queued renders.</p>}
      {workers.map(worker => <article className="production-attempt-row" key={worker.worker_id}><div><strong>{worker.status === "online" ? "Online" : "No recent heartbeat"} · {worker.worker_id}</strong><p>Last seen {new Date(worker.last_seen_at).toLocaleString()} · started {new Date(worker.started_at).toLocaleString()}</p><small>{worker.current_attempt_id ? `Active attempt ${worker.current_attempt_id}` : `Idle · heartbeat ${worker.age_seconds}s ago`}</small></div></article>)}
    </section>
    {usage && <>
      <div className="stats-grid operations-stats">
        {[["PRODUCTION ATTEMPTS", integer(usage.attempts)], ["TECHNICAL QA PASSES", integer(usage.technical_qa_passes)], ["QA FAILURES", integer(usage.technical_qa_failures)], ["RENDER FAILURES", integer(usage.render_failures)], ["TOTAL RENDER TIME", duration(usage.render_seconds_total)], ["AVERAGE PER MEASURED ATTEMPT", duration(usage.render_seconds_average)], ["SOURCE MEDIA READ", bytes(usage.source_media_bytes)], ["VIDEO OUTPUT WRITTEN", bytes(usage.rendered_video_bytes)]].map(([label, value]) => <article className="stat-card" key={label}><div className="stat-title">{label}</div><div className="stat-value">{value}</div></article>)}
      </div>
      <article className="analytics-note"><strong>Measurement coverage</strong><p>{integer(usage.measured_attempts)} of {integer(usage.attempts)} production attempts include resource measurements. Older workflow events may predate this instrumentation.</p><small>Window: {new Date(usage.starts_at).toLocaleString()} to {new Date(usage.ends_at).toLocaleString()}</small></article>
      <p className="trend-method">{usage.note}</p>
    </>}
    <section className="media-integrity">
      <div className="section-heading"><div><h3>Media storage integrity</h3><p className="muted">Compare referenced local files with their recorded checksums and find unreferenced files.</p></div><button className="secondary" onClick={auditMedia} disabled={integrityBusy}>{integrityBusy ? "Checking files…" : "Run read-only audit"}</button></div>
      {integrityError && <p className="error-message">{integrityError}</p>}
      {integrity && <>
        <article className={integrity.issues.length || !integrity.storage_root_available ? "operations-note" : "integrity-clean"}>
          <strong>{!integrity.storage_root_available ? "Media storage directory is unavailable" : integrity.issues.length ? `${integer(integrity.issues.length)} issue${integrity.issues.length === 1 ? "" : "s"} found` : "No storage issues found"}</strong>
          <p>Checked {integer(integrity.referenced_files_checked)} referenced files at {new Date(integrity.checked_at).toLocaleString()}.</p>
          {integrity.orphan_files_truncated && <p>Only the first 100 unreferenced files are listed.</p>}
        </article>
        {integrity.issues.length > 0 && <div className="integrity-issues">{integrity.issues.map((issue, index) => <div key={`${issue.category}-${issue.storage_key}-${index}`}><strong>{issue.category.replaceAll("_", " ")}</strong><span>{issue.record_type}{issue.record_id ? ` · ${issue.record_id}` : ""}</span><code>{issue.storage_key}</code></div>)}</div>}
        <p className="trend-method">{integrity.note}</p>
      </>}
    </section>
    <section className="production-attempts">
      <div className="section-heading"><div><h3>Production attempts and recovery</h3><p className="muted">Committed attempt state survives API process restarts. Stale queued or running work needs operator recovery before retry.</p></div><button className="secondary" onClick={() => void loadAttempts()}>Refresh attempts</button></div>
      {attemptError && <p className="error-message">{attemptError}</p>}
      {!attempts.length && !attemptError && <p className="muted">No production attempts have been recorded.</p>}
      {attempts.map(attempt => <article className="production-attempt-row" key={attempt.id}><div><strong>Attempt {attempt.attempt_number} · {attempt.status.replaceAll("_", " ")}{attempt.failure_class ? ` · ${attempt.failure_class.replaceAll("_", " ")}` : ""}</strong><p>{new Date(attempt.started_at).toLocaleString()} · {duration(attempt.render_duration_seconds)} · storyboard {attempt.storyboard_version_id.slice(0, 8)}</p><small>{attempt.id}{attempt.status === "running" ? ` · running ${Math.floor(attempt.age_seconds / 60)} min` : attempt.status === "queued" ? ` · queued ${Math.floor(attempt.age_seconds / 60)} min` : ""}</small></div>{attempt.is_stale && <button className="secondary reject-button" disabled={recovering === attempt.id} onClick={() => void recoverAttempt(attempt)}>{recovering === attempt.id ? "Recovering…" : attempt.status === "queued" ? "Recover stuck queue item" : "Recover interrupted render"}</button>}</article>)}
    </section>
    {!busy && usage?.attempts === 0 && <article className="empty-card channel-empty"><div className="empty-icon">◷</div><h3>No production attempts in this window</h3><p>Render usage will appear here after a production attempt completes.</p><a className="secondary" href="/studio">Open Video Studio</a></article>}
  </main>;
}
