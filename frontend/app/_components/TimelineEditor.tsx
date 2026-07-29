"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { getOutputUrl, recutClip } from "../../lib/apiClient";
import { snapBoundary } from "../../lib/snapBoundary";
import type { ClipCandidate, TimelineData, TranscriptSegment } from "../../types/clip.type";
import type { WaveformHandle } from "./WaveformWrapper";

const WaveformWrapper = dynamic(() => import("./WaveformWrapper"), { ssr: false });

type TimelineEditorProps = {
  jobId: string;
  candidate: ClipCandidate;
  timeline: TimelineData;
  onRecut: (index: number, start: number, end: number) => Promise<void>;
  onClose: () => void;
};

export function TimelineEditor({ jobId, candidate, timeline, onRecut, onClose }: TimelineEditorProps) {
  const [start, setStart] = useState(candidate.start);
  const [end, setEnd] = useState(candidate.end);
  const [busy, setBusy] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [zoom, setZoom] = useState(50);
  const videoRef = useRef<HTMLVideoElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const waveformRef = useRef<WaveformHandle>(null);
  const dragging = useRef<"start" | "end" | null>(null);
  const duration = timeline.duration || candidate.duration;

  const clampedStart = Math.max(0, Math.min(start, duration - 1));
  const clampedEnd = Math.max(clampedStart + 1, Math.min(end, duration));
  const isChanged = clampedStart !== candidate.start || clampedEnd !== candidate.end;

  const [editedSegments, setEditedSegments] = useState<Record<number, string>>({});
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [segmentErrors, setSegmentErrors] = useState<Record<number, string>>({});
  const [savingTranscript, setSavingTranscript] = useState(false);
  const hasTranscriptEdits = Object.keys(editedSegments).length > 0;

  const handleSegmentChange = (i: number, value: string) => {
    setEditedSegments(prev => ({ ...prev, [i]: value }));
    if (segmentErrors[i]) setSegmentErrors(prev => { const n = { ...prev }; delete n[i]; return n; });
  };

  const handleSegmentBlur = (i: number, value: string) => {
    setEditingIndex(null);
    if (value === timeline.segments[i].text)
      setEditedSegments(prev => { const n = { ...prev }; delete n[i]; return n; });
  };

  const handleSegmentKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, i: number, value: string) => {
    if (e.key === "Enter") handleSegmentBlur(i, value);
    if (e.key === "Escape") {
      setEditingIndex(null);
      setEditedSegments(prev => { const n = { ...prev }; delete n[i]; return n; });
    }
  };

  const handleSaveTranscript = useCallback(async () => {
    const errors: Record<number, string> = {};
    Object.entries(editedSegments).forEach(([k, v]) => {
      if (!v.trim()) errors[Number(k)] = "Teks tidak boleh kosong";
    });
    if (Object.keys(errors).length > 0) { setSegmentErrors(errors); return; }

    const allSegments = timeline.segments.map((s, i) => ({
      start: s.start, end: s.end, text: editedSegments[i] ?? s.text,
    }));

    setSavingTranscript(true);
    try {
      await recutClip(jobId, { index: candidate.index, start: clampedStart, end: clampedEnd, segments: allSegments });
      toast.success("Subtitle diperbarui");
      setEditedSegments({});
      await onRecut(candidate.index, clampedStart, clampedEnd);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan koreksi");
    } finally {
      setSavingTranscript(false);
    }
  }, [editedSegments, timeline.segments, jobId, candidate.index, clampedStart, clampedEnd, onRecut]);

  const snap = useCallback(
    (time: number, segments: TranscriptSegment[]) => snapBoundary(time, segments, duration),
    [duration]
  );

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      const video = videoRef.current;
      if (!video) return;

      switch (e.key) {
        case "i":
        case "I":
          setStart(Math.min(video.currentTime, end - 1));
          break;
        case "o":
        case "O":
          setEnd(Math.max(video.currentTime, start + 1));
          break;
        case "ArrowLeft":
          e.preventDefault();
          video.currentTime = Math.max(0, video.currentTime - (e.shiftKey ? 5 : 1));
          break;
        case "ArrowRight":
          e.preventDefault();
          video.currentTime = Math.min(duration, video.currentTime + (e.shiftKey ? 5 : 1));
          break;
        case " ":
          e.preventDefault();
          video.paused ? video.play().catch(() => {}) : video.pause();
          break;
        case "j":
        case "J":
          video.currentTime = Math.max(0, video.currentTime - 2);
          break;
        case "k":
        case "K":
          video.pause();
          break;
        case "l":
        case "L":
          video.currentTime = Math.min(duration, video.currentTime + 2);
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [start, end, duration]);

  // ── Sync waveform position to video time ────────────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const sync = () => waveformRef.current?.setTime(video.currentTime);
    video.addEventListener("timeupdate", sync);
    return () => video.removeEventListener("timeupdate", sync);
  }, []);

  // ── Zoom slider → wavesurfer ────────────────────────────────────────────
  useEffect(() => {
    waveformRef.current?.setMinPxPerSec(zoom);
  }, [zoom]);

  // ── Drag handles ────────────────────────────────────────────────────────
  const handlePointerDown = useCallback(
    (handle: "start" | "end") => (e: React.PointerEvent) => {
      dragging.current = handle;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      e.preventDefault();
    },
    []
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging.current || !trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      let time = ((e.clientX - rect.left) / rect.width) * duration;
      time = Math.max(0, Math.min(time, duration));
      if (dragging.current === "start") {
        setStart(Math.min(time, end - 1));
      } else {
        setEnd(Math.max(time, start + 1));
      }
    },
    [duration, start, end]
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging.current) return;
      const rect = trackRef.current?.getBoundingClientRect();
      if (rect) {
        let time = ((e.clientX - rect.left) / rect.width) * duration;
        time = Math.max(0, Math.min(time, duration));
        const snapped = snap(time, timeline.segments);
        if (dragging.current === "start") {
          setStart(Math.min(snapped, end - 1));
        } else {
          setEnd(Math.max(snapped, start + 1));
        }
      }
      dragging.current = null;
    },
    [duration, snap, timeline.segments, start, end]
  );

  const handlePreview = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    setPreviewing(true);
    video.currentTime = clampedStart;
    video.play().catch(() => setPreviewing(false));
  }, [clampedStart]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !previewing) return;
    const check = () => {
      if (video.currentTime >= clampedEnd) {
        video.pause();
        setPreviewing(false);
      }
    };
    video.addEventListener("timeupdate", check);
    return () => video.removeEventListener("timeupdate", check);
  }, [previewing, clampedEnd]);

  const handleRecut = useCallback(async () => {
    setBusy(true);
    try {
      await onRecut(candidate.index, clampedStart, clampedEnd);
      onClose();
    } finally {
      setBusy(false);
    }
  }, [candidate.index, clampedStart, clampedEnd, onRecut, onClose]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const startPct = duration > 0 ? (clampedStart / duration) * 100 : 0;
  const endPct = duration > 0 ? (clampedEnd / duration) * 100 : 100;

  const audioUrl = getOutputUrl(timeline.source_url);

  return (
    <div className="timelineEditor">
      <div className="timelineEditorBody">
        <div className="timelineEditorSticky">
          <video
            ref={videoRef}
            src={audioUrl}
            preload="metadata"
            muted
            className="timelineVideo"
          />
        </div>
        <div className="timelineEditorContent">
      <div className="timelineHeader">
        <h4>✂️ Trim clip: {candidate.title}</h4>
        <time className="timelineCodes">
          {formatTime(clampedStart)} — {formatTime(clampedEnd)} ({formatTime(clampedEnd - clampedStart)})
        </time>
      </div>

      {/* ── Waveform ── */}
      <WaveformWrapper
        ref={waveformRef}
        url={audioUrl}
        peaks={timeline.peaks}
        duration={duration}
      />

      {/* ── Zoom slider ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 32 }}>Zoom</span>
        <input
          type="range"
          className="waveformZoom"
          min={20}
          max={300}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
        />
        <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 28 }}>{zoom}px</span>
      </div>

      {/* ── Drag-handle track ── */}
      <div
        className="timelineTrack"
        ref={trackRef}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        style={{ touchAction: "none" }}
      >
        {timeline.segments.map((seg, i) => {
          const left = duration > 0 ? (seg.start / duration) * 100 : 0;
          const width = duration > 0 ? Math.max(0.3, ((seg.end - seg.start) / duration) * 100) : 0;
          return (
            <div
              key={i}
              className="timelineTick"
              style={{ left: `${left}%`, width: `${width}%` }}
            />
          );
        })}

        <div
          className="timelineRange"
          style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
        />

        <div
          className="timelineHandle"
          style={{ left: `${startPct}%` }}
          onPointerDown={handlePointerDown("start")}
        >
          <div className="timelineHandleLine" />
          <div className="timelineHandleKnob">▶</div>
        </div>

        <div
          className="timelineHandle timelineHandleEnd"
          style={{ left: `${endPct}%` }}
          onPointerDown={handlePointerDown("end")}
        >
          <div className="timelineHandleLine" />
          <div className="timelineHandleKnob">◀</div>
        </div>
      </div>

      {/* ── Transcript rows ── */}
      {timeline.segments.length > 0 && (
        <div className="transcriptRows">
          {timeline.segments.map((seg, i) => (
            <button
              key={i}
              type="button"
              className="transcriptRow"
              onClick={() => {
                if (videoRef.current) videoRef.current.currentTime = seg.start;
              }}
            >
              <span className="timecode">{formatTime(seg.start)}</span>
              <span>{seg.text}</span>
            </button>
          ))}
        </div>
      )}

      {/* ── Transcript correction ── */}
      {timeline.segments.length > 0 && (
        <div className="transcriptSection">
          <div className="transcriptSectionHeader">Koreksi Transkrip</div>
          <div className="transcriptEditList">
            {timeline.segments.map((seg, i) => {
              const isDirty = i in editedSegments;
              const currentText = editedSegments[i] ?? seg.text;
              const isEditing = editingIndex === i;
              return (
                <div key={i} className={`transcriptEditRow${isDirty ? " transcriptEditDirty" : ""}`}>
                  <span className="transcriptEditTime">{formatTime(seg.start)}</span>
                  {isEditing ? (
                    <input
                      autoFocus
                      className="transcriptEditInput"
                      value={currentText}
                      onChange={e => handleSegmentChange(i, e.target.value)}
                      onBlur={e => handleSegmentBlur(i, e.target.value)}
                      onKeyDown={e => handleSegmentKeyDown(e, i, currentText)}
                    />
                  ) : (
                    <span
                      className="transcriptEditText"
                      onClick={() => setEditingIndex(i)}
                      title="Klik untuk mengedit"
                    >
                      {currentText}
                    </span>
                  )}
                  {segmentErrors[i] && <span className="transcriptEditError">{segmentErrors[i]}</span>}
                </div>
              );
            })}
          </div>
          <div className="timelineActions" style={{ marginTop: 10 }}>
            <button
              type="button"
              onClick={handleSaveTranscript}
              disabled={savingTranscript || !hasTranscriptEdits}
              className="timelineBtn timelineBtnPrimary"
            >
              {savingTranscript ? "Menyimpan..." : "Simpan Koreksi"}
            </button>
          </div>
        </div>
      )}

      <div className="timelineActions">
        <button type="button" onClick={handlePreview} disabled={previewing} className="timelineBtn">
          {previewing ? "▶ Playing..." : "▸ Preview"}
        </button>
        <button
          type="button"
          onClick={handleRecut}
          disabled={busy || !isChanged}
          className="timelineBtn timelineBtnPrimary"
        >
          {busy ? "Re-cutting..." : "✂ Re-cut"}
        </button>
        <button type="button" onClick={onClose} className="timelineBtn">
          ✕ Close
        </button>
      </div>
        </div>
      </div>
    </div>
  );
}
