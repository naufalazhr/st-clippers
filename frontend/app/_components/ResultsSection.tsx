import toast from "react-hot-toast";
import { Clipboard, Download, Edit3, ExternalLink, Loader2, Scissors, Video } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { getOutputUrl, getTimeline, recutClip } from "../../lib/apiClient";
import {
  VIRALITY_SEGMENTS,
  clipTitle,
  handleCopyTitle,
  handleDownload,
  pendingClipCount,
  viralityTier,
} from "../../lib/utils";
import type { ClipFile, ClipJob, ClipCandidate, TimelineData } from "../../types/clip.type";
import { EditCaptionDialog } from "./EditCaptionDialog";
import { ThumbnailPrompt } from "./ThumbnailPrompt";
import { TimelineEditor } from "./TimelineEditor";

type ResultsSectionProps = {
  job: ClipJob | null;
  onJobRefresh: () => void;
};

export function ResultsSection({ job, onJobRefresh }: ResultsSectionProps) {
  const clips = job?.clips ?? [];
  // Clips are published as each one finishes, so the rest are still rendering.
  const pendingCount = pendingClipCount(job?.status, job?.clips_expected, clips.length);
  // A recut re-renders one existing clip in place; mark just that card busy.
  const recutIndex = job?.status === "running" ? job?.recut_index ?? -1 : -1;

  // Surface a failed background recut once, since the request itself succeeded.
  const reportedRecutError = useRef<string | null>(null);
  useEffect(() => {
    const message = job?.recut_error ?? null;
    if (message && reportedRecutError.current !== message) {
      reportedRecutError.current = message;
      toast.error(`Gagal render ulang klip: ${message}`);
    }
    if (!message) reportedRecutError.current = null;
  }, [job?.recut_error]);
  const [expandedIndex, setExpandedIndex] = useState(-1);
  const [timelineCache, setTimelineCache] = useState<Record<string, TimelineData>>({});
  const [editCaptionClip, setEditCaptionClip] = useState<string | null>(null);

  const handleEditClip = useCallback(async (clipName: string, jobId: string) => {
    const match = clipName.match(/^clip_(\d+)_/);
    if (!match) return;
    const idx = parseInt(match[1], 10);

    // Load timeline data if not cached
    if (!timelineCache[jobId]) {
      try {
        const data = await getTimeline(jobId);
        setTimelineCache((prev) => ({ ...prev, [jobId]: data }));
      } catch {
        return; // source not available, button already hidden
      }
    }
    setExpandedIndex(idx);
  }, [timelineCache]);

  const handleRecut = useCallback(async (index: number, start: number, end: number) => {
    if (!job) return;
    await recutClip(job.id, { index, start, end });
    setExpandedIndex(-1);
    onJobRefresh();
  }, [job, onJobRefresh]);

  const canEdit = (clipName: string) => {
    if (!job?.work_dir) return false;
    if ((job.request as Record<string, unknown>).source_file) return false;
    const match = clipName.match(/^clip_(\d+)_/);
    if (!match) return false;
    const idx = parseInt(match[1], 10);
    return job.candidates?.some((c) => c.index === idx) ?? false;
  };

  const handleEditCaption = useCallback((clipName: string) => {
    setEditCaptionClip(clipName);
  }, []);

  const handleEditCaptionSuccess = useCallback(() => {
    onJobRefresh();
  }, [onJobRefresh]);

  const handleCloseCaptionDialog = useCallback(() => setEditCaptionClip(null), []);

  // Rank comes from position in the list, which the backend already sorted by
  // score. Only rank when the scores are real, so an older job without them
  // does not get a meaningless leaderboard.
  const ranked = clips.some((clip) => (clip.virality_score ?? 0) > 0);
  const rankOf = (clip: ClipFile) => (ranked ? clips.indexOf(clip) + 1 : 0);

  return (
    <section className="results">
      <div className="resultsHeader">
        <div>
          <h2>Klip Siap Digunakan</h2>
          {clips.length > 1 && (
            <p className="resultsHeader-note">
              Diurutkan dari skor viral tertinggi. Mulai dari yang teratas.
            </p>
          )}
        </div>
        <span className="sectionBadge">
          {pendingCount
            ? `${clips.length} siap · ${pendingCount} diproses`
            : `${clips.length} klip siap`}
        </span>
      </div>

      {clips.length || pendingCount ? (
        <div className="clipGrid">
          {clips.map((clip) => {
            const title = clipTitle(clip.name);
            const url = getOutputUrl(clip.url);
            const match = clip.name.match(/^clip_(\d+)_/);
            const idx = match ? parseInt(match[1], 10) : -1;
            const isEditing = idx === expandedIndex;
            const hasEditBtn = canEdit(clip.name);

            const isRerendering = idx === recutIndex;
            const score = clip.virality_score ?? 0;
            const tier = viralityTier(score);
            const rank = rankOf(clip);

            return (
              <article
                className={`clipCard${isRerendering ? " clipCard--rerendering" : ""}`}
                key={clip.url}
                data-tier={tier.key}
              >
                {isRerendering && (
                  <div className="clipCard-rerenderOverlay">
                    <Loader2 className="clipCard-pendingSpinner" size={26} />
                    <span>Merender ulang...</span>
                  </div>
                )}
                <div className="clipCard-media">
                  <video
                    controls
                    preload="metadata"
                    src={url}
                    poster={clip.thumbnail_url ? getOutputUrl(clip.thumbnail_url) : undefined}
                  />
                  {rank > 0 && (
                    <span className="clipRank" aria-label={`Peringkat ${rank}`}>
                      {rank}
                    </span>
                  )}
                </div>

                {score > 0 && (
                  <div className="viralityMeter">
                    <div
                      className="viralityMeter-track"
                      role="img"
                      aria-label={`Skor viral ${score} dari 100, ${tier.label}`}
                    >
                      {Array.from({ length: VIRALITY_SEGMENTS }, (_, i) => (
                        <span
                          key={i}
                          className={`viralityMeter-tick${i < tier.segments ? " is-lit" : ""}`}
                        />
                      ))}
                    </div>
                    <span className="viralityMeter-score">{score}</span>
                    <span className="viralityMeter-verdict">{tier.label}</span>
                  </div>
                )}

                <div className="clipInfo">
                  <h3>{title}</h3>
                  <button
                    className="copyTitleButton"
                    type="button"
                    onClick={() => handleCopyTitle(title)}
                    title="Salin judul klip"
                  >
                    <Clipboard size={14} />
                    Copy
                  </button>
                </div>

                {clip.virality_reason && (
                  <div className="viralityReason">
                    <span className="viralityReason-label">Kenapa bisa viral</span>
                    <p>{clip.virality_reason}</p>
                  </div>
                )}

                <div className="clipActions">
                  <a href={url} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} />
                    Buka
                  </a>
                  <button type="button" onClick={() => handleDownload(url, clip.name)}>
                    <Download size={16} />
                    Unduh
                  </button>
                  {hasEditBtn && (
                    <>
                      <button type="button" onClick={() => handleEditClip(clip.name, job!.id)}>
                        <Scissors size={16} />
                        Edit Trim
                      </button>
                      <button type="button" onClick={() => handleEditCaption(clip.name)}>
                        <Edit3 size={16} />
                        Edit Caption
                      </button>
                    </>
                  )}
                </div>
                <ThumbnailPrompt clip={clip} />
                {isEditing && job && timelineCache[job.id] && (
                  <TimelineEditor
                    jobId={job.id}
                    candidate={job.candidates.find((c) => c.index === idx)!}
                    timeline={timelineCache[job.id]}
                    onRecut={handleRecut}
                    onClose={() => setExpandedIndex(-1)}
                  />
                )}
              </article>
            );
          })}
          {Array.from({ length: pendingCount }, (_, i) => (
            <article className="clipCard clipCard--pending" key={`pending-${i}`}>
              <div className="clipCard-pendingMedia" aria-hidden="true">
                <Loader2 className="clipCard-pendingSpinner" size={28} />
              </div>
              <div className="clipInfo">
                <h3>Klip {clips.length + i + 1} sedang dirender...</h3>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="emptyState">
          <Video className="emptyStateIcon" size={32} />
          <p>Klip vertikal 9:16 yang selesai diproses akan muncul di sini.</p>
        </div>
      )}

      {job && editCaptionClip && (
        <EditCaptionDialog
          open={true}
          clipName={editCaptionClip}
          job={job}
          onClose={handleCloseCaptionDialog}
          onSuccess={handleEditCaptionSuccess}
        />
      )}
    </section>
  );
}
