import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { PipelineStep } from "../types";

type Props = {
  steps: PipelineStep[];
};

export function ProgressRail({ steps }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Pipeline</h2>
          <span>Live progress</span>
        </div>
      </div>
      <ol className="progress-list">
        {steps.map((step) => (
          <li key={step.id} className={`progress-item status-${step.status}`}>
            <div className="progress-icon">
              {step.status === "complete" ? <CheckCircle2 size={18} /> : null}
              {step.status === "running" ? <Loader2 size={18} className="spin" /> : null}
              {step.status === "error" ? <XCircle size={18} /> : null}
              {step.status === "idle" || step.status === "queued" ? <Circle size={18} /> : null}
            </div>
            <div>
              <strong>{step.label}</strong>
              <span>{step.detail}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
