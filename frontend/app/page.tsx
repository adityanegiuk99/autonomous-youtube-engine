const sections = ["Overview", "Channels", "Trend Radar", "Content Pipeline", "Video Studio", "Approval Center", "Publishing", "Analytics", "AI Insights"];

export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">A</span><span>AYE<span className="brand-sub">STUDIO</span></span></div>
        <p className="nav-label">WORKSPACE</p>
        <nav>{sections.map((section, index) => <a className={index === 0 ? "nav-item active" : "nav-item"} href={section === "Channels" ? "/channels" : "#"} key={section}><span className="nav-icon">{["⌂", "▣", "◉", "▤", "▶", "✓", "↗", "▥", "✧"][index]}</span>{section}</a>)}</nav>
        <div className="sidebar-bottom"><div className="avatar">A</div><div><strong>Local workspace</strong><small>Foundation setup</small></div></div>
      </aside>
      <section className="content">
        <header className="topbar"><span>Workspace <b>/</b> Overview</span><div className="top-actions"><span className="status"><i /> SYSTEM READY</span><button className="profile">A</button></div></header>
        <div className="page-wrap">
          <div className="heading-row"><div><p className="eyebrow">SUNDAY, NOVEMBER 15, 2026</p><h1>Good morning</h1><p className="muted">Your content operation, at a glance.</p></div><button className="primary" disabled title="Trend discovery arrives in Phase 2">＋ &nbsp;New content idea</button></div>
          <div className="notice"><span>✦</span><div><strong>Foundation workspace</strong><p>Channel setup is being built. Trend discovery and content production will appear as those phases are implemented.</p></div><span className="notice-tag">PHASE 1</span></div>
          <div className="stats-grid">{[["CONNECTED CHANNELS", "—", "Set up your first channel"], ["IN PRODUCTION", "—", "No active workflows"], ["AWAITING APPROVAL", "—", "Approval center not active"], ["MONTHLY SPEND", "₹0", "No provider usage yet"]].map(([label, value, hint]) => <article className="stat-card" key={label}><div className="stat-title">{label}<span>↗</span></div><div className="stat-value">{value}</div><p>{hint}</p></article>)}</div>
          <div className="section-heading"><div><h2>Channel workspace</h2><p className="muted">Your channel identities and publishing health.</p></div><a className="text-button" href="/channels">Manage channels <span>→</span></a></div>
          <article className="empty-card"><div className="empty-icon">▣</div><h3>Configure your channel workspace</h3><p>Add channel identities and niches before connecting YouTube.</p><a className="secondary" href="/channels">＋ &nbsp;Set up channels</a><small>YouTube connection is not available yet.</small></article>
          <footer>AYE STUDIO <span>•</span> FOUNDATION PREVIEW</footer>
        </div>
      </section>
    </main>
  );
}
