"use client";

import { FormEvent, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Idea = { id: string; title: string; format: string; status: string };
type Script = { id: string; version: number; body: string; content_hash: string };
type Storyboard = { id: string; version: number; script_version_id: string; scenes: { duration_seconds: number; voiceover: string; visual_description: string; subtitle: string }[] };
type Video = { id: string; status: string; preview_url: string; duration_seconds: number; width: number; height: number };
type SceneInput = { duration_seconds: string; voiceover: string; visual_description: string; subtitle: string };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const blankScene = (): SceneInput => ({ duration_seconds: "5", voiceover: "", visual_description: "", subtitle: "" });

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
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadIdeas() {
    try {
      const response = await apiFetch(`${api}/ideas`);
      if (!response.ok) throw new Error("Could not load content ideas");
      const found: Idea[] = await response.json(); setIdeas(found);
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
      setVideo(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load versions"); }
  }
  useEffect(() => { void loadVersions(ideaId); }, [ideaId]);

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
      const response = await apiFetch(`${api}/ideas/${ideaId}/storyboards`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ script_version_id: scriptId, scenes: scenes.map(scene => ({ ...scene, duration_seconds: Number(scene.duration_seconds), asset_type: "user_supplied", transition: "cut", source_attribution: [] })) }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Could not save storyboard");
      setMessage(`Saved storyboard version ${data.version}`); await loadVersions(ideaId);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save storyboard"); }
  }

  async function renderPreview() {
    setError(""); setMessage(""); setVideo(null);
    try {
      const response = await apiFetch(`${api}/ideas/${ideaId}/render-preview?storyboard_version_id=${boardId}`, { method: "POST" });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Render failed");
      setVideo(data); setMessage("Silent animatic preview rendered. This is not production-ready footage.");
    } catch (e) { setError(e instanceof Error ? e.message : "Render failed"); }
  }

  const selected = ideas.find(idea => idea.id === ideaId);
  const videoUrl = video ? new URL(video.preview_url, new URL(api).origin).href : "";
  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Video Studio</h2><p className="muted">Version scripts and storyboards, then render a silent animatic for review.</p></div><a className="text-button" href="/ideas">← Content pipeline</a></div>
    <label className="studio-select">Content idea<select value={ideaId} onChange={event => setIdeaId(event.target.value)}><option value="">Choose an idea</option>{ideas.map(idea => <option key={idea.id} value={idea.id}>{idea.title} · {idea.format}</option>)}</select></label>
    {!ideas.length && <article className="empty-card channel-empty"><h3>No content ideas yet</h3><p>Create an idea in the content pipeline first.</p><a className="secondary" href="/ideas">Open content pipeline</a></article>}
    {selected && <>
      <p className="trend-method">{selected.title} · {selected.status}. AI generation, source verification, voice, and licensed assets are not configured; enter editorial content below.</p>
      <form className="studio-panel" onSubmit={saveScript}><div className="studio-panel-title"><h3>Script</h3><span>{scripts.length ? `${scripts.length} saved version(s)` : "No versions yet"}</span></div><label>Human-authored script<textarea value={scriptBody} onChange={event => setScriptBody(event.target.value)} required maxLength={100000} placeholder="Write or paste your script. Saving creates an immutable version." /></label><div className="studio-actions"><select value={scriptId} onChange={event => { setScriptId(event.target.value); setScriptBody(scripts.find(item => item.id === event.target.value)?.body ?? ""); }}><option value="">Current unsaved draft</option>{scripts.map(script => <option key={script.id} value={script.id}>Version {script.version}</option>)}</select><button className="primary" type="submit">Save new version</button></div></form>
      <form className="studio-panel" onSubmit={saveStoryboard}><div className="studio-panel-title"><h3>Storyboard scenes</h3><span>{boards.length ? `${boards.length} saved version(s)` : "No versions yet"}</span></div><label>Base scene versions on<select required value={scriptId} onChange={event => setScriptId(event.target.value)}><option value="">Choose a saved script</option>{scripts.map(script => <option key={script.id} value={script.id}>Script version {script.version}</option>)}</select></label>{scenes.map((scene, index) => <div className="scene-editor" key={index}><div className="studio-panel-title"><strong>Scene {index + 1}</strong>{scenes.length > 1 && <button className="remove-scene" type="button" onClick={() => setScenes(current => current.filter((_, i) => i !== index))}>Remove</button>}</div><label>Visual description<input required maxLength={2000} value={scene.visual_description} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, visual_description: event.target.value } : item))} /></label><label>Voiceover text<input required maxLength={5000} value={scene.voiceover} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, voiceover: event.target.value } : item))} /></label><label>Subtitle<input maxLength={2000} value={scene.subtitle} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, subtitle: event.target.value } : item))} /></label><label>Duration (seconds)<input required type="number" min="0.1" max="180" step="0.1" value={scene.duration_seconds} onChange={event => setScenes(current => current.map((item, i) => i === index ? { ...item, duration_seconds: event.target.value } : item))} /></label></div>)}<div className="studio-actions"><button className="secondary" type="button" onClick={() => setScenes(current => [...current, blankScene()])}>＋ Add scene</button><button className="primary" type="submit" disabled={!scriptId}>Save storyboard version</button></div></form>
      <section className="studio-panel"><div className="studio-panel-title"><h3>Animatic preview</h3><span>Silent, generated text cards</span></div><div className="studio-actions"><select value={boardId} onChange={event => setBoardId(event.target.value)}><option value="">Choose a saved storyboard</option>{boards.map(board => <option key={board.id} value={board.id}>Storyboard version {board.version}</option>)}</select><button className="primary" type="button" disabled={!boardId} onClick={renderPreview}>Render preview</button></div>{video && <div className="video-preview"><video controls src={videoUrl} /><p>{video.width}×{video.height} · {video.duration_seconds.toFixed(1)} seconds · {video.status}</p></div>}</section>
    </>}
    {message && <p className="success-message">{message}</p>}{error && <p className="error-message">{error}</p>}
  </main>;
}
