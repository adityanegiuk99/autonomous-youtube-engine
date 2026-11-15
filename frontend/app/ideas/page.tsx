"use client";

import { FormEvent, useEffect, useState } from "react";
import "../channels.css";
import { apiFetch } from "../lib/api";

type Channel = { id: string; name: string };
type Trend = { id: string; title: string; trend_score: number };
type Idea = { id: string; channel_id: string; title: string; format: string; opportunity_score: number; status: string };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function IdeasPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [c, t, i] = await Promise.all([apiFetch(`${api}/channels`), apiFetch(`${api}/trends`), apiFetch(`${api}/ideas`)]);
      if (![c, t, i].every(r => r.ok)) throw new Error("API request failed");
      setChannels(await c.json()); setTrends(await t.json()); setIdeas(await i.json()); setError("");
    } catch { setError("Could not load the pipeline. Check that the API is running."); }
  }
  useEffect(() => { void load(); }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    const number = (key: string) => Number(data.get(key));
    const trend = String(data.get("trend_item_id") || "");
    try {
      const response = await apiFetch(`${api}/ideas`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ channel_id: data.get("channel_id"), trend_item_id: trend || null, title: data.get("title"), format: data.get("format"), engagement_potential: number("engagement_potential"), audience_relevance: number("audience_relevance"), originality: number("originality"), research_quality: number("research_quality"), competition: data.get("competition") ? number("competition") : null }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Could not create idea");
      form.reset(); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create idea"); }
  }

  return <main className="page-wrap">
    <div className="section-heading"><div><h2>Content pipeline</h2><p className="muted">Route trend items to a channel and record editorial score inputs.</p></div><a className="text-button" href="/trends">Open Trend Radar →</a></div>
    <p className="trend-method">Engagement, audience fit, originality, and research quality are human estimates here. Trend velocity uses the RSS freshness/diversity score.</p>
    <form className="idea-form" onSubmit={create}><label>Idea title<input name="title" required maxLength={500} /></label><label>Channel<select name="channel_id" required defaultValue=""><option value="" disabled>Select a channel</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label><label>Trend item<select name="trend_item_id" defaultValue=""><option value="">No linked trend</option>{trends.map(trend => <option key={trend.id} value={trend.id}>{trend.title} ({Math.round(trend.trend_score)})</option>)}</select></label><label>Format<select name="format"><option value="short">Short</option><option value="long">Long-form</option></select></label>{[["engagement_potential", "Engagement"], ["audience_relevance", "Audience fit"], ["originality", "Originality"], ["research_quality", "Research quality"], ["competition", "Competition (optional)"]].map(([name, label]) => <label className="score-field" key={name}>{label}<input name={name} type="number" min="0" max="100" step="1" required={name !== "competition"} placeholder="0–100" /></label>)}<button className="primary" type="submit" disabled={!channels.length}>＋ &nbsp;Add opportunity</button></form>
    {error && <p className="error-message">{error}</p>}
    <div className="idea-list">{ideas.map(idea => <article className="channel-row" key={idea.id}><div className="score-pill">{Math.round(idea.opportunity_score)}<small>SCORE</small></div><div><strong>{idea.title}</strong><p>{idea.format === "short" ? "Short" : "Long-form"} · {channels.find(c => c.id === idea.channel_id)?.name ?? "Channel"} · {idea.status}</p></div></article>)}</div>
  </main>;
}
