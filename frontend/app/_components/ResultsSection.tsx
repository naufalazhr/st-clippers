import { Clipboard, Download, ExternalLink, Scissors, Video } from "lucide-react";
import { useState, useCallback } from "react";
import { getOutputUrl, getTimeline, recutClip } from "../../lib/apiClient";
import { clipTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile, ClipJob, ClipCandidate, TimelineData } from "../../types/clip.type";
import { ThumbnailPrompt } from "./ThumbnailPrompt";
import { TimelineEditor } from "./TimelineEditor";

type ResultsSectionProps = {
  job: ClipJob | null;
  onJobRefresh: () => void;
};

export function ResultsSection({ job, onJobRefresh }: ResultsSectionProps) {
  const clips = job?.clips ?? [];
  const [expandedIndex, setExpandedIndex] = useState(-1);
  const [timelineCache, setTimelineCache] = useState<Record<string, TimelineData>>({});

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

  return (
    <section className="results">
      <div className="sectionHeader">
        <h2>Klip Siap Digunakan</h2>
        <span className="sectionBadge">{clips.length} klip siap</span>
      </div>

      {clips.length ? (
        <div className="clipGrid">
          {clips.map((clip) => {
            const title = clipTitle(clip.name);
            const url = getOutputUrl(clip.url);
            const match = clip.name.match(/^clip_(\d+)_/);
            const idx = match ? parseInt(match[1], 10) : -1;
            const isEditing = idx === expandedIndex;
            const hasEditBtn = canEdit(clip.name);

            return (
              <article className="clipCard" key={clip.url}>
                <video
                  controls
                  preload="metadata"
                  src={url}
                  poster={clip.thumbnail_url ? getOutputUrl(clip.thumbnail_url) : undefined}
                />
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
                    <button type="button" onClick={() => handleEditClip(clip.name, job!.id)}>
                      <Scissors size={16} />
                      Edit Trim
                    </button>
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
        </div>
      ) : (
        <div className="emptyState">
          <Video className="emptyStateIcon" size={32} />
          <p>Klip vertikal 9:16 yang selesai diproses akan muncul di sini.</p>
        </div>
      )}
    </section>
  );
}
