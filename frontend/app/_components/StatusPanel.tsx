import { Activity } from "lucide-react";
import { statusIcon } from "../../lib/constants";
import type { ClipJob, CropMode } from "../../types/clip.type";

const CROP_MODE_LABELS: Record<CropMode, string> = {
  center: "Center crop",
  person: "Follow person",
  streamer: "Streamer",
  pillarbox: "Pillarbox",
};

type StatusPanelProps = {
  job: ClipJob | null;
  latestLogs: string[];
};

export function StatusPanel({ job, latestLogs }: StatusPanelProps) {
  const StatusIcon = job ? statusIcon[job.status] : Activity;

  return (
    <section className="panel statusPanel">
      <div className="panelHeader">
        <StatusIcon className={job?.status === "running" ? "spin" : ""} size={20} />
        <h2>Aktivitas</h2>
      </div>

      {job ? (
        <div className="activityContent">
          <div className="jobMeta">
            <span>{job.request.top ?? "Auto"} klip target</span>
            <span>
              {job.request.min_duration}s - {job.request.max_duration}s
            </span>
            <span>{job.request.analyze_seconds ? `Test: ${job.request.analyze_seconds}s` : "Full video"}</span>
            <span>{CROP_MODE_LABELS[job.request.crop_mode] ?? "Center crop"}</span>
          </div>

          <div className="logBox">
            {latestLogs.length ? (
              latestLogs.map((line, index) => <p key={`${line}-${index}`}>{line}</p>)
            ) : (
              <p>Memulai proses pipeline...</p>
            )}
          </div>

          {job.error ? <p className="error errorWithSpacing">{job.error}</p> : null}
        </div>
      ) : (
        <div className="emptyState activityEmptyState">
          <Activity className="emptyStateIcon" size={32} />
          <p>Belum ada proses berjalan.</p>
          <p className="emptyStateHint">
            Masukkan link YouTube, lalu klik <strong>Mulai Potong Video</strong> untuk memulai.
          </p>
        </div>
      )}
    </section>
  );
}
