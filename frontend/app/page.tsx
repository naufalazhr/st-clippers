"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  createJob,
  deleteJob,
  deleteJobs,
  fetchModels,
  getJob,
  getJobs,
  probeUrlDuration,
  uploadVideo,
} from "../lib/apiClient";
import {
  DEFAULT_AI_BASE_URL,
  DEFAULT_AI_MODEL,
  DEFAULT_CAPTION_COLOR,
  DEFAULT_CAPTION_FONT,
  DEFAULT_CAPTION_FONT_SIZE,
  DEFAULT_CAPTION_OUTLINE,
  DEFAULT_CAPTION_OUTLINE_COLOR,
  DEFAULT_CAPTION_POSITION,
  DEFAULT_LANGUAGE,
  DEFAULT_MAX_DURATION,
  DEFAULT_MIN_DURATION,
  DEFAULT_MODEL,
  JOB_POLL_INTERVAL_MS,
  RECENT_LOG_LIMIT,
} from "../lib/constants";
import { isActiveJob } from "../lib/utils";
import type {
  CamCorner,
  CaptionFont,
  CaptionPosition,
  ClipJob,
  CropMode,
  SourceMode,
} from "../types/clip.type";
import { ControlPanel } from "./_components/ControlPanel";
import { DeleteAllToast } from "./_components/DeleteAllToast";
import { HistorySection } from "./_components/HistorySection";
import { ResultsSection } from "./_components/ResultsSection";
import { SiteFooter } from "./_components/SiteFooter";
import { StatusPanel } from "./_components/StatusPanel";
import { Topbar } from "./_components/Topbar";
import { ModelDownloadProgress } from "./_components/ModelDownloadProgress";
import { isInTauri, useMenuActions, openExternal } from "../lib/desktop";
import { toggleTheme } from "../lib/theme";
import { AboutDialog } from "./_components/desktop/AboutDialog";
import { DesktopShell, type DesktopView } from "./_components/desktop/DesktopShell";
import { Sidebar } from "./_components/desktop/Sidebar";
import { StatusBar } from "./_components/desktop/StatusBar";
import { HistoryTable } from "./_components/desktop/HistoryTable";
import { InspectorPanel } from "./_components/desktop/InspectorPanel";
import "./_components/desktop/motion.css";

