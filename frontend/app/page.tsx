"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./lib/api";

const sections = ["Overview", "Channels", "Trend Radar", "Content Pipeline", "Video Studio", "Approval Center", "Publishing", "Analytics", "AI Insights", "Cost Monitor"];
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
type Summary = {
  configured_channels: number; active_channels: number; tracked_trends: number; content_ideas: number;
  production_renders: number; qa_passed_without_decision_renders: number; qa_failed_renders: number;
  recent_ideas: { id: string; title: string; format: string; status: string; opportunity_score: number }[];
  recent_trends: { id: string; title: string; trend_score: number }[];
};

export default function Home() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiFetch(`${api}/dashboard/summary`).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not load the workspace overview");
      if (!cancelled) setSummary(data);
    }).catch(reason => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load the workspace overview"); });
    return () => { cancelled = true; };
  }, []);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">A</span><span>AYE<span className="brand-sub">STUDIO</span></span></div>
        <p className="nav-label">WORKSPACE</p>
        <nav>{sections.map((section, index) => <a className={index === 0 ? "nav-item active" : "nav-item"} href={section === "Channels" ? "/channels" : section === "Trend Radar" ? "/trends" : section === "Content Pipeline" ? "/ideas" : section === "Video Studio" ? "/studio" : section === "Approval Center" ? "/approvals" : section === "Publishing" ? "/publishing" : section === "Analytics" ? "/analytics" : section === "Cost Monitor" ? "/operations" : "#"} key={section}><span className="nav-icon">{["⌂", "▣", "◉", "▤", "▶", "✓", "↗", "▥", "✧", "◷"][index]}</span>{section}</a>)}</nav>
        <div className="sidebar-bottom"><div className="avatar">A</div><div><strong>Local workspace</strong><small>Provider setup pending</small></div></div>
      </aside>
      <section className="content">
        <header className="topbar"><span>Workspace <b>/</b> Overview</span><div className="top-actions"><span className="status"><i /> LOCAL MODE</span><button className="profile">A</button></div></header>
        <div className="page-wrap">
          <div className="heading-row"><div><p className="eyebrow">{new Intl.DateTimeFormat(undefined, { dateStyle: "full" }).format(new Date()).toUpperCase()}</p><h1>Workspace overview</h1><p className="muted">Your content operation, at a glance.</p></div><a className="primary dashboard-action" href="/ideas">＋ &nbsp;New content idea</a></div>
          <div className="notice"><span>✦</span><div><strong>Provider-independent workflows are available</strong><p>Manage configured channels, RSS trends, content versions, production reviews, and imported analytics. AI generation and YouTube publishing still need provider setup.</p></div><span className="notice-tag">LOCAL</span></div>
          {error && <p className="error-message">{error}</p>}
          <div className="stats-grid">{[["CONFIGURED CHANNELS", summary ? String(summary.configured_channels) : "—", summary ? `${summary.active_channels} active · OAuth not connected` : "Loading overview"], ["TRACKED TRENDS", summary ? String(summary.tracked_trends) : "—", "Stored RSS trend candidates"], ["CONTENT IDEAS", summary ? String(summary.content_ideas) : "—", "Human-scored opportunities"], ["QA-PASSED, NO DECISION", summary ? String(summary.qa_passed_without_decision_renders) : "—", summary ? `${summary.production_renders} total renders · ${summary.qa_failed_renders} QA failures · some may be stale` : "Renders without a recorded decision"]].map(([label, value, hint]) => <article className="stat-card" key={label}><div className="stat-title">{label}</div><div className="stat-value">{value}</div><p>{hint}</p></article>)}</div>
          <div className="section-heading"><div><h2>Recent content ideas</h2><p className="muted">Latest opportunities in your pipeline.</p></div><a className="text-button" href="/ideas">Open content pipeline <span>→</span></a></div>
          {summary?.recent_ideas.length ? <div className="channel-list">{summary.recent_ideas.map(idea => <article className="channel-row" key={idea.id}><div><strong>{idea.title}</strong><p>{idea.format === "short" ? "Short" : "Long-form"} · {idea.status} · Score {Math.round(idea.opportunity_score)}</p></div><a className="text-button" href={`/studio?idea=${encodeURIComponent(idea.id)}`}>Open Studio →</a></article>)}</div> : <article className="empty-card"><h3>{error ? "Overview unavailable" : summary ? "No content ideas yet" : "Loading content pipeline…"}</h3><p>{error ? "Check your API connection and refresh the page." : "Create an opportunity from a trend or enter your own idea to begin."}</p><a className="secondary" href="/ideas">Open content pipeline</a></article>}
          <div className="section-heading"><div><h2>Trend Radar</h2><p className="muted">Stored candidates from configured RSS sources.</p></div><a className="text-button" href="/trends">Open Trend Radar <span>→</span></a></div>
          {summary?.recent_trends.length ? <div className="channel-list">{summary.recent_trends.map(trend => <article className="channel-row" key={trend.id}><div><strong>{trend.title}</strong><p>Heuristic score {Math.round(trend.trend_score)} · not a view prediction</p></div></article>)}</div> : <article className="empty-card"><h3>{error ? "Overview unavailable" : summary ? "No trends stored" : "Loading trend data…"}</h3><p>{error ? "Check your API connection and refresh the page." : "Configure trusted RSS feeds to discover candidates."}</p><a className="secondary" href="/trends">Configure Trend Radar</a></article>}
          <footer>AYE STUDIO <span>•</span> LOCAL WORKSPACE</footer>
        </div>
      </section>
    </main>
  );
}
