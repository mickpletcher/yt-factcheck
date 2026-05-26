import { ExternalLink, Link2 } from "lucide-react";
import { useState } from "react";
import type { EvidenceRetrievalResult } from "../types";
import { formatPercent } from "../utils/format";

type Props = {
  evidenceResult: EvidenceRetrievalResult | null;
};

export function EvidenceSection({ evidenceResult }: Props) {
  const [openIds, setOpenIds] = useState<Set<number | string>>(new Set());

  if (!evidenceResult) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Evidence</h2>
            <span>No evidence loaded</span>
          </div>
          <Link2 size={18} />
        </div>
        <div className="empty-state">Select a scored claim to review evidence.</div>
      </section>
    );
  }

  function toggle(id: number | string) {
    setOpenIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <section className="panel evidence-panel">
      <div className="panel-header">
        <div>
          <h2>Evidence</h2>
          <span>{evidenceResult.evidence.length} sources</span>
        </div>
        <Link2 size={18} />
      </div>

      <div className="query-row">
        {evidenceResult.queries.map((query) => (
          <span key={`${query.purpose}-${query.query}`}>{query.purpose}</span>
        ))}
      </div>

      <div className="evidence-list">
        {evidenceResult.evidence.map((item, index) => {
          const key = item.id ?? `${item.url}-${index}`;
          const isOpen = openIds.has(key);
          return (
            <article className="evidence-item" key={key}>
              <button type="button" onClick={() => toggle(key)}>
                <div>
                  <strong>{item.title || item.publisher || item.url}</strong>
                  <span>
                    {item.source_type} · {formatPercent(item.ranking_score)} rank
                  </span>
                </div>
                <span>{isOpen ? "Hide" : "Expand"}</span>
              </button>
              {isOpen ? (
                <div className="evidence-detail">
                  <p>{item.snippet || "No snippet returned."}</p>
                  <a href={item.url} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} />
                    {item.publisher || item.url}
                  </a>
                  <small>{item.attribution}</small>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
