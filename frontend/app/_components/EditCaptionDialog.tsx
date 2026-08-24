"use client";

import { Edit3 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { getTimeline, recutClip } from "../../lib/apiClient";
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
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editedSegments, setEditedSegments] = useState<Record<number, string>>({});
  const [captionStyle, setCaptionStyle] = useState<CaptionStyle>("classic");
  const [transition, setTransition] = useState<Transition>("none");

  const match = clipName.match(/^clip_(\d+)_/);
  const clipIndex = match ? parseInt(match[1], 10) : -1;

  useEffect(() => {
    if (!open || clipIndex === -1) return;

    setLoading(true);
    getTimeline(job.id)
      .then((data) => {
        setTimeline(data);
        // Pre-fill segments from timeline
        const candidate = job.candidates.find((c) => c.index === clipIndex);
        if (candidate) {
          const clipSegments = data.segments.filter(
            (seg) => seg.start >= candidate.start && seg.end <= candidate.end
          );
          const init: Record<number, string> = {};
          clipSegments.forEach((seg, i) => {
            init[i] = seg.text;
          });
          setEditedSegments(init);
        }
      })
      .catch(() => {
        toast.error("Gagal memuat data timeline");
        onClose();
      })
      .finally(() => setLoading(false));
  }, [open, clipIndex, job.id, job.candidates, onClose]);

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
        transition,
      });
      toast.success("Caption berhasil diperbarui");
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan perubahan");
    } finally {
      setSaving(false);
    }
  }, [timeline, clipIndex, job, editedSegments, captionStyle, transition, onSuccess, onClose]);

  if (!open) return null;

  const candidate = job.candidates.find((c) => c.index === clipIndex);
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
