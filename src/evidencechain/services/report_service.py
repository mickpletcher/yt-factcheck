from html import escape
from pathlib import Path
from time import time

from evidencechain.core.config import Settings, get_settings
from evidencechain.models.factcheck import Claim, RetrievedEvidence, ScoringResult, Verdict
from evidencechain.models.report import (
    ReportClaimSummary,
    ReportEvidenceLink,
    ReportExport,
    ReportFormat,
    ReportVerdictBucket,
    ReportVerdictSummary,
)
from evidencechain.reports.templates import HTML_REPORT_TEMPLATE, MARKDOWN_REPORT_TEMPLATE
from evidencechain.services.claim_service import ClaimNotFoundError, ClaimService
from evidencechain.services.evidence_service import EvidenceService
from evidencechain.services.scoring_service import ScoringNotFoundError, ScoringService
from evidencechain.services.transcript_service import TranscriptNotFoundError, TranscriptService


class ReportServiceError(Exception):
    pass


class ReportNotFoundError(ReportServiceError):
    pass


class ReportService:
    def __init__(
        self,
        settings: Settings | None = None,
        transcript_service: TranscriptService | None = None,
        claim_service: ClaimService | None = None,
        evidence_service: EvidenceService | None = None,
        scoring_service: ScoringService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transcript_service = transcript_service or TranscriptService(settings=self.settings)
        self.claim_service = claim_service or ClaimService(settings=self.settings)
        self.evidence_service = evidence_service or EvidenceService(settings=self.settings)
        self.scoring_service = scoring_service or ScoringService(
            settings=self.settings,
            evidence_service=self.evidence_service,
        )

    async def build_report(self, transcript_id: int) -> ReportExport:
        try:
            transcript = await self.transcript_service.get_transcript(transcript_id)
            claims = await self.claim_service.list_claims(transcript_id)
        except (TranscriptNotFoundError, ClaimNotFoundError) as error:
            raise ReportNotFoundError(str(error)) from error

        summaries = [await self._claim_summary(claim) for claim in claims if claim.id is not None]
        return ReportExport(
            transcript_id=transcript.id,
            video=transcript.metadata,
            verdict_summary=self._verdict_summary(summaries),
            claims=summaries,
        )

    async def render_report(self, transcript_id: int, report_format: ReportFormat) -> str:
        report = await self.build_report(transcript_id)
        if report_format == ReportFormat.json:
            return report.model_dump_json(indent=2)
        if report_format == ReportFormat.html:
            return self.render_html(report)
        if report_format == ReportFormat.markdown:
            return self.render_markdown(report)
        raise ReportServiceError(f"Unsupported report format: {report_format}")

    async def export_report(
        self,
        transcript_id: int,
        report_format: ReportFormat,
        output_dir: Path | None = None,
    ) -> Path:
        target_dir = output_dir or Path(self.settings.report_export_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        extension = "md" if report_format == ReportFormat.markdown else report_format.value
        target = target_dir / f"transcript-{transcript_id}.{extension}"
        target.write_text(await self.render_report(transcript_id, report_format), encoding="utf-8")
        return target

    def cleanup_exports(
        self,
        output_dir: Path | None = None,
        retention_days: int | None = None,
    ) -> dict[str, int]:
        target_dir = output_dir or Path(self.settings.report_export_dir)
        days = (
            self.settings.report_export_retention_days
            if retention_days is None
            else retention_days
        )
        if not target_dir.exists() or days < 0:
            return {"deleted": 0, "kept": 0}
        cutoff = time() - (days * 86400)
        deleted = 0
        kept = 0
        for path in target_dir.glob("transcript-*.*"):
            if not path.is_file():
                continue
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
            else:
                kept += 1
        return {"deleted": deleted, "kept": kept}

    def render_html(self, report: ReportExport) -> str:
        return HTML_REPORT_TEMPLATE.format(
            title=escape(report.video.title or f"Transcript {report.transcript_id}"),
            video_id=escape(report.video.video_id),
            channel=escape(report.video.channel or "Unknown"),
            youtube_url=escape(report.video.youtube_url),
            generated_at=escape(report.generated_at.isoformat()),
            total_claims=report.verdict_summary.total_claims,
            average_confidence=f"{report.verdict_summary.average_confidence:.0%}",
            verdict_buckets=self._html_buckets(report.verdict_summary.buckets),
            claims=self._html_claims(report.claims),
        )

    def render_markdown(self, report: ReportExport) -> str:
        return MARKDOWN_REPORT_TEMPLATE.format(
            title=report.video.title or f"Transcript {report.transcript_id}",
            video_id=report.video.video_id,
            channel=report.video.channel or "Unknown",
            youtube_url=report.video.youtube_url,
            generated_at=report.generated_at.isoformat(),
            total_claims=report.verdict_summary.total_claims,
            average_confidence=f"{report.verdict_summary.average_confidence:.0%}",
            verdict_buckets=self._markdown_buckets(report.verdict_summary.buckets),
            claims=self._markdown_claims(report.claims),
        ).strip() + "\n"

    async def _claim_summary(self, claim: Claim) -> ReportClaimSummary:
        if claim.id is None:
            raise ReportServiceError("Report claims must have stored IDs.")
        evidence = await self.evidence_service.list_claim_evidence(claim.id)
        latest_score = await self._latest_score(claim.id)
        cited_ids = set(latest_score.cited_evidence_ids if latest_score else [])
        evidence_links = [self._evidence_link(item, item.id in cited_ids) for item in evidence]
        citations = [item for item in evidence_links if item.cited]
        return ReportClaimSummary(
            id=claim.id,
            text=claim.text,
            category=claim.category,
            timestamp_seconds=claim.start_seconds,
            timestamp_label=self._timestamp_label(claim.start_seconds),
            claim_confidence=claim.confidence,
            verdict=latest_score.verdict if latest_score else Verdict.unverified,
            verdict_confidence=latest_score.confidence if latest_score else 0.0,
            explanation=latest_score.explanation if latest_score else "No verdict has been scored.",
            citations=citations,
            evidence_links=evidence_links,
        )

    async def _latest_score(self, claim_id: int) -> ScoringResult | None:
        try:
            scores = await self.scoring_service.list_results(claim_id)
        except ScoringNotFoundError as error:
            raise ReportNotFoundError(str(error)) from error
        return scores[0] if scores else None

    def _verdict_summary(self, claims: list[ReportClaimSummary]) -> ReportVerdictSummary:
        total = len(claims)
        average_confidence = (
            sum(claim.verdict_confidence for claim in claims) / total if total else 0.0
        )
        buckets = []
        for verdict in Verdict:
            count = sum(1 for claim in claims if claim.verdict == verdict)
            if count == 0:
                continue
            buckets.append(
                ReportVerdictBucket(
                    verdict=verdict,
                    count=count,
                    percentage=round((count / total) * 100, 1) if total else 0.0,
                )
            )
        return ReportVerdictSummary(
            total_claims=total,
            average_confidence=round(average_confidence, 3),
            buckets=buckets,
        )

    def _evidence_link(self, item: RetrievedEvidence, cited: bool) -> ReportEvidenceLink:
        if item.id is None:
            raise ReportServiceError("Report evidence must have stored IDs.")
        return ReportEvidenceLink(
            id=item.id,
            title=item.title,
            url=str(item.url),
            publisher=item.publisher,
            snippet=item.snippet,
            source_type=item.source_type.value,
            ranking_score=item.ranking_score,
            retrieved_at=item.retrieved_at,
            attribution=item.attribution,
            cited=cited,
        )

    def _html_buckets(self, buckets: list[ReportVerdictBucket]) -> str:
        if not buckets:
            return "<p>No scored claims yet.</p>"
        return "\n".join(
            (
                '<div class="bucket">'
                f"<strong>{escape(bucket.verdict.value)}</strong>"
                f"<div>{bucket.count} claim(s), {bucket.percentage:.1f}%</div>"
                '<div class="bar">'
                f'<div class="fill" style="width: {bucket.percentage:.1f}%"></div>'
                "</div></div>"
            )
            for bucket in buckets
        )

    def _html_claims(self, claims: list[ReportClaimSummary]) -> str:
        if not claims:
            return "<p>No claims have been extracted for this video.</p>"
        return "\n".join(self._html_claim(claim) for claim in claims)

    def _html_claim(self, claim: ReportClaimSummary) -> str:
        evidence = self._html_evidence(claim.evidence_links)
        return (
            '<article class="claim">'
            f"<h3>{escape(claim.text)}</h3>"
            '<div class="claim-meta">'
            f"<div><strong>Verdict:</strong> {escape(claim.verdict.value)}</div>"
            f"<div><strong>Confidence:</strong> {claim.verdict_confidence:.0%}</div>"
            f"<div><strong>Timestamp:</strong> {escape(claim.timestamp_label)}</div>"
            f"<div><strong>Category:</strong> {escape(claim.category.value)}</div>"
            "</div>"
            f"<p>{escape(claim.explanation)}</p>"
            f"{evidence}"
            "</article>"
        )

    def _html_evidence(self, links: list[ReportEvidenceLink]) -> str:
        if not links:
            return "<p>No linked evidence is stored for this claim.</p>"
        items = []
        for link in links:
            cited = ' <span class="badge">citation</span>' if link.cited else ""
            items.append(
                "<li>"
                f'<a href="{escape(link.url)}">{escape(link.title or link.url)}</a>{cited}'
                f"<div>{escape(link.publisher or 'Unknown')} | "
                f"Quality {link.ranking_score:.0%} | {escape(link.source_type)}</div>"
                f'<p class="snippet">{escape(link.snippet)}</p>'
                "</li>"
            )
        return f'<ol class="evidence">{"".join(items)}</ol>'

    def _markdown_buckets(self, buckets: list[ReportVerdictBucket]) -> str:
        if not buckets:
            return "No scored claims yet."
        return "\n".join(
            f"- {bucket.verdict.value}: {bucket.count} claim(s), {bucket.percentage:.1f}%"
            for bucket in buckets
        )

    def _markdown_claims(self, claims: list[ReportClaimSummary]) -> str:
        if not claims:
            return "No claims have been extracted for this video."
        return "\n\n".join(self._markdown_claim(claim) for claim in claims)

    def _markdown_claim(self, claim: ReportClaimSummary) -> str:
        evidence = self._markdown_evidence(claim.evidence_links)
        return (
            f"### {claim.text}\n\n"
            f"- Verdict: {claim.verdict.value}\n"
            f"- Verdict confidence: {claim.verdict_confidence:.0%}\n"
            f"- Claim confidence: {claim.claim_confidence:.0%}\n"
            f"- Timestamp: {claim.timestamp_label}\n"
            f"- Category: {claim.category.value}\n\n"
            f"{claim.explanation}\n\n"
            f"Evidence:\n\n{evidence}"
        )

    def _markdown_evidence(self, links: list[ReportEvidenceLink]) -> str:
        if not links:
            return "No linked evidence is stored for this claim."
        lines = []
        for index, link in enumerate(links, start=1):
            citation = " cited" if link.cited else ""
            lines.append(
                f"{index}. [{link.title or link.url}]({link.url})"
                f"{citation}. {link.publisher or 'Unknown'}, quality {link.ranking_score:.0%}."
                f"\n   {link.snippet}"
            )
        return "\n".join(lines)

    def _timestamp_label(self, seconds: float) -> str:
        rounded = int(seconds)
        hours, remainder = divmod(rounded, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
