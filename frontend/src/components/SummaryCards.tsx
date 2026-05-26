import { BarChart3, FileCheck2, ScrollText, ShieldCheck } from "lucide-react";
import type { Claim, ReportExport, ScoringResult, TranscriptDetail } from "../types";
import { formatPercent } from "../utils/format";

type Props = {
  transcript: TranscriptDetail | null;
  claims: Claim[];
  scores: ScoringResult[];
  report: ReportExport | null;
};

export function SummaryCards({ transcript, claims, scores, report }: Props) {
  const avgConfidence =
    scores.length === 0
      ? 0
      : scores.reduce((total, score) => total + score.confidence, 0) / scores.length;

  return (
    <section className="summary-grid">
      <article className="metric-card">
        <ScrollText size={20} />
        <span>Transcript</span>
        <strong>{transcript ? `${transcript.segment_count} segments` : "Not loaded"}</strong>
      </article>
      <article className="metric-card">
        <FileCheck2 size={20} />
        <span>Claims</span>
        <strong>{claims.length}</strong>
      </article>
      <article className="metric-card">
        <ShieldCheck size={20} />
        <span>Verdicts</span>
        <strong>{scores.length}</strong>
      </article>
      <article className="metric-card">
        <BarChart3 size={20} />
        <span>Avg confidence</span>
        <strong>{report ? formatPercent(report.verdict_summary.average_confidence) : formatPercent(avgConfidence)}</strong>
      </article>
    </section>
  );
}
