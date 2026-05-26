import type {
  Claim,
  EvidenceRetrievalResult,
  ReportExport,
  ScoringResult,
  TranscriptDetail
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : String(payload);
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return payload as T;
}

export async function createTranscriptFromUrl(
  youtubeUrl: string,
  language: string
): Promise<TranscriptDetail> {
  return request<TranscriptDetail>("/api/v1/transcripts/from-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ youtube_url: youtubeUrl, language })
  });
}

export async function uploadTranscript(input: {
  file: File;
  youtubeUrl: string;
  title: string;
  language: string;
}): Promise<TranscriptDetail> {
  const body = new FormData();
  body.append("file", input.file);
  body.append("language", input.language);
  body.append("title", input.title);
  if (input.youtubeUrl) {
    body.append("youtube_url", input.youtubeUrl);
  }

  return request<TranscriptDetail>("/api/v1/transcripts/upload", {
    method: "POST",
    body
  });
}

export async function extractClaims(transcriptId: number): Promise<Claim[]> {
  const result = await request<{ claims: Claim[] }>("/api/v1/claims/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript_id: transcriptId })
  });
  return result.claims;
}

export async function retrieveEvidence(claimId: number): Promise<EvidenceRetrievalResult> {
  return request<EvidenceRetrievalResult>("/api/v1/evidence/retrieve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim_id: claimId, max_results: 10 })
  });
}

export async function scoreClaim(claimId: number): Promise<ScoringResult> {
  return request<ScoringResult>(`/api/v1/scoring/claims/${claimId}`, {
    method: "POST"
  });
}

export async function getReport(transcriptId: number): Promise<ReportExport> {
  return request<ReportExport>(`/api/v1/reports/transcripts/${transcriptId}`);
}

export async function getMarkdownReport(transcriptId: number): Promise<string> {
  return request<string>(`/api/v1/reports/transcripts/${transcriptId}.md`);
}

export function htmlReportUrl(transcriptId: number): string {
  return `${API_BASE}/api/v1/reports/transcripts/${transcriptId}.html`;
}
