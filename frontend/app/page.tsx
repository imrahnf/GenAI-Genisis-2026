"use client";

import React, { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type LogEntry = {
  ts: number;
  type: string;
  message: string;
};

type Sandbox = {
  sandbox_id: string;
  url: string;
  port: number;
  goal: string;
  logs?: LogEntry[];
};

export default function Home() {
  const [goal, setGoal] = useState("Add a new food every 10 seconds.");
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedLogs, setExpandedLogs] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/status`);
      const data = await r.json();
      setSandboxes(data.sandboxes || []);
    } catch {
      setSandboxes([]);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 4000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  async function handleLaunch(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Launch failed");
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Launch failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDestroy(sandboxId: string) {
    try {
      await fetch(`${API_BASE}/destroy/${sandboxId}`, { method: "POST" });
      await fetchStatus();
    } catch {
      await fetchStatus();
    }
  }

  return (
    <main>
      <h1>DemoForge</h1>
      <form onSubmit={handleLaunch}>
        <label htmlFor="goal">Agent goal</label>
        <textarea
          id="goal"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="e.g. Add a new food every 10 seconds."
        />
        <button type="submit" disabled={loading}>
          {loading ? "Launching…" : "Launch sandbox"}
        </button>
      </form>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <h2>Active sandboxes</h2>
      {sandboxes.length === 0 ? (
        <p>No sandboxes running. Launch one above.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>URL</th>
              <th>Goal</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sandboxes.map((s) => (
              <React.Fragment key={s.sandbox_id}>
                <tr>
                  <td>{s.sandbox_id}</td>
                  <td>
                    <a href={s.url} target="_blank" rel="noopener noreferrer">
                      {s.url}
                    </a>
                  </td>
                  <td>{s.goal}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => setExpandedLogs(expandedLogs === s.sandbox_id ? null : s.sandbox_id)}
                    >
                      {expandedLogs === s.sandbox_id ? "Hide logs" : "Logs"}
                      {s.logs?.length ? ` (${s.logs.length})` : ""}
                    </button>
                    {" "}
                    <button
                      type="button"
                      className="danger"
                      onClick={() => handleDestroy(s.sandbox_id)}
                    >
                      Destroy
                    </button>
                  </td>
                </tr>
                {expandedLogs === s.sandbox_id && (
                  <tr key={`${s.sandbox_id}-logs`}>
                    <td colSpan={4} style={{ padding: "0", verticalAlign: "top" }}>
                      <div style={{ background: "#f5f5f5", padding: "0.75rem", maxHeight: "300px", overflow: "auto", fontFamily: "monospace", fontSize: "0.8rem", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                        {(!s.logs || s.logs.length === 0) ? "No agent logs yet. Logs appear as the agent runs." : s.logs.map((l, i) => (
                          <div key={i} style={{ marginBottom: "0.25rem", borderBottom: "1px solid #eee" }}>
                            <span style={{ color: "#666" }}>{new Date(l.ts * 1000).toISOString().slice(11, 19)} [{l.type}] </span>
                            {l.message}
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
