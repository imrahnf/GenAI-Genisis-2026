"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Video, RotateCcw, Trash2, ChevronDown, ChevronRight, FileText } from "lucide-react";
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
      <main className="min-h-screen bg-zinc-950 text-zinc-50 p-8">
        <p className="text-zinc-400 font-mono">Loading sandbox…</p>
        <Link href="/" className="inline-block mt-4 text-sm text-zinc-400 hover:text-white transition-colors font-sans">
          ← Back to control panel
        </Link>
      </main>
    );
  }

  if (error || !sandbox) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-50 p-8">
        <p className="text-red-400">{error || "Sandbox not found."}</p>
        <Link href="/" className="inline-block mt-4 text-sm text-zinc-400 hover:text-white transition-colors font-sans">
          ← Back to control panel
        </Link>
      </main>
    );
  }

  const status = sandbox.expires_at && Date.now() / 1000 > sandbox.expires_at ? "Expired" : "Running";

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50 font-sans">
      <div className="flex flex-col gap-10 p-8 max-w-[1070px] mx-auto pb-12">
        <div className="flex gap-[45px] items-start">
          <div className="w-[320px] h-[200px] shrink-0 rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden relative">
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-zinc-500 text-sm font-mono">Sandbox preview</span>
            </div>
          </div>
          <div className="flex flex-col flex-1 min-w-0 py-2">
            <h1 className="text-[20px] font-normal text-zinc-50 m-0 leading-none mb-4 font-mono tracking-tight">{sandbox.sandbox_id}</h1>
            <p className="text-[14px] text-zinc-400 mb-1 font-sans">
              Preset <strong className="text-zinc-50 font-mono">{sandbox.preset ?? "preset"}</strong> ·{" "}
              <span
                className={`inline-flex px-2 py-0.5 rounded-full text-xs font-mono ${
                  status === "Expired" ? "bg-red-500/20 text-red-400" : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                }`}
              >
                {status}
              </span>
              {sandbox.template_id && (
                <span className="ml-1.5 inline-flex px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono">
                  Replay
                </span>
              )}
            </p>
            <a
              href={sandbox.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[18px] text-zinc-50 hover:text-cyan-400 transition-colors leading-none block mb-2 font-mono"
            >
              {sandbox.url}
            </a>
            <p className="text-[14px] text-zinc-400 mb-4 font-sans">
              <strong className="text-zinc-50">Goal:</strong> {sandbox.goal}
            </p>
            <p className="text-[14px] text-zinc-400 mb-6 font-sans">
              <strong className="text-zinc-50">Expires:</strong> {formatExpires(sandbox.expires_at)}
            </p>
            <div className="flex items-center gap-4 mt-auto">
              <span className="text-zinc-400 text-[14px] font-mono">
                Logs ({sandbox.logs?.length ?? 0})
              </span>
              {sandbox.capture_active ? (
                <button
                  type="button"
                  onClick={() => handleCaptureStop(false, "")}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 transition-colors text-[14px] font-medium border border-cyan-500/30 text-white"
                >
                  <Video size={16} />
                  Stop recording
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleCaptureStart}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 transition-colors text-[14px] font-medium border border-cyan-500/30"
                >
                  <Video size={16} />
                  Capture
                </button>
              )}
              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-zinc-900 text-white hover:bg-zinc-800 transition-colors text-[14px] font-medium border border-zinc-700"
              >
                <RotateCcw size={16} />
                Reset
              </button>
              <button
                type="button"
                onClick={handleDestroy}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-zinc-900 text-white hover:bg-zinc-800 transition-colors text-[14px] font-medium border border-zinc-700"
              >
                <Trash2 size={16} />
                Destroy
              </button>
            </div>
          </div>
        </div>

        <div className="h-px bg-zinc-800 w-full" />

        <div className="card-dev overflow-hidden">
          <button
            type="button"
            onClick={() => setLogsOpen(!logsOpen)}
            className="w-full flex items-center gap-4 px-6 py-6 hover:bg-zinc-800/50 transition-colors"
          >
            {logsOpen ? <ChevronDown size={20} className="text-zinc-500" /> : <ChevronRight size={20} className="text-zinc-500" />}
            <FileText size={18} className="text-zinc-500 flex-shrink-0" />
            <span className="text-[20px] font-normal text-zinc-50 font-sans tracking-tight">Agent Logs</span>
            {sandbox.logs && sandbox.logs.length > 0 && (
              <span className="flex items-center gap-1.5 text-[11px] text-cyan-400 ml-auto font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                Live
              </span>
            )}
          </button>
          {logsOpen && (
            <div className="px-6 md:px-[60px] pb-8 pt-2 border-t border-zinc-800">
              <div className="flex flex-col gap-2 font-mono text-[13px]">
                {!sandbox.logs?.length ? (
                  <span className="text-zinc-500">No logs.</span>
                ) : (
                  sandbox.logs.map((l, i) => (
                    <div key={i} className="flex items-start gap-4 text-zinc-500 hover:text-zinc-400 transition-colors py-0.5">
                      <span className="text-zinc-600 flex-shrink-0 w-[70px]">
                        {new Date(l.ts * 1000).toISOString().slice(11, 19)}
                      </span>
                      <span
                        className={`flex-shrink-0 w-[52px] ${
                          l.type === "error" ? "text-red-400" : l.type === "llm" ? "text-cyan-400" : "text-zinc-500"
                        }`}
                      >
                        [{l.type}]
                      </span>
                      <span className="text-zinc-50 flex-1 break-all">{l.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors font-sans"
        >
          <ArrowLeft size={16} />
          Back to control panel
        </Link>
      </div>
    </main>
  );
}
