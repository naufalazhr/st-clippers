"use client";

import { Edit3 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { getTimeline, recutClip } from "../../lib/apiClient";
import { DEFAULT_BOX_OPACITY } from "../../lib/constants";
import type { CaptionStyle, ClipJob, TimelineData, Transition, TranscriptSegment } from "../../types/clip.type";

type EditCaptionDialogProps = {
  open: boolean;
  clipName: string;
  job: ClipJob;
  onClose: () => void;
  onSuccess: () => void;
};

const CAPTION_STYLE_OPTIONS: { value: CaptionStyle; label: string }[] = [
  { value: "classic", label: "Classic" },
  { value: "bold", label: "Bold" },
  { value: "boxed", label: "Boxed" },
  { value: "highlight", label: "Highlight" },
  { value: "shadow", label: "Shadow" },
];

const TRANSITION_OPTIONS: { value: Transition; label: string }[] = [
  { value: "none", label: "Tanpa Efek" },
  { value: "fade", label: "Fade" },
  { value: "fadeblack", label: "Fade Hitam" },
  { value: "fadewhite", label: "Fade Putih" },
];

export function EditCaptionDialog({ open, clipName, job, onClose, onSuccess }: EditCaptionDialogProps) {
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  // The job object is re-fetched every couple of seconds while this dialog is
  // open, so anything read from it inside the loader effect has to go through a
  // ref. Depending on job.candidates (a fresh array each poll) or on an inline
  // onClose made the effect re-run constantly: it flipped back to the loading
  // state and discarded whatever had been typed.
  const jobRef = useRef(job);
  jobRef.current = job;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editedSegments, setEditedSegments] = useState<Record<number, string>>({});
  const [captionStyle, setCaptionStyle] = useState<CaptionStyle>("classic");
  // null = follow the preset default (solid for boxed, translucent for highlight).
  const [boxOpacity, setBoxOpacity] = useState<number | null>(null);
  const [transition, setTransition] = useState<Transition>("none");

  const match = clipName.match(/^clip_(\d+)_/);
  const clipIndex = match ? parseInt(match[1], 10) : -1;
  const jobId = job.id;

  // Stable candidate lookup - avoids re-fetching when job.candidates reference changes
  const candidate = useMemo(
    () => job.candidates.find((c) => c.index === clipIndex),
    [job.candidates, clipIndex]
  );

  useEffect(() => {
    if (!open || clipIndex === -1 || !candidate) return;

    setLoading(true);
    getTimeline(jobId)
      .then((data) => {
        setTimeline(data);
        // Pre-fill segments from timeline, scoped to this clip's window.
        const clipSegments = data.segments.filter(
          (seg) => seg.start >= candidate.start && seg.end <= candidate.end
        );
        const init: Record<number, string> = {};
        clipSegments.forEach((seg, i) => {
          init[i] = seg.text;
        });
        setEditedSegments(init);
      })
      .catch(() => {
        toast.error("Gagal memuat data timeline");
        onCloseRef.current();
      })
      .finally(() => setLoading(false));
    // Reload only when a different clip is opened -- not on every job refresh.
    // `onClose` and `job` are read through refs, so they don't belong in deps.
  }, [open, clipIndex, jobId, candidate]);

  const handleOverlay = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  const handleSegmentChange = (index: number, value: string) => {
    setEditedSegments((prev) => ({ ...prev, [index]: value }));
  };

  const handleSave = useCallback(async () => {
    if (!timeline || clipIndex === -1) return;

    const candidate = job.candidates.find((c) => c.index === clipIndex);
    if (!candidate) return;

    const clipSegments = timeline.segments.filter(
      (seg) => seg.start >= candidate.start && seg.end <= candidate.end
    );

    const updatedSegments: TranscriptSegment[] = clipSegments.map((seg, i) => ({
      start: seg.start,
      end: seg.end,
      text: editedSegments[i] ?? seg.text,
    }));

    setSaving(true);
    try {
      await recutClip(job.id, {
        index: clipIndex,
        start: candidate.start,
        end: candidate.end,
        segments: updatedSegments,
        caption_style: captionStyle,
        caption_box_opacity: boxOpacity,
        transition,
      });
      // The render runs in the background now, so close immediately and let the
      // clip card show its progress instead of freezing this dialog.
      toast.success("Perubahan disimpan, klip sedang dirender ulang...");
      onClose();
      onSuccess();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan perubahan");
    } finally {
      setSaving(false);
    }
  }, [timeline, clipIndex, job, editedSegments, captionStyle, boxOpacity, transition, onSuccess, onClose]);

  if (!open) return null;

  const clipSegments = timeline?.segments.filter(
    (seg) => candidate && seg.start >= candidate.start && seg.end <= candidate.end
  ) ?? [];

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="editCaptionModal-overlay" onClick={handleOverlay}>
      <div className="editCaptionModal">
        <div className="editCaptionModal-header">
          <h3>
            <Edit3 size={18} style={{ display: "inline", marginRight: 8, verticalAlign: "middle" }} />
            Edit Caption — {candidate?.title || clipName}
          </h3>
        </div>

        <div className="editCaptionModal-body">
          {loading ? (
            <p style={{ color: "var(--text-secondary)" }}>Memuat data...</p>
          ) : (
            <>
              <div className="editCaptionModal-section">
                <div className="editCaptionModal-sectionTitle">Segmen Caption</div>
                <div className="editCaptionSegmentList">
                  {clipSegments.map((seg, i) => (
                    <div key={i} className="editCaptionSegment">
                      <span className="editCaptionSegment-time">{formatTime(seg.start)}</span>
                      <textarea
                        value={editedSegments[i] ?? seg.text}
                        onChange={(e) => handleSegmentChange(i, e.target.value)}
                        placeholder="Teks caption..."
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className="editCaptionModal-section">
                <div className="editCaptionModal-sectionTitle">Style Caption</div>
                <div className="captionStylePicker" style={{ marginBottom: 16 }}>
                  {CAPTION_STYLE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`captionStyleChip${captionStyle === opt.value ? " captionStyleChip--active" : ""}`}
                      onClick={() => setCaptionStyle(opt.value)}
                      style={{ minWidth: "60px" }}
                    >
                      <span className={`captionStylePreview captionStylePreview--${opt.value}`}>Aa</span>
                      <span className="captionStyleLabel">{opt.label}</span>
                    </button>
                  ))}
                </div>

                {(captionStyle === "boxed" || captionStyle === "highlight") && (
                  <div className="editCaptionModal-boxOpacity">
                    <label htmlFor="recutBoxOpacity">
                      Opacity Box ({boxOpacity ?? DEFAULT_BOX_OPACITY[captionStyle]}%)
                    </label>
                    <input
                      id="recutBoxOpacity"
                      className="fontSlider"
                      type="range"
                      min={0}
                      max={100}
                      step={5}
                      value={boxOpacity ?? DEFAULT_BOX_OPACITY[captionStyle]}
                      onChange={(event) => setBoxOpacity(Number(event.target.value))}
                    />
                  </div>
                )}
              </div>

              <div className="editCaptionModal-section">
                <div className="editCaptionModal-sectionTitle">Transisi</div>
                <div className="transitionPicker">
                  {TRANSITION_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`transitionChip${transition === opt.value ? " transitionChip--active" : ""}`}
                      onClick={() => setTransition(opt.value)}
                      style={{ minWidth: "80px" }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="editCaptionModal-footer">
          <button type="button" className="editCaptionModal-btnCancel" onClick={onClose} disabled={saving}>
            Batal
          </button>
          <button type="button" className="editCaptionModal-btnSave" onClick={handleSave} disabled={loading || saving}>
            {saving ? "Menyimpan..." : "Simpan"}
          </button>
        </div>
      </div>
    </div>
  );
}
