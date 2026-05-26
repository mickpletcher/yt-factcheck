import { Clock3 } from "lucide-react";
import type { Claim } from "../types";
import { formatPercent, formatTimestamp, timestampUrl } from "../utils/format";

type Props = {
  claims: Claim[];
  activeClaimId: number | null;
  youtubeUrl: string;
  onSelect: (claimId: number | null) => void;
};

export function ClaimList({ claims, activeClaimId, youtubeUrl, onSelect }: Props) {
  if (claims.length === 0) {
    return <div className="empty-state">No claims yet.</div>;
  }

  return (
    <div className="claim-list">
      {claims.map((claim) => {
        const isActive = claim.id === activeClaimId;
        return (
          <article
            className={`claim-card ${isActive ? "active" : ""}`}
            key={`${claim.id}-${claim.text}`}
          >
            <button type="button" onClick={() => onSelect(claim.id)} className="claim-button">
              <div className="claim-meta">
                <span>{claim.category}</span>
                <span>{formatPercent(claim.confidence)}</span>
              </div>
              <p>{claim.text}</p>
            </button>
            <a
              className="timestamp-link"
              href={timestampUrl(youtubeUrl, claim.start_seconds)}
              target="_blank"
              rel="noreferrer"
            >
              <Clock3 size={14} />
              {formatTimestamp(claim.start_seconds)}
            </a>
          </article>
        );
      })}
    </div>
  );
}
