"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import WaveSurfer from "wavesurfer.js";

export type WaveformHandle = {
  setTime: (t: number) => void;
  setMinPxPerSec: (n: number) => void;
};

type WaveformWrapperProps = {
  url: string;
  peaks: number[];
  duration: number;
};

const WaveformWrapper = forwardRef<WaveformHandle, WaveformWrapperProps>(
  function WaveformWrapper({ url, peaks, duration }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WaveSurfer | null>(null);

    useImperativeHandle(ref, () => ({
      setTime(t: number) {
        if (wsRef.current) wsRef.current.seekTo(t / (wsRef.current.getDuration() || 1));
      },
      setMinPxPerSec(n: number) {
        if (wsRef.current) wsRef.current.zoom(n);
      },
    }));

    useEffect(() => {
      if (!containerRef.current || !url) return;

      const ws = WaveSurfer.create({
        container: containerRef.current,
        url,
        peaks: peaks.length > 0 ? [peaks] : undefined,
        duration: duration || undefined,
        normalize: true,
        waveColor: "var(--text-secondary)",
        progressColor: "var(--primary)",
        height: 60,
        interact: false,
        backend: "WebAudio",
      });

      wsRef.current = ws;

      return () => {
        ws.destroy();
        wsRef.current = null;
      };
      // url/peaks/duration are stable per mount — re-mount if they change
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [url]);

    if (!peaks || peaks.length === 0) {
      return <div className="waveformWrapper waveformPlaceholder" />;
    }

    return <div className="waveformWrapper" ref={containerRef} />;
  }
);

export default WaveformWrapper;
