"use client";

import { FormEvent, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Channel = { id: string; name: string; niche: string | null; language: string; target_country: string | null; description: string | null; is_active: boolean };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);

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
      const response = await apiFetch(editingId ? `${api}/channels/${editingId}` : `${api}/channels`, { method: editingId ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, niche: niche || null }) });
      if (!response.ok) throw new Error("Could not create channel");
      setName(""); setNiche(""); setEditingId(null); await refresh();
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
    <form className="channel-form" onSubmit={create}><label>Channel name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Curious Circuit" /></label><label>Niche<input maxLength={120} value={niche} onChange={e => setNiche(e.target.value)} placeholder="e.g. Technology and AI" /></label><div className="channel-form-actions"><button className="primary" type="submit">{editingId ? "Save changes" : "＋  Add channel"}</button>{editingId && <button className="secondary" type="button" onClick={() => { setEditingId(null); setName(""); setNiche(""); }}>Cancel</button>}</div></form>
    {error && <p className="error-message">{error}</p>}
    {loading ? <p className="muted">Loading channels…</p> : channels.length ? <div className="channel-list">{channels.map(channel => <article className="channel-row" key={channel.id}><div className="channel-avatar">{channel.name.slice(0, 1).toUpperCase()}</div><div><strong>{channel.name}</strong><p>{channel.niche || "Niche not set"} · {channel.language.toUpperCase()}</p></div><span className="config-state">CONFIGURED</span><div className="channel-actions"><button onClick={() => { setEditingId(channel.id); setName(channel.name); setNiche(channel.niche ?? ""); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button><button onClick={() => remove(channel)}>Delete</button></div></article>)}</div> : <article className="empty-card channel-empty"><div className="empty-icon">▣</div><h3>No channel configurations yet</h3><p>Add a channel above to define its name and niche. YouTube connection is not available yet.</p></article>}
  </main>;
}
