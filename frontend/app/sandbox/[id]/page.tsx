"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Video, RotateCcw, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import type { Sandbox } from "../../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function formatExpires(expiresAt: number | string | null | undefined): string {
  if (expiresAt == null || expiresAt === "") return "—";
  const t = typeof expiresAt === "string" ? parseFloat(expiresAt) : expiresAt;
  if (Number.isNaN(t)) return "—";
  const d = new Date(t * 1000);
  const now = Date.now();
  if (d.getTime() <= now) return "Expired";
  const minLeft = Math.round((d.getTime() - now) / 60000);
  return `${d.toLocaleTimeString()} (in ${minLeft} min)`;
}

export default function SandboxDetail({ params }: { params: { id: string } }) {
  const [sandbox, setSandbox] = useState<Sandbox | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logsOpen, setLogsOpen] = useState(true);

  const fetchSandbox = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/status`);
      const data = await r.json();
      const found = (data.sandboxes as Sandbox[] | undefined)?.find((s) => s.sandbox_id === params.id);
      if (!found) {
        setError("Sandbox not found or no longer running.");
        setSandbox(null);
      } else {
        setSandbox(found);
        setError(null);
      }
    } catch {
      setError("Failed to load sandbox status.");
      setSandbox(null);
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    fetchSandbox();
  }, [fetchSandbox]);

  useEffect(() => {
    if (!sandbox) return;
    const t = setInterval(fetchSandbox, 4000);
    return () => clearInterval(t);
  }, [sandbox, fetchSandbox]);

  const handleCaptureStart = async () => {
    try {
      await fetch(`${API_BASE}/capture/start/${params.id}`, { method: "POST" });
      await fetchSandbox();
    } catch {
      await fetchSandbox();
    }
  };

  const handleCaptureStop = async (saveAsTemplate: boolean, name: string) => {
    try {
      await fetch(`${API_BASE}/capture/stop/${params.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ save_as_template: saveAsTemplate, name: name || "Unnamed template" }),
      });
      await fetchSandbox();
    } catch {
      await fetchSandbox();
    }
  };

  const handleReset = async () => {
    try {
      const r = await fetch(`${API_BASE}/reset/${params.id}`, { method: "POST" });
      if (!r.ok) {
        const data = await r.json();
        throw new Error(data.detail);
      }
      await fetchSandbox();
    } catch {
      await fetchSandbox();
    }
  };

  const handleDestroy = async () => {
    try {
      await fetch(`${API_BASE}/destroy/${params.id}`, { method: "POST" });
      window.location.href = "/";
    } catch {
      await fetchSandbox();
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-background text-foreground p-8">
        <p className="text-muted-foreground">Loading sandbox…</p>
        <Link href="/" className="inline-block mt-4 text-sm text-muted-foreground hover:text-foreground">
          ← Back to control panel
        </Link>
      </main>
    );
  }

  if (error || !sandbox) {
    return (
      <main className="min-h-screen bg-background text-foreground p-8">
        <p className="text-destructive">{error || "Sandbox not found."}</p>
        <Link href="/" className="inline-block mt-4 text-sm text-muted-foreground hover:text-foreground">
          ← Back to control panel
        </Link>
      </main>
    );
  }

  const status = sandbox.expires_at && Date.now() / 1000 > sandbox.expires_at ? "Expired" : "Running";

  return (
    <main className="min-h-screen bg-background text-foreground font-sans">
      <div className="flex flex-col gap-10 p-8 max-w-[1070px] mx-auto pb-12">
        <div className="flex gap-[45px] items-start">
          <div className="w-[320px] h-[200px] shrink-0 rounded-2xl border-2 border-border bg-secondary overflow-hidden relative">
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-muted-foreground text-sm">Sandbox preview</span>
            </div>
          </div>
          <div className="flex flex-col flex-1 min-w-0 py-2">
            <h1 className="text-[20px] font-normal text-foreground m-0 leading-none mb-4">{sandbox.sandbox_id}</h1>
            <p className="text-[14px] text-muted-foreground mb-1">
              Preset <strong className="text-foreground">{sandbox.preset ?? "preset"}</strong> ·{" "}
              <span
                className={`inline-flex px-2 py-0.5 rounded-full text-xs ${
                  status === "Expired" ? "bg-destructive/20 text-destructive" : "bg-accent/20 text-accent border border-accent/30"
                }`}
              >
                {status}
              </span>
              {sandbox.template_id && (
                <span className="ml-1.5 inline-flex px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  Replay
                </span>
              )}
            </p>
            <a
              href={sandbox.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[18px] text-foreground hover:text-accent transition-colors leading-none block mb-2"
            >
              {sandbox.url}
            </a>
            <p className="text-[14px] text-muted-foreground mb-4">
              <strong className="text-foreground">Goal:</strong> {sandbox.goal}
            </p>
            <p className="text-[14px] text-muted-foreground mb-6">
              <strong className="text-foreground">Expires:</strong> {formatExpires(sandbox.expires_at)}
            </p>
            <div className="flex items-center gap-4 mt-auto">
              <span className="text-muted-foreground text-[14px]">
                Logs ({sandbox.logs?.length ?? 0})
              </span>
              {sandbox.capture_active ? (
                <button
                  type="button"
                  onClick={() => handleCaptureStop(false, "")}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent/10 text-accent hover:bg-accent/20 transition-colors text-[14px] font-medium border border-accent/20"
                >
                  <Video size={16} />
                  Stop recording
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleCaptureStart}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent/10 text-accent hover:bg-accent/20 transition-colors text-[14px] font-medium border border-accent/20"
                >
                  <Video size={16} />
                  Capture
                </button>
              )}
              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-secondary text-foreground hover:bg-secondary/80 transition-colors text-[14px] font-medium"
              >
                <RotateCcw size={16} />
                Reset
              </button>
              <button
                type="button"
                onClick={handleDestroy}
                className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-secondary text-foreground hover:bg-secondary/80 transition-colors text-[14px] font-medium"
              >
                <Trash2 size={16} />
                Destroy
              </button>
            </div>
          </div>
        </div>

        <div className="h-px bg-border w-full" />

        <div className="border border-border rounded-2xl bg-card overflow-hidden">
          <button
            type="button"
            onClick={() => setLogsOpen(!logsOpen)}
            className="w-full flex items-center gap-4 px-5 py-6 hover:bg-secondary/20 transition-colors"
          >
            {logsOpen ? <ChevronDown size={20} className="text-muted-foreground" /> : <ChevronRight size={20} className="text-muted-foreground" />}
            <span className="text-[20px] font-normal text-foreground">Agent Logs</span>
          </button>
          {logsOpen && (
            <div className="px-6 pb-8 pt-2 border-t border-border/50">
              <div className="flex flex-col gap-2 font-mono text-[13px]">
                {!sandbox.logs?.length ? (
                  <span className="text-muted-foreground">No logs.</span>
                ) : (
                  sandbox.logs.map((l, i) => (
                    <div key={i} className="flex items-start gap-4">
                      <span className="text-muted-foreground/70 flex-shrink-0 w-[80px]">
                        {new Date(l.ts * 1000).toISOString().slice(11, 19)}
                      </span>
                      <span className="text-muted-foreground/50 flex-shrink-0 w-[50px]">[{l.type}]</span>
                      <span className="text-foreground flex-1 break-all">{l.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft size={16} />
          Back to control panel
        </Link>
      </div>
    </main>
  );
}
