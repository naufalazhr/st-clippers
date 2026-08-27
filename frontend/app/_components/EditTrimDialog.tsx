"use client";

import { Scissors, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { getTimeline, recutClip } from "../../lib/apiClient";
import type { ClipJob, TimelineData } from "../../types/clip.type";
import { TimelineEditor } from "./TimelineEditor";

type EditTrimDialogProps = {
  open: boolean;
  clipName: string;
  job: ClipJob;
  onClose: () => void;
  onSuccess: () => void;
};

export function EditTrimDialog({ open, clipName, job, onClose, onSuccess }: EditTrimDialogProps) {
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const match = clipName.match(/^clip_(\d+)_/);
  const clipIndex = match ? parseInt(match[1], 10) : -1;
  const candidate = job.candidates.find((c) => c.index === clipIndex);

  useEffect(() => {
    if (!open || clipIndex === -1 || !candidate) return;

    setLoading(true);
    setTimeline(null);
    getTimeline(job.id)
      .then((data) => setTimeline(data))
      .catch(() => {
        toast.error("Gagal memuat data timeline");
        onClose();
      })
      .finally(() => setLoading(false));
    // job.id and candidate are stable refs; only re-fetch when clip changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, clipIndex]);

  const handleRecut = useCallback(
    async (index: number, start: number, end: number) => {
      if (!job) return;
      setBusy(true);
      try {
        await recutClip(job.id, { index, start, end });
        toast.success("Trim berhasil diperbarui");
        onSuccess();
        onClose();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Gagal memotong ulang");
      } finally {
        setBusy(false);
      }
    },
    [job, onSuccess, onClose]
  );

  const handleOverlay = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget && !busy) onClose();
    },
    [onClose, busy]
  );

  if (!open) return null;

  return (
    <div className="editTrimDialog-overlay" onClick={handleOverlay}>
      <div className="editTrimDialog">
        <div className="editTrimDialog-header">
          <h3>
            <Scissors size={18} style={{ display: "inline", marginRight: 8, verticalAlign: "middle" }} />
            Edit Trim — {candidate?.title || clipName}
          </h3>
          <button
            type="button"
            className="editTrimDialog-close"
            onClick={onClose}
            disabled={busy}
            aria-label="Tutup"
          >
            <X size={18} />
          </button>
        </div>

        <div className="editTrimDialog-body">
          {loading || !timeline || !candidate ? (
            <p style={{ color: "var(--text-secondary)", padding: "32px", textAlign: "center" }}>
              Memuat data timeline...
            </p>
          ) : (
            <TimelineEditor
              jobId={job.id}
              candidate={candidate}
              timeline={timeline}
              onRecut={handleRecut}
              onClose={onClose}
            />
          )}
        </div>
      </div>
    </div>
  );
}
