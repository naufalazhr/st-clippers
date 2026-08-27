import { Clipboard, Download, Edit3, ExternalLink, Scissors, Video } from "lucide-react";
import { useState, useCallback } from "react";
import { getOutputUrl, recutClip } from "../../lib/apiClient";
import { clipTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile, ClipJob, ClipCandidate } from "../../types/clip.type";
import { EditCaptionDialog } from "./EditCaptionDialog";
import { EditTrimDialog } from "./EditTrimDialog";
import { ThumbnailPrompt } from "./ThumbnailPrompt";

type ResultsSectionProps = {
  job: ClipJob | null;
  onJobRefresh: () => void;
};

export function ResultsSection({ job, onJobRefresh }: ResultsSectionProps) {
  const clips = job?.clips ?? [];
  const [editCaptionClip, setEditCaptionClip] = useState<string | null>(null);
  const [editTrimClip, setEditTrimClip] = useState<string | null>(null);
  const [previewClipName, setPreviewClipName] = useState<string | null>(null);

  const handleRecut = useCallback(
    async (index: number, start: number, end: number) => {
      if (!job) return;
      await recutClip(job.id, { index, start, end });
      onJobRefresh();
    },
    [job, onJobRefresh]
  );

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

  const handleEditTrim = useCallback((clipName: string) => {
    setEditTrimClip(clipName);
  }, []);

  const handleEditCaptionSuccess = useCallback(() => {
    onJobRefresh();
  }, [onJobRefresh]);

  const handleEditTrimSuccess = useCallback(() => {
    onJobRefresh();
  }, [onJobRefresh]);

  const previewClip = previewClipName
    ? clips.find((c) => c.name === previewClipName) ?? null
    : null;

  return (
    <section className="results">
      <div className="sectionHeader">
        <h2>Klip Siap Digunakan</h2>
        <span className="sectionBadge">{clips.length} klip siap</span>
      </div>

      {clips.length ? (
        <div className="resultsLayout">
          <div className="clipGrid">
            {clips.map((clip) => {
              const title = clipTitle(clip.name);
              const url = getOutputUrl(clip.url);
              const hasEditBtn = canEdit(clip.name);
              const isPreviewing = clip.name === previewClipName;

              return (
                <article
                  className={`clipCard${isPreviewing ? " clipCard--active" : ""}`}
                  key={clip.url}
                  onMouseEnter={() => setPreviewClipName(clip.name)}
                  onFocus={() => setPreviewClipName(clip.name)}
                >
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
                      <>
                        <button type="button" onClick={() => handleEditTrim(clip.name)}>
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
                </article>
              );
            })}
          </div>

          <aside className="resultsPreview">
            {previewClip ? (
              <>
                <div className="resultsPreview-frame">
                  <video
                    key={previewClip.url}
                    controls
                    autoPlay
                    muted
                    playsInline
                    src={getOutputUrl(previewClip.url)}
                    poster={previewClip.thumbnail_url ? getOutputUrl(previewClip.thumbnail_url) : undefined}
                  />
                </div>
                <div className="resultsPreview-meta">
                  <h4>{clipTitle(previewClip.name)}</h4>
                  <p className="resultsPreview-fileName">{previewClip.name}</p>
                </div>
              </>
            ) : (
              <div className="resultsPreview-empty">
                <Video size={28} />
                <p>Hover sebuah klip untuk preview di sini</p>
              </div>
            )}
          </aside>
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
          onClose={() => setEditCaptionClip(null)}
          onSuccess={handleEditCaptionSuccess}
        />
      )}

      {job && editTrimClip && (
        <EditTrimDialog
          open={true}
          clipName={editTrimClip}
          job={job}
          onClose={() => setEditTrimClip(null)}
          onSuccess={handleEditTrimSuccess}
        />
      )}
    </section>
  );
}
