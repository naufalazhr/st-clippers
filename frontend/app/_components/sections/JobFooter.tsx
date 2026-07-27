"use client";

import { Loader2, Play } from "lucide-react";

type JobFooterProps = {
  error: string;
  isStartDisabled: boolean;
  isProcessing: boolean;
  onStartJob: () => void;
};

export function JobFooter({ error, isStartDisabled, isProcessing, onStartJob }: JobFooterProps) {
  return (
    <>
      {error ? <p className="error">{error}</p> : null}

      <button className="btnPrimary" type="button" disabled={isStartDisabled} onClick={onStartJob}>
        {isProcessing ? (
          <>
            <Loader2 className="spin" size={18} />
            Sedang Memproses...
          </>
        ) : (
          <>
            Mulai Potong Video
            <span className="btnPrimary-inner-icon">
              <Play size={14} />
            </span>
          </>
        )}
      </button>
    </>
  );
}
