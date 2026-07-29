"use client";

import { useCallback } from "react";
import type { ClipJob } from "../../../types/clip.type";

interface AboutDialogProps {
  open: boolean;
  onClose: () => void;
}

export function AboutDialog({ open, onClose }: AboutDialogProps) {
  const handleOverlay = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  if (!open) return null;

  return (
    <div className="aboutDialog-overlay" onClick={handleOverlay}>
      <div className="aboutDialog">
        <h2>About Sultan Clip</h2>
         <p>Sultan Clip v0.1.0</p>
        <p>Turn long videos into vertical clips, locally.</p>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
