"use client";

import { FormEvent, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Channel = { id: string; name: string; niche: string | null; language: string; target_country: string | null; description: string | null; audience_profile: string | null; brand_voice: string | null; visual_guidelines: string | null; content_pillars: string[]; preferred_formats: string[]; publishing_frequency_per_week: number | null; is_active: boolean };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("");
  const [audienceProfile, setAudienceProfile] = useState("");
  const [brandVoice, setBrandVoice] = useState("");
  const [visualGuidelines, setVisualGuidelines] = useState("");
  const [contentPillars, setContentPillars] = useState("");
  const [preferredFormats, setPreferredFormats] = useState<string[]>(["short", "long"]);
  const [publishingFrequency, setPublishingFrequency] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);

  function clearForm() {
    setName(""); setNiche(""); setAudienceProfile(""); setBrandVoice(""); setVisualGuidelines("");
    setContentPillars(""); setPreferredFormats(["short", "long"]); setPublishingFrequency(""); setEditingId(null);
  }

  async function refresh() {
    setLoading(true);
    try {
      const response = await apiFetch(`${api}/channels`);
      if (!response.ok) throw new Error("Could not load channels");
      setChannels(await response.json());
      setError("");
    } catch {
      setError("API is unavailable. Start the local stack and reload this page.");
    } finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await apiFetch(editingId ? `${api}/channels/${editingId}` : `${api}/channels`, { method: editingId ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, niche: niche || null, audience_profile: audienceProfile || null, brand_voice: brandVoice || null, visual_guidelines: visualGuidelines || null, content_pillars: contentPillars.split("\n").map(item => item.trim()).filter(Boolean), preferred_formats: preferredFormats, publishing_frequency_per_week: publishingFrequency === "" ? null : Number(publishingFrequency) }) });
      if (!response.ok) throw new Error("Could not create channel");
      clearForm(); await refresh();
    } catch { setError("Channel could not be saved. Check that the API is running."); }
  }

  async function remove(channel: Channel) {
    if (!window.confirm(`Delete channel configuration “${channel.name}”?`)) return;
    try {
      const response = await apiFetch(`${api}/channels/${channel.id}`, { method: "DELETE" });
      if (!response.ok) { const result = await response.json(); throw new Error(result.detail ?? "Could not delete channel"); }
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not delete channel"); }
  }

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Channel configuration</h2><p className="muted">Set up channel identities before connecting YouTube.</p></div><a className="text-button" href="/">← Overview</a></div>
    <form className="channel-form strategy-form" onSubmit={create}><label>Channel name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Curious Circuit" /></label><label>Niche<input maxLength={120} value={niche} onChange={e => setNiche(e.target.value)} placeholder="e.g. Technology and AI" /></label><label>Audience profile<textarea maxLength={2000} value={audienceProfile} onChange={e => setAudienceProfile(e.target.value)} placeholder="Who is this channel for? What do they know and want?" /></label><label>Brand voice<textarea maxLength={1000} value={brandVoice} onChange={e => setBrandVoice(e.target.value)} placeholder="Tone, vocabulary, pacing, and point of view" /></label><label>Visual guidelines<textarea maxLength={2000} value={visualGuidelines} onChange={e => setVisualGuidelines(e.target.value)} placeholder="Color, composition, typography, and visual constraints" /></label><label>Content pillars (one per line)<textarea maxLength={1300} value={contentPillars} onChange={e => setContentPillars(e.target.value)} placeholder="Maximum 10 pillars, 120 characters each" /></label><label>Publishing target per week<input type="number" min="0" max="14" value={publishingFrequency} onChange={e => setPublishingFrequency(e.target.value)} placeholder="Optional" /></label><fieldset><legend>Preferred formats</legend>{([["short", "Shorts"], ["long", "Long-form"]] as const).map(([value, label]) => <label className="format-check" key={value}><input type="checkbox" checked={preferredFormats.includes(value)} onChange={e => setPreferredFormats(current => e.target.checked ? [...current, value] : current.filter(item => item !== value))} />{label}</label>)}</fieldset><div className="channel-form-actions"><button className="primary" type="submit" disabled={!preferredFormats.length}>{editingId ? "Save changes" : "＋  Add channel"}</button>{editingId && <button className="secondary" type="button" onClick={clearForm}>Cancel</button>}</div></form>
    {error && <p className="error-message">{error}</p>}
    {loading ? <p className="muted">Loading channels…</p> : channels.length ? <div className="channel-list">{channels.map(channel => <article className="channel-row" key={channel.id}><div className="channel-avatar">{channel.name.slice(0, 1).toUpperCase()}</div><div className="channel-summary"><strong>{channel.name}</strong><p>{channel.niche || "Niche not set"} · {channel.language.toUpperCase()} · {channel.preferred_formats.map(format => format === "short" ? "Shorts" : "Long-form").join(" / ")}</p><details><summary>Editorial profile</summary><p><b>Audience:</b> {channel.audience_profile || "Not set"}</p><p><b>Voice:</b> {channel.brand_voice || "Not set"}</p><p><b>Visuals:</b> {channel.visual_guidelines || "Not set"}</p><p><b>Content pillars:</b> {channel.content_pillars.join(", ") || "Not set"}</p><p><b>Publishing target:</b> {channel.publishing_frequency_per_week === null ? "Not set" : `${channel.publishing_frequency_per_week} per week`}</p></details></div><span className="config-state">CONFIGURED</span><div className="channel-actions"><button onClick={() => { setEditingId(channel.id); setName(channel.name); setNiche(channel.niche ?? ""); setAudienceProfile(channel.audience_profile ?? ""); setBrandVoice(channel.brand_voice ?? ""); setVisualGuidelines(channel.visual_guidelines ?? ""); setContentPillars(channel.content_pillars.join("\n")); setPreferredFormats(channel.preferred_formats); setPublishingFrequency(channel.publishing_frequency_per_week?.toString() ?? ""); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button><button onClick={() => remove(channel)}>Delete</button></div></article>)}</div> : <article className="empty-card channel-empty"><div className="empty-icon">▣</div><h3>No channel configurations yet</h3><p>Add a channel above to define its name, audience, and editorial identity. YouTube connection is not available yet.</p></article>}
  </main>;
}
