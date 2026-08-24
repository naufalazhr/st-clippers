"use client";

import { useState } from "react";
import { History, Trash2 } from "lucide-react";
import { statusCopy } from "../../../lib/constants";
import type { ClipJob } from "../../../types/clip.type";
import "./HistoryTable.css";

type SortKey = "date" | "status";
type SortState = { key: SortKey; dir: 1 | -1 };

const STATUS_ORDER: Record<string, number> = {
  running: 0,
  queued: 1,
  completed: 2,
  failed: 3,
};

interface HistoryTableProps {
  jobs: ClipJob[];
  loading?: boolean;
  onSelectJob: (job: ClipJob) => void;
  onDeleteAll: () => void;
  onDeleteJob: (jobId: string) => void;
  onViewChange: (v: "clip") => void;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function truncateUrl(url: string, max = 42): string {
  if (!url || url.length <= max) return url;
  return url.slice(0, max - 1) + "…";
}

export function HistoryTable({
  jobs,
  loading,
  onSelectJob,
  onDeleteAll,
  onDeleteJob,
  onViewChange,
}: HistoryTableProps) {
  const [sort, setSort] = useState<SortState>({ key: "date", dir: -1 });
  const [nameQuery, setNameQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const toggleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: (prev.dir * -1) as 1 | -1 }
        : { key, dir: key === "date" ? -1 : 1 },
    );
  };

  const filtered = jobs.filter((item) => {
    const name = item.request.name || item.request.url || item.id;
    if (nameQuery && !name.toLowerCase().includes(nameQuery.toLowerCase())) {
      return false;
    }
    if (dateFrom || dateTo) {
      const d = new Date(item.created_at);
      const localDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (dateFrom && localDate < dateFrom) return false;
      if (dateTo && localDate > dateTo) return false;
    }
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sort.key === "date") {
      return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * sort.dir;
    }
    const oa = STATUS_ORDER[a.status] ?? 9;
    const ob = STATUS_ORDER[b.status] ?? 9;
    return (oa - ob) * sort.dir;
  });

  const handleRowClick = (job: ClipJob) => {
    onSelectJob(job);
    onViewChange("clip");
  };

  const sortIndicator = (key: SortKey) =>
    sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : "";

  if (loading && jobs.length === 0) {
    return (
      <table className="historyTable">
        <thead>
          <tr>
            <th>Nama</th>
            <th>Tanggal</th>
            <th>Sumber</th>
            <th>Status</th>
            <th>Klip</th>
            <th className="historyTable-actionsCol" />
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 5 }, (_, i) => (
            <tr key={i}>
              <td colSpan={6}>
                <div className="skeleton skeleton-row" style={{ animationDelay: `${i * 80}ms` }} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="historyTable-empty">
        <div className="historyTable-emptyIcon">
          <History size={40} />
        </div>
        <h3 className="historyTable-emptyTitle hint-line">Belum ada riwayat</h3>
        <p className="historyTable-emptyHint hint-line">
          Proses klip yang selesai akan muncul di sini.
        </p>
        <p className="historyTable-emptyHint hint-line" style={{ opacity: 0.5 }}>
          Mulai dari tab Klip Baru untuk memotong video pertama Anda.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="historyTable-filters">
        <input
          type="text"
          placeholder="Cari nama project…"
          aria-label="Cari nama project"
          value={nameQuery}
          onChange={(e) => setNameQuery(e.target.value)}
        />
        <label>
          Dari
          <input type="date" aria-label="Tanggal mulai filter" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          Sampai
          <input type="date" aria-label="Tanggal akhir filter" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        {(nameQuery || dateFrom || dateTo) && (
          <button type="button" className="filterResetBtn" onClick={() => { setNameQuery(""); setDateFrom(""); setDateTo(""); }}>
            Reset
          </button>
        )}
      </div>
      <table className="historyTable">
        <thead>
          <tr>
            <th>Nama</th>
            <th>
              <button
                type="button"
                className="historyTable-sortBtn"
                onClick={() => toggleSort("date")}
              >
                Tanggal{sortIndicator("date")}
              </button>
            </th>
            <th>Sumber</th>
            <th>
              <button
                type="button"
                className="historyTable-sortBtn"
                onClick={() => toggleSort("status")}
              >
                Status{sortIndicator("status")}
              </button>
            </th>
            <th>Klip</th>
            <th className="historyTable-actionsCol">
              <button
                type="button"
                className="iconButton dangerIconButton"
                onClick={onDeleteAll}
                title="Hapus Semua Riwayat"
              >
                <Trash2 size={16} />
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => {
            const count = item.clips.length
              ? `${item.clips.length} klip`
              : `${item.candidates.length} kandidat`;

            return (
              <tr
                key={item.id}
                className="historyTable-row"
                onClick={() => handleRowClick(item)}
              >
                <td className="historyTable-nameCell">{item.request.name?.trim() || truncateUrl(item.request.url) || item.id}</td>
                <td className="timecode">{formatDate(item.created_at)}</td>
                <td className="historyTable-source" title={item.request.url || item.id}>
                  {truncateUrl(item.request.url) || item.id}
                </td>
                <td>
                  <span className={`statusBadge status-${item.status}`}>
                    {statusCopy[item.status]}
                  </span>
                </td>
                <td className="timecode">{count}</td>
                <td className="historyTable-actionsCol">
                  <button
                    type="button"
                    className="iconButton dangerIconButton"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm("Hapus project ini?")) onDeleteJob(item.id);
                    }}
                    title="Hapus project"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
