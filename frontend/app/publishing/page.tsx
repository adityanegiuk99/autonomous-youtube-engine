"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import "../channels.css";
import "./publishing.css";
import { apiFetch } from "../lib/api";

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
type Video = { id: string; content_idea_id: string; status: string; video_type: string; content_hash: string | null; qa_report: { status?: string } | null };
type Approval = { id: string; video_id: string; content_hash: string; decision: string; created_at: string };
type Channel = { id: string; name: string };
type Idea = { id: string; title: string; channel_id: string };
type Candidate = { video: Video; approval: Approval; title: string; channel_id: string };
type PublishJob = { id: string; video_id: string; approval_id: string; channel_id: string; content_hash: string; title: string; description: string; tags: string[]; metadata_hash: string | null; metadata_reviewed_at: string | null; scheduled_at: string; visibility: "private"; status: "scheduled_local" | "cancelled"; created_at: string; cancelled_at: string | null };

function localDateTime(minutesFromNow: number) {
  const date = new Date(Date.now() + minutesFromNow * 60_000);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export default function PublishingPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<PublishJob[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [videoId, setVideoId] = useState("");
  const [scheduledAt, setScheduledAt] = useState(localDateTime(60));
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [metadataReviewed, setMetadataReviewed] = useState(false);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [videoResponse, ideaResponse, channelResponse, jobResponse] = await Promise.all([
        apiFetch(`${api}/videos?limit=200`), apiFetch(`${api}/ideas?limit=200`), apiFetch(`${api}/channels`), apiFetch(`${api}/publishing/jobs`),
      ]);
      const [videos, ideas, channelData, jobData] = await Promise.all([videoResponse.json(), ideaResponse.json(), channelResponse.json(), jobResponse.json()]);
      for (const response of [videoResponse, ideaResponse, channelResponse, jobResponse]) if (!response.ok) throw new Error("Could not load publishing workspace");
      const ideaMap = new Map((ideas as Idea[]).map(idea => [idea.id, idea]));
      const approvedVideos = (videos as Video[]).filter(video => video.video_type === "production" && video.qa_report?.status === "TECHNICAL_QA_PASSED");
      const approvalResults = await Promise.all(approvedVideos.map(async video => {
        const response = await apiFetch(`${api}/videos/${video.id}/approvals`);
        const records: Approval[] = response.ok ? await response.json() : [];
        const approval = records.find(record => record.decision === "approve");
        const idea = ideaMap.get(video.content_idea_id);
        return approval && approval.content_hash === video.content_hash ? { video, approval, title: idea?.title ?? "Untitled idea", channel_id: idea?.channel_id ?? "" } : null;
      }));
      const jobs = jobData as PublishJob[];
      const activeVideoIds = new Set(jobs.filter(job => job.status === "scheduled_local").map(job => job.video_id));
      const ready = approvalResults.filter((candidate): candidate is Candidate => candidate !== null && !activeVideoIds.has(candidate.video.id));
      setCandidates(ready);
      setJobs(jobs);
      setChannels(channelData as Channel[]);
      setVideoId(current => ready.some(candidate => candidate.video.id === current) ? current : ready[0]?.video.id ?? "");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load publishing workspace"); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const selected = candidates.find(candidate => candidate.video.id === videoId);

  async function schedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!videoId || !scheduledAt) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/publishing/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ video_id: videoId, scheduled_at: new Date(scheduledAt).toISOString(), title: title.trim() || null, description, tags: tags.split(",").map(tag => tag.trim()).filter(Boolean), metadata_reviewed: metadataReviewed }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not save local schedule");
      setMessage("Local schedule saved with human-reviewed metadata. No YouTube upload was attempted.");
      setTitle(""); setDescription(""); setTags(""); setMetadataReviewed(false);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save local schedule"); }
    finally { setSaving(false); }
  }

  async function cancel(job: PublishJob) {
    setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/publishing/jobs/${job.id}`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not cancel local schedule");
      setMessage("Local schedule cancelled. No YouTube upload was attempted.");
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not cancel local schedule"); }
  }

  const channelNames = new Map(channels.map(channel => [channel.id, channel.name]));
  return <main className="page-wrap publishing-page">
    <div className="section-heading"><div><h2>Publishing calendar</h2><p className="muted">Prepare private-first schedules for human-approved production renders.</p></div><button className="secondary" onClick={() => void refresh()} disabled={busy}>Refresh</button></div>
    <article className="operations-note"><strong>Local schedule only · no YouTube connection</strong><p>Saving a schedule stores a human-reviewed metadata fingerprint and a future time. This is separate from video approval and does not upload or publish anything on YouTube. Visibility is fixed to private until publishing OAuth and upload are implemented.</p></article>
    {error && <p className="error-message">{error}</p>}{message && <p className="success-message">{message}</p>}{busy && <p className="muted">Loading publishing workspace…</p>}
    <section className="studio-panel publishing-form"><div className="studio-panel-title"><div><h3>Prepare a schedule</h3><span>Only current, approved, QA-passed production renders are accepted.</span></div><strong className="approval-state">PRIVATE</strong></div>
      {!candidates.length && !busy ? <div className="empty-card channel-empty"><h3>No approved renders available</h3><p>Complete technical QA and human approval before preparing a schedule.</p><a className="secondary" href="/approvals">Open Approval Center</a></div> : <form onSubmit={schedule}>
        <label>Approved render<select value={videoId} onChange={event => { setVideoId(event.target.value); setTitle(""); setMetadataReviewed(false); }} required><option value="">Select an approved render</option>{candidates.map(candidate => <option value={candidate.video.id} key={candidate.video.id}>{candidate.title} · {candidate.video.id.slice(0, 8)}</option>)}</select></label>
        <label>Schedule time<input type="datetime-local" value={scheduledAt} onChange={event => setScheduledAt(event.target.value)} required /></label>
        <label>Video title<input maxLength={100} value={title || selected?.title || ""} onChange={event => { setTitle(event.target.value); setMetadataReviewed(false); }} required /></label>
        <label>Description<textarea maxLength={5000} value={description} onChange={event => { setDescription(event.target.value); setMetadataReviewed(false); }} rows={4} /></label>
        <label>Tags (comma separated)<input maxLength={3300} value={tags} onChange={event => { setTags(event.target.value); setMetadataReviewed(false); }} placeholder="Add up to 30 tags" /></label>
        <label className="rights-check"><input type="checkbox" checked={metadataReviewed} onChange={event => setMetadataReviewed(event.target.checked)} required />I reviewed this exact title, description, tags, and private visibility for the selected approved render.</label>
        <div className="publishing-summary"><span>Channel</span><strong>{selected ? (channelNames.get(selected.channel_id) ?? "Configured channel") : "—"}</strong><span>Approval fingerprint</span><code>{selected?.approval.content_hash ?? "—"}</code></div>
        <button className="primary" type="submit" disabled={saving || busy || !videoId || !metadataReviewed}>{saving ? "Saving…" : "Save local schedule"}</button>
      </form>}
    </section>
    <section className="publish-jobs"><div className="section-heading"><div><h3>Scheduled items</h3><p className="muted">Local records only; this list does not represent YouTube uploads.</p></div></div>
      {!jobs.length && !busy && <article className="empty-card"><h3>No scheduled items</h3><p>Approved renders will appear here after you save a local schedule.</p></article>}
      {jobs.map(job => <article className="publish-job" key={job.id}><div><strong>{job.title}</strong><p>{channelNames.get(job.channel_id) ?? "Configured channel"} · {new Date(job.scheduled_at).toLocaleString()} · {job.visibility} · {job.status.replaceAll("_", " ")}</p><small>Video {job.video_id} · approval hash {job.content_hash.slice(0, 12)}…</small><small>{job.metadata_reviewed_at ? `Metadata reviewed ${new Date(job.metadata_reviewed_at).toLocaleString()} · hash ${job.metadata_hash?.slice(0, 12) ?? "—"}` : "Metadata review not recorded for this legacy schedule"}</small></div>{job.status === "scheduled_local" && <button className="secondary reject-button" onClick={() => void cancel(job)}>Cancel</button>}</article>)}
    </section>
  </main>;
}
