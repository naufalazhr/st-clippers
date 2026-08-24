"use client";

import { useState } from "react";
import { Eye, EyeOff, Loader2, RefreshCw, Sparkles } from "lucide-react";

type AiSectionProps = {
  aiEnabled: boolean;
  aiBaseUrl: string;
  aiModel: string;
  aiApiKey: string;
  aiModels: string[];
  isLoadingModels: boolean;
  onLoadModels: () => void;
  onAiEnabledChange: (value: boolean) => void;
  onAiBaseUrlChange: (value: string) => void;
  onAiModelChange: (value: string) => void;
  onAiApiKeyChange: (value: string) => void;
};

export function AiSection({
  aiEnabled,
  aiBaseUrl,
  aiModel,
  aiApiKey,
  aiModels,
  isLoadingModels,
  onLoadModels,
  onAiEnabledChange,
  onAiBaseUrlChange,
  onAiModelChange,
  onAiApiKeyChange,
}: AiSectionProps) {
  const [showKey, setShowKey] = useState(false);
  return (
    <div className="sectionBody">
      <div className="aiBlock">
        <label className="aiToggle">
          <span className="aiToggleLabel"><Sparkles size={16} /> AI Agent Pemilih Klip</span>
          <input type="checkbox" checked={aiEnabled} onChange={(event) => onAiEnabledChange(event.target.checked)} aria-label="AI Agent Pemilih Klip" />
        </label>
        <p className="field-help">LLM menilai setiap kandidat dan memilih bagian paling kuat untuk dijadikan klip.</p>

        {aiEnabled ? (
          <div className="aiFields">
            <label className="field wide">
              <span>Endpoint (Base URL)</span>
              <input value={aiBaseUrl} onChange={(event) => onAiBaseUrlChange(event.target.value)} placeholder="http://localhost:20128/v1" />
            </label>
            <label className="field wide">
              <span>API Key</span>
              <div className="passwordField">
                <input type={showKey ? "text" : "password"} value={aiApiKey} onChange={(event) => onAiApiKeyChange(event.target.value)} placeholder="sk-..." autoComplete="off" />
                <button type="button" className="passwordToggle" onClick={() => setShowKey((v) => !v)} aria-label={showKey ? "Sembunyikan API key" : "Tampilkan API key"}>
                  {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </label>
            <label className="field wide">
              <span>Model</span>
              <div className="modelRow">
                {aiModels.length > 0 ? (
                  <select className="fontSelect" value={aiModel} onChange={(event) => onAiModelChange(event.target.value)}>
                    {!aiModels.includes(aiModel) ? <option value={aiModel}>{aiModel}</option> : null}
                    {aiModels.map((model) => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                ) : (
                  <input value={aiModel} onChange={(event) => onAiModelChange(event.target.value)} placeholder="tr/MiniMax-M3" />
                )}
                <button type="button" className="loadModelsButton" onClick={onLoadModels} disabled={isLoadingModels || !aiBaseUrl.trim()}>
                  {isLoadingModels ? <Loader2 className="spin" size={14} /> : <RefreshCw size={14} />}
                  {aiModels.length > 0 ? "Refresh" : "Muat Model"}
                </button>
              </div>
            </label>
          </div>
        ) : null}
      </div>
    </div>
  );
}
