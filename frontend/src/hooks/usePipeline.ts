import { useMemo, useReducer } from "react";
import {
  createTranscriptFromUrl,
  extractClaims,
  getMarkdownReport,
  getReport,
  retrieveEvidence,
  scoreClaim,
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
  TranscriptDetail
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
  | { type: "running"; running: boolean };

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
  running: false
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
    default:
      return state;
  }
}

export function usePipeline() {
  const [state, dispatch] = useReducer(reducer, initialState);

  async function run(input: PipelineInput) {
    dispatch({ type: "reset" });
    dispatch({ type: "running", running: true });
    let currentStep: PipelineStepId = "transcript";

    try {
      currentStep = "transcript";
      dispatch({ type: "step", step: "transcript", status: "running", detail: "Creating transcript" });
      const transcript = input.transcriptFile
        ? await uploadTranscript({
            file: input.transcriptFile,
            youtubeUrl: input.youtubeUrl.trim(),
            title: input.title.trim(),
            language: input.language.trim() || "en"
          })
        : await createTranscriptFromUrl(input.youtubeUrl.trim(), input.language.trim() || "en");
      dispatch({ type: "transcript", transcript });
      dispatch({
        type: "step",
        step: "transcript",
        status: "complete",
        detail: `${transcript.segment_count} segments, ${transcript.chunk_count} chunks`
      });

      currentStep = "claims";
      dispatch({ type: "step", step: "claims", status: "running", detail: "Extracting claims" });
      const claims = await extractClaims(transcript.id);
      dispatch({ type: "claims", claims });
      currentStep = "evidence";
      dispatch({
        type: "step",
        step: "claims",
        status: "complete",
        detail: `${claims.length} claims extracted`
      });

      currentStep = "verdicts";
      dispatch({
        type: "step",
        step: "evidence",
        status: "running",
        detail: `Retrieving evidence for ${claims.length} claims`
      });
      for (const [index, claim] of claims.entries()) {
        if (claim.id === null) {
          continue;
        }
        dispatch({
          type: "step",
          step: "evidence",
          status: "running",
          detail: `Claim ${index + 1} of ${claims.length}`
        });
        const evidence = await retrieveEvidence(claim.id);
        dispatch({ type: "evidence", claimId: claim.id, evidence });
      }
      dispatch({ type: "step", step: "evidence", status: "complete", detail: "Evidence stored" });

      dispatch({
        type: "step",
        step: "verdicts",
        status: "running",
        detail: `Scoring ${claims.length} claims`
      });
      for (const [index, claim] of claims.entries()) {
        if (claim.id === null) {
          continue;
        }
        dispatch({
          type: "step",
          step: "verdicts",
          status: "running",
          detail: `Verdict ${index + 1} of ${claims.length}`
        });
        const score = await scoreClaim(claim.id);
        dispatch({ type: "score", claimId: claim.id, score });
      }
      dispatch({ type: "step", step: "verdicts", status: "complete", detail: "Verdicts scored" });

      currentStep = "report";
      dispatch({ type: "step", step: "report", status: "running", detail: "Rendering reports" });
      const [report, markdownReport] = await Promise.all([
        getReport(transcript.id),
        getMarkdownReport(transcript.id)
      ]);
      dispatch({ type: "report", report, markdownReport });
      dispatch({ type: "step", step: "report", status: "complete", detail: "Reports ready" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Pipeline failed";
      dispatch({ type: "error", message });
      dispatch({ type: "step", step: currentStep, status: "error", detail: message });
    } finally {
      dispatch({ type: "running", running: false });
    }
  }

  const activeClaim = useMemo(
    () => state.claims.find((claim) => claim.id === state.activeClaimId) ?? null,
    [state.activeClaimId, state.claims]
  );

  return {
    state,
    activeClaim,
    run,
    setActiveClaim: (claimId: number | null) => dispatch({ type: "activeClaim", claimId })
  };
}
