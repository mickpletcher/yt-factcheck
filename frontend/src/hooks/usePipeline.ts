import { useMemo, useReducer, type Dispatch } from "react";
import {
  cancelPipelineJob,
  getPipelineJob,
  getMarkdownReport,
  getReport,
  getTranscript,
  queueFactcheck,
  uploadTranscript
} from "../api/client";
import type {
  Claim,
  EvidenceRetrievalResult,
  PipelineInput,
  PipelineStep,
  PipelineStepId,
  ReportExport,
  ScoringResult,
  TranscriptDetail,
  PipelineJobDetail,
  ReportClaimSummary
} from "../types";

type PipelineState = {
  steps: PipelineStep[];
  transcript: TranscriptDetail | null;
  claims: Claim[];
  evidenceByClaim: Record<number, EvidenceRetrievalResult>;
  scoresByClaim: Record<number, ScoringResult>;
  report: ReportExport | null;
  markdownReport: string;
  activeClaimId: number | null;
  error: string;
  running: boolean;
  jobId: number | null;
};

type Action =
  | { type: "reset" }
  | { type: "step"; step: PipelineStepId; status: PipelineStep["status"]; detail: string }
  | { type: "transcript"; transcript: TranscriptDetail }
  | { type: "claims"; claims: Claim[] }
  | { type: "evidence"; claimId: number; evidence: EvidenceRetrievalResult }
  | { type: "score"; claimId: number; score: ScoringResult }
  | { type: "report"; report: ReportExport; markdownReport: string }
  | { type: "activeClaim"; claimId: number | null }
  | { type: "error"; message: string }
  | { type: "running"; running: boolean }
  | { type: "job"; jobId: number | null };

const initialSteps: PipelineStep[] = [
  { id: "transcript", label: "Transcript", status: "idle", detail: "Waiting for input" },
  { id: "claims", label: "Claims", status: "idle", detail: "Claims not extracted" },
  { id: "evidence", label: "Evidence", status: "idle", detail: "Evidence not retrieved" },
  { id: "verdicts", label: "Verdicts", status: "idle", detail: "Verdicts not scored" },
  { id: "report", label: "Report", status: "idle", detail: "Report not rendered" }
];

const initialState: PipelineState = {
  steps: initialSteps,
  transcript: null,
  claims: [],
  evidenceByClaim: {},
  scoresByClaim: {},
  report: null,
  markdownReport: "",
  activeClaimId: null,
  error: "",
  running: false,
  jobId: null
};

function reducer(state: PipelineState, action: Action): PipelineState {
  switch (action.type) {
    case "reset":
      return { ...initialState };
    case "step":
      return {
        ...state,
        steps: state.steps.map((step) =>
          step.id === action.step
            ? { ...step, status: action.status, detail: action.detail }
            : step
        )
      };
    case "transcript":
      return { ...state, transcript: action.transcript };
    case "claims":
      return {
        ...state,
        claims: action.claims,
        activeClaimId: action.claims[0]?.id ?? null
      };
    case "evidence":
      return {
        ...state,
        evidenceByClaim: { ...state.evidenceByClaim, [action.claimId]: action.evidence }
      };
    case "score":
      return {
        ...state,
        scoresByClaim: { ...state.scoresByClaim, [action.claimId]: action.score }
      };
    case "report":
      return { ...state, report: action.report, markdownReport: action.markdownReport };
    case "activeClaim":
      return { ...state, activeClaimId: action.claimId };
    case "error":
      return { ...state, error: action.message };
    case "running":
      return { ...state, running: action.running };
    case "job":
      return { ...state, jobId: action.jobId };
    default:
      return state;
  }
}

