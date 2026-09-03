import type { ClipJob, CreateClipJobInput, TimelineData, ClipFile, ClipCandidate } from "../types/clip.type";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8010";
const CLIENT_API_BASE = API_BASE;

export const uploadVideo = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  // Upload straight to the backend; the Next.js proxy corrupts binary bodies.
  const response = await fetch(`${API_BASE}/api/uploads`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to upload video");
  }
  return (await response.json()) as {
    source_file: string;
    original_name: string;
    duration: number | null;
  };
};

export const fetchModels = async (baseUrl: string, apiKey: string) => {
  const response = await fetch(`${API_BASE}/api/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to load models");
  }
  const data = (await response.json()) as { models: string[] };
  return data.models;
};

export const probeUrlDuration = async (url: string): Promise<{ duration: number | null; title: string | null } | null> => {
  const response = await fetch(`${API_BASE}/api/probe?url=${encodeURIComponent(url)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }
  const data = (await response.json()) as { duration: number | null; title: string | null };
  return data;
};

export const getJobs = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }
  return (await response.json()) as ClipJob[];
};

export const deleteJobs = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Failed to delete jobs");
  }
};

export const deleteJob = async (jobId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Failed to delete job");
  }
};

export const getJob = async (jobId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load job");
  }
  return (await response.json()) as ClipJob;
};

export const createJob = async (input: CreateClipJobInput) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to create job");
  }

  return (await response.json()) as ClipJob;
};

export type ModelStatus = {
  model_present: boolean;
  model_name: string;
  download_progress: number | null;
};

export const fetchModelStatus = async () => {
  // The backend takes a few seconds to bind on a cold start, so this poll runs
  // before it is listening. Report that as null (the caller retries on null)
  // instead of letting the rejection escape as an unhandled error.
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/model-status`, { cache: "no-store" });
  } catch {
    return null;
  }
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as ModelStatus;
};

export const getOutputUrl = (path: string) => `${API_BASE}${path}`;

export type RecutResponse = {
  /** The render runs in the background; poll the job for progress. */
  status: string;
  index: number;
};

export const getTimeline = async (jobId: string): Promise<TimelineData> => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/timeline`, { cache: "no-store" });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<TimelineData>;
};

export const uploadWatermarkImage = async (jobId: string, file: File): Promise<{ url: string }> => {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}/watermark-upload`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to upload watermark image");
  }
  return response.json() as Promise<{ url: string }>;
};

export const recutClip = async (jobId: string, body: { index: number; start: number; end: number; segments?: { start: number; end: number; text: string }[]; caption_style?: string; caption_box_opacity?: number | null; transition?: string }): Promise<RecutResponse> => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/recut`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<RecutResponse>;
};


// --- MCP (local agent access) ----------------------------------------------

export type McpStatus = {
  enabled: boolean;
  running: boolean;
  preferred_port: number;
  /** The port actually bound. Not the preferred one -- it moves when taken. */
  bound_port: number | null;
  /** True when the bound port differs from the one an agent config may hold. */
  port_changed: boolean;
  last_error: string | null;
  token: string;
  url: string | null;
};

export const getMcpStatus = async (): Promise<McpStatus> => {
  const response = await fetch(`${API_BASE}/api/mcp/status`, { cache: "no-store" });
  if (!response.ok) throw new Error("Gagal memuat status MCP");
  return (await response.json()) as McpStatus;
};

export const setMcpEnabled = async (enabled: boolean): Promise<McpStatus> => {
  const response = await fetch(`${API_BASE}/api/mcp/enabled`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as McpStatus;
};

export const regenerateMcpToken = async (): Promise<McpStatus> => {
  const response = await fetch(`${API_BASE}/api/mcp/regenerate-token`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as McpStatus;
};
