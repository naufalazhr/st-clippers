import { Scissors } from "lucide-react";
import type { CamCorner, CaptionFont, CaptionPosition, CropMode, SourceMode, WatermarkPosition, WatermarkType } from "../../types/clip.type";
import { CaptionPreview } from "./CaptionPreview";
import { AiSection } from "./sections/AiSection";
import { CropCaptionSection } from "./sections/CropCaptionSection";
import { HashtagsSection } from "./sections/HashtagsSection";
import { JobFooter } from "./sections/JobFooter";
import { RangeSection } from "./sections/RangeSection";
import { SourceSection } from "./sections/SourceSection";
import { WatermarkSection } from "./sections/WatermarkSection";

export type ControlPanelProps = {
  cropMode: CropMode;
  error: string;
  isBusy: boolean;
  isSubmitting: boolean;
  sourceMode: SourceMode;
  uploadFileName: string;
  uploadPreviewUrl: string;
  isUploading: boolean;
  camCorner: CamCorner;
  onCamCornerChange: (value: CamCorner) => void;
  onSourceModeChange: (mode: SourceMode) => void;
  onUploadFileChange: (file: File | null) => void;
  maxDuration: number;
  minDuration: number;
  targetClips: number;
  maxClips: number | null;
  videoDuration: number | null;
  onTargetClipsChange: (value: number) => void;
  burnSubtitles: boolean;
  captionFontSize: number;
  captionPosition: CaptionPosition;
  captionColor: string;
  captionFont: CaptionFont;
  captionOutline: number;
  captionOutlineColor: string;
  onCaptionFontChange: (value: CaptionFont) => void;
  onCaptionOutlineChange: (value: number) => void;
  onCaptionOutlineColorChange: (value: string) => void;
  aiEnabled: boolean;
  aiBaseUrl: string;
  aiModel: string;
  aiApiKey: string;
  aiModels: string[];
  isLoadingModels: boolean;
  onLoadModels: () => void;
  requiredHashtags: string[];
  onRequiredHashtagsChange: (tags: string[]) => void;
  onCropModeChange: (mode: CropMode) => void;
  onMaxDurationChange: (value: number) => void;
  onMinDurationChange: (value: number) => void;
  onBurnSubtitlesChange: (value: boolean) => void;
  onCaptionFontSizeChange: (value: number) => void;
  onCaptionPositionChange: (value: CaptionPosition) => void;
  onCaptionColorChange: (value: string) => void;
  onAiEnabledChange: (value: boolean) => void;
  onAiBaseUrlChange: (value: string) => void;
  onAiModelChange: (value: string) => void;
  onAiApiKeyChange: (value: string) => void;
  onStartJob: () => void;
  onUrlChange: (value: string) => void;
  url: string;
  name: string;
  onNameChange: (value: string) => void;
  watermarkType: WatermarkType;
  onWatermarkTypeChange: (value: WatermarkType) => void;
  watermarkText: string;
  onWatermarkTextChange: (value: string) => void;
  watermarkPosition: WatermarkPosition;
  onWatermarkPositionChange: (value: WatermarkPosition) => void;
  watermarkOpacity: number;
  onWatermarkOpacityChange: (value: number) => void;
  watermarkScale: number;
  onWatermarkScaleChange: (value: number) => void;
  watermarkFontFamily: string;
  onWatermarkFontFamilyChange: (value: string) => void;
  watermarkColor: string;
  onWatermarkColorChange: (value: string) => void;
  watermarkImage: File | null;
  onWatermarkImageChange: (file: File | null) => void;
  watermarkUploadedImageUrl: string | null;
};

export function ControlPanel(props: ControlPanelProps) {
  const hasSource = props.sourceMode === "url" ? Boolean(props.url.trim()) : Boolean(props.uploadFileName);
  const isStartDisabled = props.isSubmitting || props.isBusy || props.isUploading || !hasSource;
  const isProcessing = props.isSubmitting || props.isBusy;

  return (
    <section className="panel controlPanel">
      <div className="panelHeader">
        <Scissors size={20} />
        <h2>Potong Video</h2>
      </div>

      <div className="sectionEyebrow">Sumber Video</div>
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

      <div className="sectionEyebrow">Durasi & Klip</div>
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

      <div className="sectionEyebrow">Crop & Tampilan</div>
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
      {props.burnSubtitles ? (
        <CaptionPreview
          fontSize={props.captionFontSize}
          position={props.captionPosition}
          color={props.captionColor}
          font={props.captionFont}
          outline={props.captionOutline}
          outlineColor={props.captionOutlineColor}
        />
      ) : null}

      <div className="sectionEyebrow">Watermark</div>
      <WatermarkSection
        watermarkType={props.watermarkType}
        onWatermarkTypeChange={props.onWatermarkTypeChange}
        watermarkText={props.watermarkText}
        onWatermarkTextChange={props.onWatermarkTextChange}
        watermarkPosition={props.watermarkPosition}
        onWatermarkPositionChange={props.onWatermarkPositionChange}
        watermarkOpacity={props.watermarkOpacity}
        onWatermarkOpacityChange={props.onWatermarkOpacityChange}
        watermarkScale={props.watermarkScale}
        onWatermarkScaleChange={props.onWatermarkScaleChange}
        watermarkFontFamily={props.watermarkFontFamily}
        onWatermarkFontFamilyChange={props.onWatermarkFontFamilyChange}
        watermarkColor={props.watermarkColor}
        onWatermarkColorChange={props.onWatermarkColorChange}
        watermarkImage={props.watermarkImage}
        onWatermarkImageChange={props.onWatermarkImageChange}
        uploadedImageUrl={props.watermarkUploadedImageUrl}
      />

      <div className="sectionEyebrow">AI</div>
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

      <div className="sectionEyebrow">Hashtag</div>
      <HashtagsSection
        requiredHashtags={props.requiredHashtags}
        onRequiredHashtagsChange={props.onRequiredHashtagsChange}
      />

      <JobFooter error={props.error} isStartDisabled={isStartDisabled} isProcessing={isProcessing} onStartJob={props.onStartJob} />
    </section>
  );
}
