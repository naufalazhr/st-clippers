"use client";

import { useEffect, useState } from "react";
import { fetchModelStatus, type ModelStatus } from "../../lib/apiClient";

export function ModelDownloadProgress() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const poll = async () => {
      const s = await fetchModelStatus();
      if (cancelled) return;
      if (!s) { attempts++; if (attempts < 10) setTimeout(poll, 2000); return; }
      setStatus(s);
      if (s.download_progress != null) {
        setVisible(true);
        setTimeout(poll, 2000);
      } else if (s.model_present) {
        setVisible(false);
      } else {
        // model not present and not in a download — wait for trigger
        setTimeout(poll, 4000);
      }
    };

    poll();
    return () => { cancelled = true; };
  }, []);

  if (!visible || !status) return null;

  return (
    <div className="modelDownloadBar">
      <div className="modelDownloadBar-text">
        Downloading model: {status.model_name}
      </div>
      <div className="modelDownloadBar-track">
        <div
          className="modelDownloadBar-fill"
          style={{ width: `${status.download_progress ?? 50}%` }}
        />
      </div>
    </div>
  );
}