export default function HomePage() {
   const [url, setUrl] = useState("");
   const [name, setName] = useState("");
   const [sourceMode, setSourceMode] = useState<SourceMode>("url");
  const [uploadToken, setUploadToken] = useState("");
  const [uploadFileName, setUploadFileName] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [minDuration, setMinDuration] = useState(DEFAULT_MIN_DURATION);
  const [maxDuration, setMaxDuration] = useState(DEFAULT_MAX_DURATION);
  const [targetClips, setTargetClips] = useState(0);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState("");
  const [cropMode, setCropMode] = useState<CropMode>("person");
  const [camCorner, setCamCorner] = useState<CamCorner>("auto");
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [captionFontSize, setCaptionFontSize] = useState(DEFAULT_CAPTION_FONT_SIZE);
  const [captionPosition, setCaptionPosition] = useState<CaptionPosition>(DEFAULT_CAPTION_POSITION);
  const [captionColor, setCaptionColor] = useState(DEFAULT_CAPTION_COLOR);
  const [captionFont, setCaptionFont] = useState<CaptionFont>(DEFAULT_CAPTION_FONT);
  const [captionOutline, setCaptionOutline] = useState(DEFAULT_CAPTION_OUTLINE);
  const [captionOutlineColor, setCaptionOutlineColor] = useState(DEFAULT_CAPTION_OUTLINE_COLOR);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiBaseUrl, setAiBaseUrl] = useState(DEFAULT_AI_BASE_URL);
  const [aiModel, setAiModel] = useState(DEFAULT_AI_MODEL);
  const [aiApiKey, setAiApiKey] = useState("");
  const [requiredHashtags, setRequiredHashtags] = useState("");
  const [aiModels, setAiModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [job, setJob] = useState<ClipJob | null>(null);
  const [jobs, setJobs] = useState<ClipJob[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [isDesktop, setIsDesktop] = useState(false);
  useLayoutEffect(() => { setIsDesktop(isInTauri()); }, []);
  const [view, setView] = useState<DesktopView>("editor");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showStatusbar, setShowStatusbar] = useState(true);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(true);

  const activeJobId = job?.id;
  const isBusy = isActiveJob(job);
  const latestLogs = useMemo(() => job?.logs.slice(-RECENT_LOG_LIMIT) ?? [], [job]);

  // min_duration * target_clips must fit within 80% of the video length.
  const maxClips = useMemo(() => {
    if (!videoDuration || minDuration <= 0) return null;
    return Math.max(1, Math.floor((videoDuration * 0.8) / minDuration));
  }, [videoDuration, minDuration]);

  useEffect(() => {
    if (sourceMode !== "url") return;
    const trimmed = url.trim();
    if (!trimmed) {
      setVideoDuration(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const duration = await probeUrlDuration(trimmed).catch(() => null);
      if (!cancelled) setVideoDuration(duration);
    }, 700);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [url, sourceMode]);

  const loadJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      setJobs(await getJobs());
    } finally {
      setJobsLoading(false);
    }
  }, []);

   const resetForm = useCallback(() => {
     setJob(null);
     setUrl("");
     setName("");
     setUploadToken("");
     setUploadFileName("");
     setVideoDuration(null);
     setUploadPreviewUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return ""; });
     setError("");
   }, []);

   useEffect(() => {
     loadJobs().catch(() => undefined);
   }, [loadJobs]);

   // Poll active job for status updates
   useEffect(() => {
     if (!activeJobId) return;

     const interval = window.setInterval(async () => {
       try {
         const nextJob = await getJob(activeJobId);
         setJob(nextJob);

         if (nextJob.status === "completed" || nextJob.status === "failed") {
           loadJobs().catch(() => undefined);
         }
       } catch {
         // Silently skip failed polls — the interval will retry
       }
     }, JOB_POLL_INTERVAL_MS);

     return () => window.clearInterval(interval);
   }, [activeJobId, loadJobs]);

   const handleLoadModels = useCallback(async () => {
    const base = aiBaseUrl.trim();
    if (!base) return;
    setIsLoadingModels(true);
    try {
      const models = await fetchModels(base, aiApiKey.trim());
      setAiModels(models);
      if (models.length) {
        toast.success(`${models.length} model dimuat`);
      } else {
        toast.error("Tidak ada model ditemukan");
      }
    } catch (modelsError) {
      toast.error(modelsError instanceof Error ? modelsError.message : "Gagal memuat model");
    } finally {
      setIsLoadingModels(false);
    }
   }, [aiBaseUrl, aiApiKey]);

  const handleSourceModeChange = useCallback((mode: SourceMode) => {
    setSourceMode(mode);
    setError("");
  }, []);

  const handleMenuAction = useCallback((itemId: string) => {
    switch (itemId) {
      case "view.refresh":
        loadJobs();
        break;
      case "file.new-job":
        setView("editor");
        resetForm();
        requestAnimationFrame(() => {
          document.getElementById("url-input")?.focus();
        });
        break;
      case "file.open-video":
        setView("editor");
        handleSourceModeChange("upload");
        requestAnimationFrame(() => {
          (document.getElementById("video-file-input") as HTMLInputElement | null)?.click();
        });
        break;
      case "view.theme":
        toggleTheme();
        break;
      case "view.sidebar":
        setShowSidebar((v) => !v);
        break;
      case "view.statusbar":
        setShowStatusbar((v) => !v);
        break;
      case "help.docs":
        void openExternal("https://github.com/sultantech/st-clippers");
        break;
      case "help.about":
        setAboutOpen(true);
        break;
    }
  }, [loadJobs, resetForm, handleSourceModeChange]);

  useMenuActions(handleMenuAction);

  useEffect(() => {
    if (!job && jobs.length > 0) {
      const completedJob = jobs.find((j) => j.status === "completed");
      if (completedJob) {
        setJob(completedJob);
      }
    }
  }, [jobs, job]);

  const handleUploadFileChange = useCallback(async (file: File | null) => {
    setError("");
    setUploadPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return file ? URL.createObjectURL(file) : "";
    });
    if (!file) {
      setUploadToken("");
      setUploadFileName("");
      setVideoDuration(null);
      return;
    }

    setIsUploading(true);
    try {
      const result = await toast.promise(uploadVideo(file), {
        loading: "Mengunggah video...",
        success: "Video berhasil diunggah!",
        error: "Gagal mengunggah video",
      });
       setUploadToken(result.source_file);
       setUploadFileName(result.original_name);
       setVideoDuration(result.duration);
       setName((prev) => (prev.trim() ? prev : result.original_name.replace(/\.[^.]+$/, "")));
    } catch (uploadError) {
      setUploadToken("");
      setVideoDuration(null);
      setUploadFileName("");
      setError(uploadError instanceof Error ? uploadError.message : "Gagal mengunggah video.");
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleStartJob = useCallback(async () => {
    const trimmedUrl = url.trim();
    setError("");

    if (sourceMode === "url" && !trimmedUrl) {
      setError("Link YouTube tidak boleh kosong.");
      return;
    }
    if (sourceMode === "upload" && !uploadToken) {
      setError("Unggah file video terlebih dahulu.");
      return;
    }

    setIsSubmitting(true);

    try {
      const nextJob = await toast.promise(
        createJob({
           url: sourceMode === "url" ? trimmedUrl : "",
           source_file: sourceMode === "upload" ? uploadToken : "",
           name: name.trim(),
          top: targetClips > 0 ? targetClips : undefined,
          min_duration: minDuration,
          max_duration: maxDuration,
          model: DEFAULT_MODEL,
          language: DEFAULT_LANGUAGE,
          burn_subtitles: burnSubtitles,
          crop_mode: cropMode,
          cam_corner: camCorner,
          caption_font_size: captionFontSize,
          caption_position: captionPosition,
          caption_color: captionColor,
          caption_font: captionFont,
          caption_outline: captionOutline,
          caption_outline_color: captionOutlineColor,
          required_hashtags: requiredHashtags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
          ai_enabled: aiEnabled,
          ai_base_url: aiBaseUrl.trim(),
          ai_model: aiModel.trim(),
          ai_api_key: aiApiKey.trim(),
        }),
        {
          loading: "Mempersiapkan proses pemotongan...",
          success: "Proses pemotongan berhasil dimulai!",
          error: "Gagal memulai proses pemotongan",
        },
      );

      setJob(nextJob);
      setView("clip");
      await loadJobs();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Gagal memulai proses.");
    } finally {
      setIsSubmitting(false);
    }
  }, [
     aiApiKey,
     aiBaseUrl,
     aiEnabled,
     aiModel,
     burnSubtitles,
     camCorner,
     captionColor,
     captionFont,
     captionFontSize,
     captionOutline,
     captionOutlineColor,
     captionPosition,
     cropMode,
     loadJobs,
     maxDuration,
     minDuration,
     name,
     requiredHashtags,
     sourceMode,
     targetClips,
     uploadToken,
     url,
   ]);

  const handleDeleteAllConfirmed = useCallback(async () => {
    await toast.promise(deleteJobs(), {
      loading: "Menghapus riwayat...",
      success: "Seluruh riwayat berhasil dihapus!",
      error: "Gagal menghapus riwayat",
    });

    setJob(null);
    await loadJobs();
  }, [loadJobs]);

  const handleDeleteAll = useCallback(() => {
    toast((item) => <DeleteAllToast toastId={item.id} onConfirm={handleDeleteAllConfirmed} />, {
      duration: Infinity,
    });
  }, [handleDeleteAllConfirmed]);

  const handleDeleteJob = useCallback(async (jobId: string) => {
    try {
      await deleteJob(jobId);
      if (job?.id === jobId) setJob(null);
      await loadJobs();
    } catch {
      toast.error("Gagal menghapus project");
    }
  }, [job?.id, loadJobs]);

  if (isDesktop) {
    return (
      <DesktopShell
        view={view}
        onViewChange={setView}
        showSidebar={showSidebar}
        showStatusbar={showStatusbar}
        onToggleSidebar={() => setShowSidebar((v) => !v)}
        onToggleStatusbar={() => setShowStatusbar((v) => !v)}
        sidebar={
          <Sidebar
            view={view}
            onViewChange={setView}
            collapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
          />
        }
        canvas={
          view === "editor" ? (
            <InspectorPanel
               cropMode={cropMode}
               error={error}
               isBusy={isBusy}
               isSubmitting={isSubmitting}
               sourceMode={sourceMode}
               uploadFileName={uploadFileName}
               uploadPreviewUrl={uploadPreviewUrl}
               isUploading={isUploading}
               camCorner={camCorner}
               onCamCornerChange={setCamCorner}
               onSourceModeChange={handleSourceModeChange}
               onUploadFileChange={handleUploadFileChange}
               maxDuration={maxDuration}
               minDuration={minDuration}
               targetClips={targetClips}
               maxClips={maxClips}
               videoDuration={videoDuration}
               onTargetClipsChange={setTargetClips}
               burnSubtitles={burnSubtitles}
               captionFontSize={captionFontSize}
               captionPosition={captionPosition}
               captionColor={captionColor}
               captionFont={captionFont}
               captionOutline={captionOutline}
               captionOutlineColor={captionOutlineColor}
               onCaptionFontChange={setCaptionFont}
               onCaptionOutlineChange={setCaptionOutline}
               onCaptionOutlineColorChange={setCaptionOutlineColor}
               aiEnabled={aiEnabled}
               aiBaseUrl={aiBaseUrl}
               aiModel={aiModel}
               aiApiKey={aiApiKey}
               aiModels={aiModels}
               isLoadingModels={isLoadingModels}
               onLoadModels={handleLoadModels}
               requiredHashtags={requiredHashtags}
               onRequiredHashtagsChange={setRequiredHashtags}
               onCropModeChange={setCropMode}
               onMaxDurationChange={setMaxDuration}
               onMinDurationChange={setMinDuration}
               onBurnSubtitlesChange={setBurnSubtitles}
               onCaptionFontSizeChange={setCaptionFontSize}
               onCaptionPositionChange={setCaptionPosition}
               onCaptionColorChange={setCaptionColor}
               onAiEnabledChange={setAiEnabled}
               onAiBaseUrlChange={setAiBaseUrl}
               onAiModelChange={setAiModel}
               onAiApiKeyChange={setAiApiKey}
               onStartJob={handleStartJob}
               onUrlChange={setUrl}
               url={url}
               name={name}
               onNameChange={setName}
             />
          ) : view === "clip" ? (
            jobsLoading && !job ? (
              <div className="skeleton-cards">
                <div className="skeleton skeleton-card" />
                <div className="skeleton skeleton-card" />
                <div className="skeleton skeleton-card" />
              </div>
            ) : (
              <>
                <ModelDownloadProgress />
                <ResultsSection job={job} onJobRefresh={() => activeJobId && getJob(activeJobId).then(setJob)} />
              </>
            )
          ) : (
            <HistoryTable jobs={jobs} loading={jobsLoading} onSelectJob={setJob} onDeleteAll={handleDeleteAll} onDeleteJob={handleDeleteJob} onViewChange={setView} />
          )
        }
        statusbar={
          <StatusBar
            job={job}
            logs={latestLogs}
            showSidebar={showSidebar}
            onToggleSidebar={() => setShowSidebar((v) => !v)}
          />
        }
      />
    );
  }

  return (
    <>
      <main className="shell py-28">
        <Topbar onRefresh={loadJobs} />
        <ModelDownloadProgress />

        <section className="workspace">
          <div className="doppelrand workspace-main">
            <div className="doppelrand-inner">
               <ControlPanel
                 cropMode={cropMode}
                 error={error}
                 isBusy={isBusy}
                 isSubmitting={isSubmitting}
                 sourceMode={sourceMode}
                 uploadFileName={uploadFileName}
                 uploadPreviewUrl={uploadPreviewUrl}
                 isUploading={isUploading}
                 camCorner={camCorner}
                 onCamCornerChange={setCamCorner}
                 onSourceModeChange={handleSourceModeChange}
                 onUploadFileChange={handleUploadFileChange}
                 maxDuration={maxDuration}
                 minDuration={minDuration}
                 targetClips={targetClips}
                 maxClips={maxClips}
                 videoDuration={videoDuration}
                 onTargetClipsChange={setTargetClips}
                 burnSubtitles={burnSubtitles}
                 captionFontSize={captionFontSize}
                 captionPosition={captionPosition}
                 captionColor={captionColor}
                 captionFont={captionFont}
                 captionOutline={captionOutline}
                 captionOutlineColor={captionOutlineColor}
                 onCaptionFontChange={setCaptionFont}
                 onCaptionOutlineChange={setCaptionOutline}
                 onCaptionOutlineColorChange={setCaptionOutlineColor}
                 aiEnabled={aiEnabled}
                 aiBaseUrl={aiBaseUrl}
                 aiModel={aiModel}
                 aiApiKey={aiApiKey}
                 aiModels={aiModels}
                 isLoadingModels={isLoadingModels}
                 onLoadModels={handleLoadModels}
                 requiredHashtags={requiredHashtags}
                 onRequiredHashtagsChange={setRequiredHashtags}
                 onCropModeChange={setCropMode}
                 onMaxDurationChange={setMaxDuration}
                 onMinDurationChange={setMinDuration}
                 onBurnSubtitlesChange={setBurnSubtitles}
                 onCaptionFontSizeChange={setCaptionFontSize}
                 onCaptionPositionChange={setCaptionPosition}
                 onCaptionColorChange={setCaptionColor}
                 onAiEnabledChange={setAiEnabled}
                 onAiBaseUrlChange={setAiBaseUrl}
                 onAiModelChange={setAiModel}
                 onAiApiKeyChange={setAiApiKey}
                 onStartJob={handleStartJob}
                 onUrlChange={setUrl}
                 url={url}
                 name={name}
                 onNameChange={setName}
               />
            </div>
          </div>
          <div className="doppelrand workspace-side">
            <div className="doppelrand-inner">
              <StatusPanel job={job} latestLogs={latestLogs} />
            </div>
          </div>
        </section>

        <div className="doppelrand results">
          <div className="doppelrand-inner">
            <ResultsSection job={job} onJobRefresh={() => activeJobId && getJob(activeJobId).then(setJob)} />
          </div>
        </div>
        <div className="doppelrand history">
          <div className="doppelrand-inner">
            <HistorySection jobs={jobs} onDeleteAll={handleDeleteAll} onSelectJob={setJob} />
          </div>
        </div>
        <SiteFooter />
      </main>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </>
  );
}
