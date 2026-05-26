import { ShieldAlert, ShieldCheck } from "lucide-react";
import type { Claim, ScoringResult } from "../types";
import { formatPercent } from "../utils/format";

type Props = {
  claim: Claim | null;
  score: ScoringResult | null;
};

export function VerdictPanel({ claim, score }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Verdict</h2>
          <span>{claim ? "Selected claim" : "No claim selected"}</span>
        </div>
        {score ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
      </div>

      {!claim ? <div className="empty-state">Select a claim to inspect its verdict.</div> : null}

      {claim && !score ? (
        <div className="empty-state">Verdict has not been scored for this claim yet.</div>
      ) : null}

      {claim && score ? (
        <div className="verdict-body">
          <div className={`verdict-badge verdict-${score.verdict.toLowerCase().replaceAll(" ", "-")}`}>
            {score.verdict}
          </div>
          <div className="confidence-bar">
            <span style={{ width: `${Math.round(score.confidence * 100)}%` }} />
          </div>
          <strong>{formatPercent(score.confidence)} confidence</strong>
          <p>{score.explanation}</p>
          {score.safeguards.blocked_reasons.length > 0 ? (
            <ul className="compact-list">
              {score.safeguards.blocked_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
