export type PipelineStatus = "idle" | "queued" | "running" | "complete" | "error";

export type PipelineStepId =
  | "transcript"
  | "claims"
  | "evidence"
  | "verdicts"
  | "report";

export type PipelineStep = {
  id: PipelineStepId;
  label: string;
  status: PipelineStatus;
  detail: string;
};

export type VideoMetadata = {
  video_id: string;
  youtube_url: string;
  title: string;
  channel: string;
  duration_seconds: number | null;
  upload_date: string | null;
};

export type TranscriptSegment = {
  start_seconds: number;
  end_seconds: number;
  text: string;
};

export type TranscriptChunk = {
  position: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
  segment_start_index: number;
  segment_end_index: number;
};

export type TranscriptDetail = {
  id: number;
  metadata: VideoMetadata;
  source: "youtube" | "upload";
  language: string;
  raw_format: "txt" | "srt" | "vtt" | "json";
  segment_count: number;
  chunk_count: number;
  created_at: string;
  segments: TranscriptSegment[];
  chunks: TranscriptChunk[];
};

export type Claim = {
  id: number | null;
  transcript_id: number | null;
  chunk_position: number;
  text: string;
  category: string;
  confidence: number;
  start_seconds: number;
  end_seconds: number;
  source_text: string;
  created_at: string | null;
};

export type SearchQuery = {
  query: string;
  purpose: string;
};

export type RetrievedEvidence = {
  id: number | null;
  claim_id: number | null;
  provider: string;
  query: string;
  title: string;
  url: string;
  publisher: string;
  snippet: string;
  source_type: string;
  credibility_score: number;
  relevance_score: number;
  quality_score: number;
  ranking_score: number;
  attribution: string;
  retrieved_at: string;
};

export type EvidenceRetrievalResult = {
  run_id: number;
  claim_id: number | null;
  claim_text: string;
  provider: string;
  queries: SearchQuery[];
  evidence: RetrievedEvidence[];
};

export type EvidenceComparison = {
  evidence_id: number;
  relationship: "supports" | "contradicts" | "neutral";
  relevance_score: number;
  stance_score: number;
  explanation: string;
};

export type ScoringResult = {
  id: number | null;
  claim: Claim;
  verdict: string;
  confidence: number;
  explanation: string;
  evidence: RetrievedEvidence[];
  comparisons: EvidenceComparison[];
  cited_evidence_ids: number[];
  safeguards: {
    stored_evidence_only: boolean;
    has_sufficient_evidence: boolean;
    citation_validation_passed: boolean;
    blocked_reasons: string[];
  };
  created_at: string | null;
};

export type ReportEvidenceLink = {
  id: number;
  title: string;
  url: string;
  publisher: string;
  snippet: string;
  source_type: string;
  ranking_score: number;
  retrieved_at: string;
  attribution: string;
  cited: boolean;
};

export type ReportClaimSummary = {
  id: number;
  text: string;
  category: string;
  timestamp_seconds: number;
  timestamp_label: string;
  claim_confidence: number;
  verdict: string;
  verdict_confidence: number;
  explanation: string;
  citations: ReportEvidenceLink[];
  evidence_links: ReportEvidenceLink[];
};

export type ReportExport = {
  transcript_id: number;
  generated_at: string;
  video: VideoMetadata;
  verdict_summary: {
    total_claims: number;
    average_confidence: number;
    buckets: Array<{ verdict: string; count: number; percentage: number }>;
  };
  claims: ReportClaimSummary[];
};

export type PipelineInput = {
  youtubeUrl: string;
  transcriptFile: File | null;
  language: string;
  title: string;
};