export function usePipeline() {
  const [state, dispatch] = useReducer(reducer, initialState);

  async function run(input: PipelineInput) {
    dispatch({ type: "reset" });
    dispatch({ type: "running", running: true });
    try {
      if (input.transcriptFile) {
        dispatch({
          type: "step",
          step: "transcript",
          status: "running",
          detail: "Uploading transcript"
        });
        const transcript = await uploadTranscript({
          file: input.transcriptFile,
          youtubeUrl: input.youtubeUrl.trim(),
          title: input.title.trim(),
          language: input.language.trim() || "en"
        });
        dispatch({ type: "transcript", transcript });
        await runQueued({ transcriptId: transcript.id });
      } else {
        await runQueued({ youtubeUrl: input.youtubeUrl.trim() });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Pipeline failed";
      dispatch({ type: "error", message });
      dispatch({ type: "step", step: "transcript", status: "error", detail: message });
    } finally {
      dispatch({ type: "running", running: false });
    }
  }

  async function runQueued(input: { youtubeUrl?: string; transcriptId?: number }) {
    dispatch({ type: "step", step: "transcript", status: "queued", detail: "Queued on backend" });
    try {
      const queued = await queueFactcheck(input);
      dispatch({ type: "job", jobId: queued.job_id });
      let job = await getPipelineJob(queued.job_id);
      while (["queued", "running", "retrying"].includes(job.status)) {
        applyQueuedProgress(job, dispatch);
        await sleep(1500);
        job = await getPipelineJob(queued.job_id);
      }
      applyQueuedProgress(job, dispatch);
      if (job.status === "canceled") {
        throw new Error("Pipeline job was canceled.");
      }
      if (job.status !== "succeeded" || job.transcript_id === null) {
        throw new Error(job.error_message ?? "Pipeline failed");
      }
      const [transcript, report, markdownReport] = await Promise.all([
        getTranscript(job.transcript_id),
        getReport(job.transcript_id),
        getMarkdownReport(job.transcript_id)
      ]);
      dispatch({ type: "transcript", transcript });
      dispatch({ type: "claims", claims: report.claims.map(reportClaimToClaim) });
      dispatch({ type: "report", report, markdownReport });
      for (const claim of report.claims) {
        dispatch({
          type: "evidence",
          claimId: claim.id,
          evidence: {
            run_id: 0,
            claim_id: claim.id,
            claim_text: claim.text,
            provider: "stored",
            queries: [],
            evidence: claim.evidence_links.map((link) => ({
              id: link.id,
              claim_id: claim.id,
              provider: "stored",
              query: "",
              title: link.title,
              url: link.url,
              publisher: link.publisher,
              snippet: link.snippet,
              source_type: link.source_type,
              credibility_score: link.ranking_score,
              relevance_score: link.ranking_score,
              quality_score: link.ranking_score,
              ranking_score: link.ranking_score,
              attribution: link.attribution,
              retrieved_at: link.retrieved_at
            }))
          }
        });
        dispatch({ type: "score", claimId: claim.id, score: reportClaimToScore(claim) });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Pipeline failed";
      dispatch({ type: "error", message });
      dispatch({ type: "step", step: "transcript", status: "error", detail: message });
    }
  }

  async function cancel() {
    if (state.jobId === null) {
      return;
    }
    await cancelPipelineJob(state.jobId);
    dispatch({ type: "running", running: false });
    dispatch({ type: "error", message: "Pipeline job was canceled." });
  }

  const activeClaim = useMemo(
    () => state.claims.find((claim) => claim.id === state.activeClaimId) ?? null,
    [state.activeClaimId, state.claims]
  );

  return {
    state,
    activeClaim,
    run,
    cancel,
    setActiveClaim: (claimId: number | null) => dispatch({ type: "activeClaim", claimId })
  };
}

function applyQueuedProgress(job: PipelineJobDetail, dispatch: Dispatch<Action>) {
  const stageMap: Record<string, PipelineStepId> = {
    transcript_ingestion: "transcript",
    chunking: "transcript",
    claim_extraction: "claims",
    evidence_retrieval: "evidence",
    scoring: "verdicts",
    report_generation: "report"
  };
  const activeStep = job.current_stage ? stageMap[job.current_stage] : null;
  const completed = completedSteps(activeStep, job.status);
  initialSteps.forEach((step) => {
    if (completed.includes(step.id)) {
      dispatch({ type: "step", step: step.id, status: "complete", detail: "Completed on backend" });
    } else if (step.id === activeStep) {
      dispatch({ type: "step", step: step.id, status: "running", detail: job.status });
    }
  });
}

function completedSteps(activeStep: PipelineStepId | null, status: PipelineJobDetail["status"]) {
  if (status === "succeeded") {
    return initialSteps.map((step) => step.id);
  }
  if (activeStep === null) {
    return [];
  }
  const activeIndex = initialSteps.findIndex((step) => step.id === activeStep);
  return initialSteps.slice(0, activeIndex).map((step) => step.id);
}

function reportClaimToClaim(claim: ReportClaimSummary): Claim {
  return {
    id: claim.id,
    transcript_id: null,
    chunk_position: 0,
    text: claim.text,
    category: claim.category,
    confidence: claim.claim_confidence,
    start_seconds: claim.timestamp_seconds,
    end_seconds: claim.timestamp_seconds,
    source_text: claim.text,
    created_at: null
  };
}

function reportClaimToScore(claim: ReportClaimSummary): ScoringResult {
  const convertedClaim = reportClaimToClaim(claim);
  return {
    id: null,
    claim: convertedClaim,
    verdict: claim.verdict,
    confidence: claim.verdict_confidence,
    explanation: claim.explanation,
    evidence: claim.evidence_links.map((link) => ({
      id: link.id,
      claim_id: claim.id,
      provider: "stored",
      query: "",
      title: link.title,
      url: link.url,
      publisher: link.publisher,
      snippet: link.snippet,
      source_type: link.source_type,
      credibility_score: link.ranking_score,
      relevance_score: link.ranking_score,
      quality_score: link.ranking_score,
      ranking_score: link.ranking_score,
      attribution: link.attribution,
      retrieved_at: link.retrieved_at
    })),
    comparisons: [],
    cited_evidence_ids: claim.citations.map((link) => link.id),
    safeguards: {
      stored_evidence_only: true,
      has_sufficient_evidence: claim.evidence_links.length > 0,
      citation_validation_passed: true,
      blocked_reasons: []
    },
    created_at: null
  };
}

function sleep(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
