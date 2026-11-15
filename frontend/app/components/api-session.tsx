"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import { clearApiToken, saveApiToken } from "../lib/api";
import "../session.css";

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function ApiSession({ children }: { children: ReactNode }) {
  const [token, setToken] = useState("");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);

  async function verify(candidate: string) {
    const response = await fetch(`${api}/auth/verify`, { headers: { Authorization: `Bearer ${candidate}` } });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail ?? "API token could not be verified");
    }
  }

  useEffect(() => {
    const existing = window.sessionStorage.getItem("aye_api_token");
    if (!existing) { setChecking(false); return; }
    verify(existing).then(() => { setToken(existing); setReady(true); })
      .catch(() => { clearApiToken(); setError("Session token is invalid or the API is not ready. Enter the configured token again."); })
      .finally(() => setChecking(false));
  }, []);

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setChecking(true);
    try { await verify(token); saveApiToken(token); setReady(true); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not verify token"); }
    finally { setChecking(false); }
  }

  function disconnect() { clearApiToken(); setToken(""); setReady(false); }

  if (checking) return <main className="session-screen"><p>Checking local workspace…</p></main>;
  if (!ready) return <main className="session-screen"><form className="session-card" onSubmit={connect}><span className="brand-mark">A</span><p className="eyebrow">LOCAL WORKSPACE</p><h1>Connect to AYE</h1><p>Enter the bearer token configured in your local <code>.env</code> file. It stays in this browser session.</p><label>API token<input type="password" autoComplete="current-password" value={token} onChange={event => setToken(event.target.value)} required minLength={32} /></label><button className="primary" type="submit" disabled={checking}>{checking ? "Checking…" : "Connect"}</button>{error && <p className="error-message">{error}</p>}<small>Local single-owner access · session storage only</small></form></main>;
  return <><div className="session-bar"><span>Local API session</span><button onClick={disconnect}>Disconnect</button></div>{children}</>;
}
