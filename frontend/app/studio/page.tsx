"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Idea = { id: string; title: string; format: string; status: string };
type Script = { id: string; version: number; body: string; content_hash: string };
type Storyboard = { id: string; version: number; script_version_id: string; scenes: { duration_seconds: number; voiceover: string; visual_description: string; subtitle: string }[] };
type Video = { id: string; status: string; preview_url: string; thumbnail_url: string | null; captions_url: string | null; video_type: string; content_hash: string | null; qa_report: { status: string; checks: Record<string, boolean>; note: string } | null; duration_seconds: number; width: number; height: number };
type ProductionAttempt = { id: string; status: "queued" | "running" | "completed" | "failed"; video_id: string | null; failure_class: string | null; is_stale: boolean };
type MediaAsset = { id: string; asset_type: string; original_filename: string; license_type: string; source_url: string | null; duration_seconds: number | null };
type SceneInput = { duration_seconds: string; voiceover: string; visual_description: string; subtitle: string; image_asset_id: string; audio_asset_id: string };
type ReviewChecks = { editorial_accuracy_reviewed: boolean; sources_reviewed: boolean; media_rights_reviewed: boolean; disclosures_reviewed: boolean };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const blankScene = (): SceneInput => ({ duration_seconds: "5", voiceover: "", visual_description: "", subtitle: "", image_asset_id: "", audio_asset_id: "" });

