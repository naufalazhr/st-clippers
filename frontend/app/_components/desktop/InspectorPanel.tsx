"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import type { ControlPanelProps } from "../ControlPanel";
import { AiSection } from "../sections/AiSection";
import { CropCaptionSection } from "../sections/CropCaptionSection";
import { HashtagsSection } from "../sections/HashtagsSection";
import { JobFooter } from "../sections/JobFooter";
import { RangeSection } from "../sections/RangeSection";
import { SourceSection } from "../sections/SourceSection";
import "./InspectorPanel.css";

function CollapseGroup({ title, defaultOpen, children }: { title: string; defaultOpen: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="collapseGroup" data-open={open ? "true" : "false"}>
      <button className="collapseGroup-header" aria-expanded={open} onClick={() => setOpen((v) => !v)} type="button">
        <ChevronRight size={14} className="collapseGroup-chevron" />
        {title}
      </button>
      <div className="collapseGroup-body">
        <div className="collapseGroup-inner">{children}</div>
      </div>
    </section>
  );
}

export function InspectorPanel(props: ControlPanelProps) {
  const hasSource = props.sourceMode === "url" ? Boolean(props.url.trim()) : Boolean(props.uploadFileName);
  const isStartDisabled = props.isSubmitting || props.isBusy || props.isUploading || !hasSource;
  const isProcessing = props.isSubmitting || props.isBusy;

  return (
    <aside className="inspectorPanel">
      <CollapseGroup title="Sumber Video" defaultOpen={true}>
        <SourceSection
          sourceMode={props.sourceMode}
          uploadFileName={props.uploadFileName}
          uploadPreviewUrl={props.uploadPreviewUrl}
          isUploading={props.isUploading}
          url={props.url}
          name={props.name}
          onNameChange={props.onNameChange}
          onSourceModeChange={props.onSourceModeChange}
          onUploadFileChange={props.onUploadFileChange}
          onUrlChange={props.onUrlChange}
        />
      </CollapseGroup>

      <CollapseGroup title="Durasi & Klip" defaultOpen={true}>
        <RangeSection
          maxDuration={props.maxDuration}
          minDuration={props.minDuration}
          targetClips={props.targetClips}
          maxClips={props.maxClips}
          videoDuration={props.videoDuration}
          onTargetClipsChange={props.onTargetClipsChange}
          onMaxDurationChange={props.onMaxDurationChange}
          onMinDurationChange={props.onMinDurationChange}
        />
      </CollapseGroup>

      <CollapseGroup title="Crop & Tampilan" defaultOpen={false}>
        <CropCaptionSection
          cropMode={props.cropMode}
          camCorner={props.camCorner}
          burnSubtitles={props.burnSubtitles}
          captionFontSize={props.captionFontSize}
          captionPosition={props.captionPosition}
          captionColor={props.captionColor}
          captionFont={props.captionFont}
          captionOutline={props.captionOutline}
          captionOutlineColor={props.captionOutlineColor}
          onCropModeChange={props.onCropModeChange}
          onCamCornerChange={props.onCamCornerChange}
          onBurnSubtitlesChange={props.onBurnSubtitlesChange}
          onCaptionFontSizeChange={props.onCaptionFontSizeChange}
          onCaptionPositionChange={props.onCaptionPositionChange}
          onCaptionColorChange={props.onCaptionColorChange}
          onCaptionFontChange={props.onCaptionFontChange}
          onCaptionOutlineChange={props.onCaptionOutlineChange}
          onCaptionOutlineColorChange={props.onCaptionOutlineColorChange}
        />
      </CollapseGroup>

      <CollapseGroup title="AI" defaultOpen={false}>
        <AiSection
          aiEnabled={props.aiEnabled}
          aiBaseUrl={props.aiBaseUrl}
          aiModel={props.aiModel}
          aiApiKey={props.aiApiKey}
          aiModels={props.aiModels}
          isLoadingModels={props.isLoadingModels}
          onLoadModels={props.onLoadModels}
          onAiEnabledChange={props.onAiEnabledChange}
          onAiBaseUrlChange={props.onAiBaseUrlChange}
          onAiModelChange={props.onAiModelChange}
          onAiApiKeyChange={props.onAiApiKeyChange}
        />
      </CollapseGroup>

      <CollapseGroup title="Hashtag" defaultOpen={false}>
        <HashtagsSection
          requiredHashtags={props.requiredHashtags}
          onRequiredHashtagsChange={props.onRequiredHashtagsChange}
        />
      </CollapseGroup>

      <div className="inspectorFooter">
        <JobFooter error={props.error} isStartDisabled={isStartDisabled} isProcessing={isProcessing} onStartJob={props.onStartJob} />
      </div>
    </aside>
  );
}
