"use client";

import { Link2, Upload } from "lucide-react";
import type { SourceMode } from "../../../types/clip.type";

type SourceSectionProps = {
  sourceMode: SourceMode;
  uploadFileName: string;
  uploadPreviewUrl: string;
  isUploading: boolean;
  url: string;
  name: string;
  onNameChange: (value: string) => void;
  onSourceModeChange: (mode: SourceMode) => void;
  onUploadFileChange: (file: File | null) => void;
  onUrlChange: (value: string) => void;
};

export function SourceSection({
  sourceMode,
  uploadFileName,
  uploadPreviewUrl,
  isUploading,
  url,
  name,
  onNameChange,
  onSourceModeChange,
  onUploadFileChange,
  onUrlChange,
}: SourceSectionProps) {
  return (
    <div className="sectionBody">
      <label className="field wide">
        <span>Nama Project</span>
        <input
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="Nama project (opsional)"
        />
      </label>

      <div className="segmentedField">
        <span>Sumber Video</span>
        <div className="segmentedControl" role="group" aria-label="Sumber video">
          <button
            className={sourceMode === "url" ? "active" : ""}
            type="button"
            onClick={() => onSourceModeChange("url")}
          >
            <Link2 size={15} /> Link YouTube
          </button>
          <button
            className={sourceMode === "upload" ? "active" : ""}
            type="button"
            onClick={() => onSourceModeChange("upload")}
          >
            <Upload size={15} /> Upload Video
          </button>
        </div>
      </div>

      {sourceMode === "url" ? (
        <label className="field wide">
          <span>Link Video YouTube</span>
          <input
            id="url-input"
            value={url}
            onChange={(event) => onUrlChange(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
          />
          <p className="field-help">Pastikan video memiliki percakapan yang jelas untuk hasil transkripsi terbaik.</p>
        </label>
      ) : (
        <label className="field wide">
          <span>Upload File Video</span>
          <input
            id="video-file-input"
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska,video/webm,.mp4,.mov,.mkv,.webm,.m4v,.avi"
            onChange={(event) => onUploadFileChange(event.target.files?.[0] ?? null)}
          />
          <p className="field-help">
            {isUploading
              ? "Mengunggah video..."
              : uploadFileName
                ? `Siap: ${uploadFileName}`
                : "Format didukung: MP4, MOV, MKV, WEBM, M4V, AVI."}
          </p>
          {uploadPreviewUrl ? (
            <video className="uploadPreview" src={uploadPreviewUrl} controls preload="metadata" />
          ) : null}
        </label>
      )}
    </div>
  );
}
