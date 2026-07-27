"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getOutputUrl } from "../../lib/apiClient";
import type { ClipCandidate, TimelineData, TranscriptSegment } from "../../types/clip.type";

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
  const videoRef = useRef<HTMLVideoElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<"start" | "end" | null>(null);
  const duration = timeline.duration || candidate.duration;

  const clampedStart = Math.max(0, Math.min(start, duration - 1));
  const clampedEnd = Math.max(clampedStart + 1, Math.min(end, duration));
  const isChanged = clampedStart !== candidate.start || clampedEnd !== candidate.end;

  const snapBoundary = useCallback((time: number, segments: TranscriptSegment[]): number => {
    let best = time;
    let bestDist = 0.4;
    for (const s of segments) {
      for (const t of [s.start, s.end]) {
        const dist = Math.abs(time - t);
        if (dist < bestDist) {
          bestDist = dist;
          best = t;
        }
      }
    }
    return Math.max(0, Math.min(best, duration));
  }, [duration]);

  const handlePointerDown = useCallback((handle: "start" | "end") => (e: React.PointerEvent) => {
    dragging.current = handle;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
  }, []);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    let time = ((e.clientX - rect.left) / rect.width) * duration;
    time = Math.max(0, Math.min(time, duration));
    if (dragging.current === "start") {
      setStart(Math.min(time, end - 1));
    } else {
      setEnd(Math.max(time, start + 1));
    }
  }, [duration, start, end]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    const rect = trackRef.current?.getBoundingClientRect();
    if (rect) {
      let time = ((e.clientX - rect.left) / rect.width) * duration;
      time = Math.max(0, Math.min(time, duration));
      const snapped = snapBoundary(time, timeline.segments);
      if (dragging.current === "start") {
        setStart(Math.min(snapped, end - 1));
      } else {
        setEnd(Math.max(snapped, start + 1));
      }
    }
    dragging.current = null;
  }, [duration, snapBoundary, timeline.segments, start, end]);

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

  return (
    <div className="timelineEditor">
      <div className="timelineHeader">
        <h4>✂️ Trim clip: {candidate.title}</h4>
        <time className="timelineCodes">{formatTime(clampedStart)} — {formatTime(clampedEnd)} ({formatTime(clampedEnd - clampedStart)})</time>
      </div>

      <video
        ref={videoRef}
        src={getOutputUrl(timeline.source_url)}
        preload="metadata"
        muted
        className="timelineVideo"
      />

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

      <div className="timelineActions">
        <button type="button" onClick={handlePreview} disabled={previewing} className="timelineBtn">
          {previewing ? "▶ Playing..." : "▸ Preview"}
        </button>
        <button type="button" onClick={handleRecut} disabled={busy || !isChanged} className="timelineBtn timelineBtnPrimary">
          {busy ? "Re-cutting..." : "✂ Re-cut"}
        </button>
        <button type="button" onClick={onClose} className="timelineBtn">
          ✕ Close
        </button>
      </div>
    </div>
  );
}