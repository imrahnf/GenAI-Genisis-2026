"use client";

import React, { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type LogEntry = { ts: number; type: string; message: string };

type Sandbox = {
  sandbox_id: string;
  url: string;
  port: number;
  goal: string;
  preset?: string;
  template_id?: string | null;
  expires_at?: number | null;
  capture_active?: boolean;
  capture_steps_count?: number;
  logs?: LogEntry[];
};

function formatExpires(expiresAt: number | string | null | undefined) {
  if (expiresAt == null || expiresAt === "") return "—";
  const t = typeof expiresAt === "string" ? parseFloat(expiresAt) : expiresAt;
  if (Number.isNaN(t)) return "—";
  const d = new Date(t * 1000);
  const now = Date.now();
  if (d.getTime() <= now) return "expired";
  const minLeft = Math.round((d.getTime() - now) / 60000);
  return `${d.toLocaleTimeString()} (in ${minLeft} min)`;
}

export default function SandboxDetail({ params }: { params: { id: string } }) {
  const [sandbox, setSandbox] = useState<Sandbox | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSandbox() {
      try {
        const r = await fetch(`${API_BASE}/status`);
        const data = await r.json();
        const found = (data.sandboxes as Sandbox[] | undefined)?.find(
          (s) => s.sandbox_id === params.id,
        );
        if (!found) {
          setError("Sandbox not found or no longer running.");
        } else {
          setSandbox(found);
        }
      } catch {
        setError("Failed to load sandbox status.");
      } finally {
        setLoading(false);
      }
    }
    fetchSandbox();
  }, [params.id]);

  if (loading) {
    return (
      <main className="dashboard">
        <p className="muted">Loading sandbox…</p>
      </main>
    );
  }

  if (error || !sandbox) {
    return (
      <main className="dashboard">
        <p className="message error">{error || "Sandbox not found."}</p>
        <a href="/" className="muted">
          ← Back to control panel
        </a>
      </main>
    );
  }

  const status = sandbox.expires_at && Date.now() / 1000 > sandbox.expires_at ? "Expired" : "Running";

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <h1>Sandbox detail</h1>
        <p className="tagline">
          Preset <strong>{sandbox.preset ?? "preset"}</strong> ·{" "}
          <span className="preset-chip">{status}</span>
          {sandbox.template_id && <span className="preset-chip">Replay</span>}
        </p>
      </header>

      <section className="config-panel">
        <h2>Overview</h2>
        <p>
          <strong>Sandbox ID:</strong> {sandbox.sandbox_id}
        </p>
        <p>
          <strong>URL:</strong>{" "}
          <a href={sandbox.url} target="_blank" rel="noopener noreferrer">
            {sandbox.url}
          </a>
        </p>
        <p>
          <strong>Goal:</strong> {sandbox.goal}
        </p>
        <p>
          <strong>Expires:</strong> {formatExpires(sandbox.expires_at)}
        </p>
      </section>

      <section className="sandboxes-section">
        <h2>Logs</h2>
        <div className="logs-cell">
          <pre>
            {!sandbox.logs || sandbox.logs.length === 0
              ? "No logs."
              : sandbox.logs
                  .map(
                    (l) =>
                      `${new Date(l.ts * 1000)
                        .toISOString()
                        .slice(11, 19)} [${l.type}] ${l.message}`,
                  )
                  .join("\n")}
          </pre>
        </div>
      </section>

      <p>
        <a href="/" className="muted">
          ← Back to control panel
        </a>
      </p>
    </main>
  );
}

