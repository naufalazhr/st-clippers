"use client";

import { useCallback, useEffect, useState } from "react";
import { Moon, PanelLeft, Sun } from "lucide-react";
import { API_BASE } from "../../../lib/apiClient";
import { toggleTheme } from "../../../lib/theme";
import { LogTail } from "../LogTail";
import type { ClipJob } from "../../../types/clip.type";
import "./StatusBar.css";

type HealthStatus = "connecting" | "ok" | "error";

type StatusBarProps = {
  job: ClipJob | null;
  logs: string[];
  showSidebar: boolean;
  onToggleSidebar: () => void;
};

export function StatusBar({
  job,
  logs,
  showSidebar,
  onToggleSidebar,
}: StatusBarProps) {
  const [health, setHealth] = useState<HealthStatus>("connecting");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const stored = localStorage.getItem("theme") as "dark" | "light" | null;
    if (stored) setTheme(stored);
  }, []);

  const handleToggleTheme = useCallback(() => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
    toggleTheme();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (!cancelled) setHealth(res.ok ? "ok" : "error");
      } catch {
        if (!cancelled) setHealth("error");
      }
    };
    check();
    const id = setInterval(check, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const jobTitle = (() => {
    if (!job) return "";
    const url = job.request.url;
    if (url) {
      try {
        const u = new URL(url);
        return u.hostname.replace("www.", "") + u.pathname.slice(0, 24);
      } catch {
        return url.slice(0, 32);
      }
    }
    return job.id.slice(0, 8);
  })();

  return (
    <div className="statusBar">
      <div className="statusBar-log"><LogTail logs={logs} /></div>

      <div className="statusBar-strip">
        <div className="statusBar-left">
          <span className={`healthDot healthDot--${health}`} />
          <span className="statusBar-label">Backend</span>
        </div>

        <div className="statusBar-center">
          {job ? (
            <>
              <span className={`statusBadge status-${job.status}`}>{job.status}</span>
              <span className="statusBar-title">{jobTitle}</span>
            </>
          ) : (
            <span className="statusBar-idle">No active job</span>
          )}
        </div>

        <div className="statusBar-right">
          <button
            className="statusBar-iconBtn"
            type="button"
            onClick={handleToggleTheme}
            title="Toggle theme"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </button>
          <button
            className="statusBar-iconBtn"
            type="button"
            onClick={onToggleSidebar}
            title="Toggle sidebar"
            aria-label="Toggle sidebar"
            data-active={showSidebar}
          >
            <PanelLeft size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