export default function StudioPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [ideaId, setIdeaId] = useState("");
  const [scripts, setScripts] = useState<Script[]>([]);
  const [scriptId, setScriptId] = useState("");
  const [scriptBody, setScriptBody] = useState("");
  const [boards, setBoards] = useState<Storyboard[]>([]);
  const [boardId, setBoardId] = useState("");
  const [scenes, setScenes] = useState<SceneInput[]>([blankScene()]);
  const [video, setVideo] = useState<Video | null>(null);
  const [renderAttemptId, setRenderAttemptId] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [thumbnailUrl, setThumbnailUrl] = useState("");
  const [captionsUrl, setCaptionsUrl] = useState("");
  const [captionWarning, setCaptionWarning] = useState("");
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [reviewChecks, setReviewChecks] = useState<ReviewChecks>({ editorial_accuracy_reviewed: false, sources_reviewed: false, media_rights_reviewed: false, disclosures_reviewed: false });
  const [reviewNotes, setReviewNotes] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadIdeas() {
    try {
      const [ideasResponse, assetsResponse] = await Promise.all([apiFetch(`${api}/ideas`), apiFetch(`${api}/media-assets`)]);
      if (!ideasResponse.ok || !assetsResponse.ok) throw new Error("Could not load content ideas or media assets");
      const found: Idea[] = await ideasResponse.json(); setIdeas(found); setAssets(await assetsResponse.json());
      const requested = new URLSearchParams(window.location.search).get("idea");
      setIdeaId(current => current || (requested && found.some(item => item.id === requested) ? requested : found[0]?.id || ""));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load ideas"); }
  }
  useEffect(() => { void loadIdeas(); }, []);

  async function loadVersions(id: string) {
    if (!id) { setScripts([]); setBoards([]); return; }
    try {
      const [s, b] = await Promise.all([apiFetch(`${api}/ideas/${id}/scripts`), apiFetch(`${api}/ideas/${id}/storyboards`)]);
      if (!s.ok || !b.ok) throw new Error("Could not load content versions");
      const scriptItems: Script[] = await s.json(); const boardItems: Storyboard[] = await b.json();
      setScripts(scriptItems); setBoards(boardItems);
      if (scriptItems.length) { setScriptId(scriptItems[0].id); setScriptBody(scriptItems[0].body); }
      else { setScriptId(""); setScriptBody(""); }
      if (boardItems.length) setBoardId(boardItems[0].id); else setBoardId("");
      setVideo(null); setVideoUrl(""); setThumbnailUrl(""); setCaptionsUrl(""); setRenderAttemptId(""); setCaptionWarning(""); setReviewChecks({ editorial_accuracy_reviewed: false, sources_reviewed: false, media_rights_reviewed: false, disclosures_reviewed: false });
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load versions"); }
  }
  useEffect(() => { void loadVersions(ideaId); }, [ideaId]);
  useEffect(() => () => { if (videoUrl) URL.revokeObjectURL(videoUrl); }, [videoUrl]);
  useEffect(() => () => { if (thumbnailUrl) URL.revokeObjectURL(thumbnailUrl); }, [thumbnailUrl]);
  useEffect(() => () => { if (captionsUrl) URL.revokeObjectURL(captionsUrl); }, [captionsUrl]);

  const loadRenderedMedia = useCallback(async (data: Video) => {
    const fileResponse = await apiFetch(new URL(data.preview_url, new URL(api).origin));
    if (!fileResponse.ok) throw new Error("Could not load the rendered video file");
    setVideoUrl(URL.createObjectURL(await fileResponse.blob()));
    if (data.thumbnail_url) {
      const thumbResponse = await apiFetch(new URL(data.thumbnail_url, new URL(api).origin));
      if (thumbResponse.ok) setThumbnailUrl(URL.createObjectURL(await thumbResponse.blob()));
    } else setThumbnailUrl("");
    if (data.captions_url) {
      const captionsResponse = await apiFetch(new URL(data.captions_url, new URL(api).origin));
      if (captionsResponse.ok) {
        setCaptionsUrl(URL.createObjectURL(await captionsResponse.blob()));
        setCaptionWarning("");
      } else {
        setCaptionsUrl("");
        setCaptionWarning("Caption sidecar could not be loaded. Check the Operations media integrity audit.");
      }
    } else { setCaptionsUrl(""); setCaptionWarning(""); }
  }, []);

  useEffect(() => {
    if (!renderAttemptId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const response = await apiFetch(`${api}/operations/production-attempts/${renderAttemptId}`);
        const attempt: ProductionAttempt = await response.json();
        if (!response.ok) throw new Error("Could not read production attempt status");
        if (cancelled) return;
        if (attempt.status === "completed" && attempt.video_id) {
          const videoResponse = await apiFetch(`${api}/videos/${attempt.video_id}`);
          const rendered: Video = await videoResponse.json();
          if (!videoResponse.ok) throw new Error("Render completed, but video metadata could not be loaded");
          await loadRenderedMedia(rendered);
          if (cancelled) return;
          setVideo(rendered);
          setReviewChecks({ editorial_accuracy_reviewed: false, sources_reviewed: false, media_rights_reviewed: false, disclosures_reviewed: false });
          setMessage(`Background render completed with ${rendered.status}. Technical QA is not human approval.`);
          setRenderAttemptId("");
          return;
        }
        if (attempt.status === "failed") {
          setError(`Background render failed (${attempt.failure_class ?? "unknown failure"}). Review Operations before retrying.`);
          setRenderAttemptId("");
          return;
        }
        setMessage(attempt.status === "queued" ? "Production render is queued for the local worker…" : "Production render is running in the local worker…");
        timer = setTimeout(poll, 2500);
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Could not read render status");
          timer = setTimeout(poll, 5000);
        }
      }
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [renderAttemptId, loadRenderedMedia]);

  async function saveScript(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/ideas/${ideaId}/scripts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body: scriptBody, origin: "human" }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not save script");
      setMessage(`Saved script version ${data.version}`); await loadVersions(ideaId);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save script"); }
  }

  async function saveStoryboard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/ideas/${ideaId}/storyboards`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ script_version_id: scriptId, scenes: scenes.map(scene => ({ ...scene, image_asset_id: scene.image_asset_id || null, audio_asset_id: scene.audio_asset_id || null, duration_seconds: Number(scene.duration_seconds), asset_type: "user_supplied", transition: "cut", source_attribution: [scene.image_asset_id, scene.audio_asset_id].map(id => assets.find(asset => asset.id === id)?.source_url).filter(Boolean) })) }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not save storyboard");
      setMessage(`Saved storyboard version ${data.version}`); await loadVersions(ideaId);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save storyboard"); }
  }

  async function renderPreview() {
    setError(""); setMessage(""); setVideo(null); setVideoUrl(""); setThumbnailUrl(""); setCaptionsUrl(""); setCaptionWarning("");
    try {
      const response = await apiFetch(`${api}/ideas/${ideaId}/render-preview?storyboard_version_id=${boardId}`, { method: "POST" });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Render failed");
      await loadRenderedMedia(data); setVideo(data); setMessage("Silent animatic preview rendered. This is not production-ready footage.");
    } catch (e) { setError(e instanceof Error ? e.message : "Render failed"); }
  }

  async function uploadAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage(""); setUploading(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const response = await apiFetch(`${api}/media-assets`, { method: "POST", body: data });
      const result = await response.json(); if (!response.ok) throw new Error(result.detail ?? "Upload failed");
      setAssets(current => [result, ...current]); form.reset(); setMessage(`Uploaded ${result.original_filename}; rights confirmation and provenance saved.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setUploading(false); }
  }

  async function renderProduction() {
    setError(""); setMessage(""); setVideo(null); setVideoUrl(""); setThumbnailUrl(""); setCaptionsUrl(""); setCaptionWarning("");
    try {
      const response = await apiFetch(`${api}/ideas/${ideaId}/render-production-queue?storyboard_version_id=${boardId}`, { method: "POST" });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Production render failed");
      if (data.status === "completed" && data.video_id) {
        const videoResponse = await apiFetch(`${api}/videos/${data.video_id}`); const rendered: Video = await videoResponse.json();
        if (!videoResponse.ok) throw new Error("Could not load the reused production render");
        await loadRenderedMedia(rendered); setVideo(rendered); setMessage("Reused an existing intact QA-passed render. Technical QA is not human approval.");
      } else {
        if (typeof data.attempt_id !== "string" || !data.attempt_id) throw new Error("The production queue returned no attempt ID");
        setRenderAttemptId(data.attempt_id);
        setMessage("Production render queued for the local background worker…");
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Production render failed"); }
  }

  async function decideApproval(decision: "approve" | "reject" | "request_changes") {
    if (!video) return;
    setError(""); setMessage("");
    try {
      const response = await apiFetch(`${api}/videos/${video.id}/approvals`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, review_checks: reviewChecks, notes: reviewNotes || null }) });
      const result = await response.json(); if (!response.ok) throw new Error(result.detail ?? "Approval action failed");
      setVideo(current => current ? { ...current, status: decision === "approve" ? "APPROVED" : decision === "reject" ? "REJECTED" : "CHANGES_REQUESTED" } : null);
      setMessage(`Human decision recorded: ${result.decision} · content hash ${result.content_hash.slice(0, 12)}…`);
    } catch (e) { setError(e instanceof Error ? e.message : "Approval action failed"); }
  }

  const selected = ideas.find(idea => idea.id === ideaId);
  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Video Studio</h2><p className="muted">Version scripts and storyboards, then render a silent animatic for review.</p></div><a className="text-button" href="/ideas">← Content pipeline</a></div>
    <label className="studio-select">Content idea<select value={ideaId} onChange={event => setIdeaId(event.target.value)}><option value="">Choose an idea</option>{ideas.map(idea => <option key={idea.id} value={idea.id}>{idea.title} · {idea.format}</option>)}</select></label>
    {!ideas.length && <article className="empty-card channel-empty"><h3>No content ideas yet</h3><p>Create an idea in the content pipeline first.</p><a className="secondary" href="/ideas">Open content pipeline</a></article>}
    {selected && <>
      <p className="trend-method">{selected.title} · {selected.status}. AI generation, source verification, voice, and licensed assets are not configured; enter editorial content below.</p>
      <form className="studio-panel" onSubmit={saveScript}><div className="studio-panel-title"><h3>Script</h3><span>{scripts.length ? `${scripts.length} saved version(s)` : "No versions yet"}</span></div><label>Human-authored script<textarea value={scriptBody} onChange={event => setScriptBody(event.target.value)} required maxLength={100000} placeholder="Write or paste your script. Saving creates an immutable version." /></label><div className="studio-actions"><select value={scriptId} onChange={event => { setScriptId(event.target.value); setScriptBody(scripts.find(item => item.id === event.target.value)?.body ?? ""); }}><option value="">Current unsaved draft</option>{scripts.map(script => <option key={script.id} value={script.id}>Version {script.version}</option>)}</select><button className="primary" type="submit">Save new version</button></div></form>
      <section className="studio-panel"><div className="studio-panel-title"><h3>Media library</h3><span>{assets.length} uploaded assets</span></div><p className="trend-method">Upload images and voice clips you have permission to use. Files are limited to 30 MB. Non-owned assets need a source URL and scene attribution.</p><form className="asset-form" onSubmit={uploadAsset}><label>Media file<input name="file" type="file" accept="image/jpeg,image/png,image/webp,audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/flac,audio/ogg" required /></label><label>Rights basis<select name="license_type"><option value="owned">I created/own it</option><option value="licensed">Licensed</option><option value="public_domain">Public domain</option><option value="creative_commons">Creative Commons</option></select></label><label>Source URL (required for non-owned)<input name="source_url" type="url" placeholder="https://…" /></label><label className="rights-check"><input name="rights_confirmed" type="checkbox" value="true" required />I confirm I have the right to use this file.</label><button className="primary" type="submit" disabled={uploading}>{uploading ? "Uploading…" : "Upload asset"}</button></form><div className="asset-list">{assets.map(asset => <div className="asset-row" key={asset.id}><span className={asset.asset_type === "image" ? "asset-type image-type" : "asset-type audio-type"}>{asset.asset_type}</span><strong>{asset.original_filename}</strong><small>{asset.license_type}{asset.duration_seconds ? ` · ${asset.duration_seconds.toFixed(1)} sec` : ""}</small></div>)}</div></section>
      <form className="studio-panel" onSubmit={saveStoryboard}><div className="studio-panel-title"><h3>Storyboard scenes</h3><span>{boards.length ? `${boards.length} saved version(s)` : "No versions yet"}</span></div><label>Base scene versions on<select required value={scriptId} onChange={event => setScriptId(event.target.value)}><option value="">Choose a saved script</option>{scripts.map(script => <option key={script.id} value={script.id}>Script version {script.version}</option>)}</select></label>{scenes.map((scene, index) => <div className="scene-editor" key={index}><div className="studio-panel-title"><strong>Scene {index + 1}</strong>{scenes.length > 1 && <button className="remove-scene" type="button" onClick={() => setScenes(current => current.filter((_, i) => i !== index))}>Remove</button>}</div><label>Visual description<input required maxLength={2000} value={scene.visual_description} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, visual_description: event.target.value } : item))} /></label><label>Voiceover text<input required maxLength={5000} value={scene.voiceover} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, voiceover: event.target.value } : item))} /></label><label>Subtitle<input maxLength={2000} value={scene.subtitle} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, subtitle: event.target.value } : item))} /></label><label>Duration (seconds)<input required type="number" min="0.1" max="180" step="0.1" value={scene.duration_seconds} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, duration_seconds: event.target.value } : item))} /></label><label>Visual image<select value={scene.image_asset_id} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, image_asset_id: event.target.value } : item))}><option value="">Animatic card only</option>{assets.filter(asset => asset.asset_type === "image").map(asset => <option key={asset.id} value={asset.id}>{asset.original_filename} · {asset.license_type}</option>)}</select></label><label>Voice audio<select value={scene.audio_asset_id} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, audio_asset_id: event.target.value } : item))}><option value="">No audio</option>{assets.filter(asset => asset.asset_type === "audio").map(asset => <option key={asset.id} value={asset.id}>{asset.original_filename} · {asset.duration_seconds?.toFixed(1)} sec</option>)}</select></label></div>)}<div className="studio-actions"><button className="secondary" type="button" onClick={() => setScenes(current => [...current, blankScene()])}>＋ Add scene</button><button className="primary" type="submit" disabled={!scriptId}>Save storyboard version</button></div></form>
      <section className="studio-panel"><div className="studio-panel-title"><h3>Render and review</h3><span>Animatic or media-backed render</span></div><div className="studio-actions"><select value={boardId} onChange={event => setBoardId(event.target.value)}><option value="">Choose a saved storyboard</option>{boards.map(board => <option key={board.id} value={board.id}>Storyboard version {board.version}</option>)}</select><button className="secondary" type="button" disabled={!boardId} onClick={renderPreview}>Render silent animatic</button><button className="primary" type="button" disabled={!boardId || Boolean(renderAttemptId)} onClick={renderProduction}>{renderAttemptId ? "Rendering in background\u2026" : "Render production video"}</button></div>{video && <div className="video-preview"><video controls src={videoUrl}>{captionsUrl && <track kind="captions" src={captionsUrl} srcLang="und" label="Captions" default />}</video><p>{video.width}×{video.height} · {video.duration_seconds.toFixed(1)} seconds · {video.video_type} · {video.status}</p>{captionWarning && <p className="error-message">{captionWarning}</p>}{video.content_hash && <small className="content-fingerprint">Version fingerprint: {video.content_hash}</small>}{video.thumbnail_url && thumbnailUrl && <img className="render-thumbnail" src={thumbnailUrl} alt="Generated thumbnail preview" />}{captionsUrl && <a className="text-button" href={captionsUrl} download={`aye-captions-${video.id}.vtt`}>Download WebVTT captions</a>}{video.qa_report && <pre>{JSON.stringify(video.qa_report, null, 2)}</pre>}{video.video_type === "production" && video.status === "TECHNICAL_QA_PASSED" && video.qa_report?.status === "TECHNICAL_QA_PASSED" && <div className="approval-panel"><h4>Human approval</h4><p>Review the video, script, storyboard, source pack, and asset provenance before approving this exact version.</p>{([["editorial_accuracy_reviewed", "I reviewed factual claims and editorial accuracy."], ["sources_reviewed", "I reviewed source links and attribution."], ["media_rights_reviewed", "I reviewed asset rights and license terms."], ["disclosures_reviewed", "I reviewed required synthetic-content disclosures."]] as const).map(([key, label]) => <label className="review-check" key={key}><input type="checkbox" checked={reviewChecks[key]} onChange={event => setReviewChecks(current => ({ ...current, [key]: event.target.checked }))} />{label}</label>)}<label className="review-notes">Notes<textarea value={reviewNotes} onChange={event => setReviewNotes(event.target.value)} placeholder="Required if rejecting or requesting changes" /></label><div className="studio-actions"><button type="button" className="secondary" onClick={() => decideApproval("request_changes")}>Request changes</button><button type="button" className="secondary reject-button" onClick={() => decideApproval("reject")}>Reject</button><button type="button" className="primary" disabled={!Object.values(reviewChecks).every(Boolean)} onClick={() => decideApproval("approve")}>Approve this version</button></div></div>}</div>}</section>
    </>}
    {message && <p className="success-message">{message}</p>}{error && <p className="error-message">{error}</p>}
  </main>;
}
