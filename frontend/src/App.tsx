import { Activity, FileText, Moon, Play, Search, Upload, Youtube } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { htmlReportUrl } from "./api/client";
import { ClaimList } from "./components/ClaimList";
import { EvidenceSection } from "./components/EvidenceSection";
import { ProgressRail } from "./components/ProgressRail";
import { ReportViewer } from "./components/ReportViewer";
import { SummaryCards } from "./components/SummaryCards";
import { VerdictPanel } from "./components/VerdictPanel";
import { usePipeline } from "./hooks/usePipeline";
import type { PipelineInput } from "./types";

export function App() {
  const { state, activeClaim, run, setActiveClaim } = usePipeline();
  const [input, setInput] = useState<PipelineInput>({
    youtubeUrl: "",
    transcriptFile: null,
    language: "en",
    title: ""
  });
  const [search, setSearch] = useState("");

  const filteredClaims = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return state.claims;
    }
    return state.claims.filter((claim) =>
      [claim.text, claim.category, claim.source_text].some((value) =>
        value.toLowerCase().includes(query)
      )
    );
  }, [search, state.claims]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(input);
  }

  const activeClaimId = activeClaim?.id ?? null;
  const activeEvidence =
    activeClaimId === null ? null : state.evidenceByClaim[activeClaimId] ?? null;
  const activeScore = activeClaimId === null ? null : state.scoresByClaim[activeClaimId] ?? null;

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <div className="eyebrow">
            <Activity size={16} />
            EvidenceChain Dashboard
          </div>
          <h1>Fact check YouTube claims with stored evidence.</h1>
          <p>
            Submit a YouTube URL, upload a fallback transcript, watch the pipeline, then review
            claims, evidence, verdicts, and final reports in one workspace.
          </p>
        </div>
        <div className="theme-pill" title="Dark mode is enabled by the interface theme">
          <Moon size={16} />
          Dark
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="left-column">
          <form className="panel input-panel" onSubmit={onSubmit}>
            <div className="panel-header">
              <div>
                <h2>Input</h2>
                <span>URL transcript or uploaded fallback</span>
              </div>
              <Upload size={18} />
            </div>

            <label>
              <span>YouTube URL</span>
              <div className="input-with-icon">
                <Youtube size={18} />
                <input
                  value={input.youtubeUrl}
                  onChange={(event) =>
                    setInput((current) => ({ ...current, youtubeUrl: event.target.value }))
                  }
                  placeholder="https://www.youtube.com/watch?v=..."
                  type="url"
                />
              </div>
            </label>

            <div className="input-row">
              <label>
                <span>Language</span>
                <input
                  value={input.language}
                  onChange={(event) =>
                    setInput((current) => ({ ...current, language: event.target.value }))
                  }
                  placeholder="en"
                />
              </label>
              <label>
                <span>Upload title</span>
                <input
                  value={input.title}
                  onChange={(event) =>
                    setInput((current) => ({ ...current, title: event.target.value }))
                  }
                  placeholder="Optional"
                />
              </label>
            </div>

            <label className="file-drop">
              <FileText size={20} />
              <span>{input.transcriptFile?.name ?? "Upload .txt, .srt, .vtt, or .json"}</span>
              <input
                type="file"
                accept=".txt,.srt,.vtt,.json"
                onChange={(event) =>
                  setInput((current) => ({
                    ...current,
                    transcriptFile: event.target.files?.[0] ?? null
                  }))
                }
              />
            </label>

            <button
              className="primary-button"
              type="submit"
              disabled={state.running || (!input.youtubeUrl.trim() && !input.transcriptFile)}
            >
              <Play size={18} />
              {state.running ? "Running pipeline" : "Run fact check"}
            </button>
            {state.error ? <div className="error-box">{state.error}</div> : null}
          </form>

          <ProgressRail steps={state.steps} />
        </aside>

        <section className="main-column">
          <SummaryCards
            transcript={state.transcript}
            claims={state.claims}
            scores={Object.values(state.scoresByClaim)}
            report={state.report}
          />

          <div className="content-grid">
            <section className="panel claims-panel">
              <div className="panel-header">
                <div>
                  <h2>Claims</h2>
                  <span>{filteredClaims.length} visible</span>
                </div>
                <div className="search-box">
                  <Search size={16} />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search claims"
                  />
                </div>
              </div>
              <ClaimList
                claims={filteredClaims}
                activeClaimId={state.activeClaimId}
                youtubeUrl={state.transcript?.metadata.youtube_url ?? input.youtubeUrl}
                onSelect={setActiveClaim}
              />
            </section>

            <section className="detail-stack">
              <VerdictPanel claim={activeClaim} score={activeScore} />
              <EvidenceSection evidenceResult={activeEvidence} />
            </section>
          </div>

          <ReportViewer
            report={state.report}
            markdown={state.markdownReport}
            htmlUrl={state.transcript ? htmlReportUrl(state.transcript.id) : ""}
          />
        </section>
      </section>
    </main>
  );
}
