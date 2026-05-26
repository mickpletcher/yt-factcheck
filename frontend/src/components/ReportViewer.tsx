import { ExternalLink, FileJson, FileText } from "lucide-react";
import { useState } from "react";
import type { ReportExport } from "../types";

type Props = {
  report: ReportExport | null;
  markdown: string;
  htmlUrl: string;
};

export function ReportViewer({ report, markdown, htmlUrl }: Props) {
  const [tab, setTab] = useState<"summary" | "markdown" | "json">("summary");

  return (
    <section className="panel report-panel">
      <div className="panel-header">
        <div>
          <h2>Final Report</h2>
          <span>{report ? `Generated ${new Date(report.generated_at).toLocaleString()}` : "Not ready"}</span>
        </div>
        {htmlUrl ? (
          <a className="icon-link" href={htmlUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            HTML
          </a>
        ) : null}
      </div>

      <div className="tabs">
        <button className={tab === "summary" ? "active" : ""} onClick={() => setTab("summary")}>
          <FileText size={15} />
          Summary
        </button>
        <button className={tab === "markdown" ? "active" : ""} onClick={() => setTab("markdown")}>
          <FileText size={15} />
          Markdown
        </button>
        <button className={tab === "json" ? "active" : ""} onClick={() => setTab("json")}>
          <FileJson size={15} />
          JSON
        </button>
      </div>

      {!report ? <div className="empty-state">Run the pipeline to render reports.</div> : null}

      {report && tab === "summary" ? (
        <div className="report-summary">
          <h3>{report.video.title || report.video.youtube_url || "EvidenceChain report"}</h3>
          <div className="bucket-row">
            {report.verdict_summary.buckets.map((bucket) => (
              <div className="bucket" key={bucket.verdict}>
                <strong>{bucket.count}</strong>
                <span>{bucket.verdict}</span>
              </div>
            ))}
          </div>
          <div className="report-claims">
            {report.claims.map((claim) => (
              <article key={claim.id}>
                <strong>{claim.verdict}</strong>
                <p>{claim.text}</p>
                <span>{claim.timestamp_label}</span>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {report && tab === "markdown" ? <pre className="report-code">{markdown}</pre> : null}
      {report && tab === "json" ? (
        <pre className="report-code">{JSON.stringify(report, null, 2)}</pre>
      ) : null}
    </section>
  );
}
