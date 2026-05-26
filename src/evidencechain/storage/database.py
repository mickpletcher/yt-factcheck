import aiosqlite

from evidencechain.core.config import Settings

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS factcheck_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS verification_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    report_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES factcheck_runs(id)
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    youtube_url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER,
    upload_date TEXT,
    source TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    raw_format TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcript_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    text TEXT NOT NULL,
    segment_start_index INTEGER NOT NULL,
    segment_end_index INTEGER NOT NULL,
    FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS claim_extraction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    extraction_run_id INTEGER NOT NULL,
    chunk_position INTEGER NOT NULL,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    source_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
    FOREIGN KEY(extraction_run_id) REFERENCES claim_extraction_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcript_segments_transcript_id
ON transcript_segments(transcript_id);

CREATE INDEX IF NOT EXISTS idx_transcript_chunks_transcript_id
ON transcript_chunks(transcript_id);

CREATE INDEX IF NOT EXISTS idx_claim_extraction_runs_transcript_id
ON claim_extraction_runs(transcript_id);

CREATE INDEX IF NOT EXISTS idx_claims_transcript_id
ON claims(transcript_id);

CREATE TABLE IF NOT EXISTS evidence_retrieval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER,
    claim_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    queries_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(claim_id) REFERENCES claims(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    claim_id INTEGER,
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    publisher TEXT NOT NULL,
    snippet TEXT NOT NULL,
    source_type TEXT NOT NULL,
    credibility_score REAL NOT NULL,
    relevance_score REAL NOT NULL,
    quality_score REAL NOT NULL,
    ranking_score REAL NOT NULL,
    attribution TEXT NOT NULL,
    retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_result_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES evidence_retrieval_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(claim_id) REFERENCES claims(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evidence_retrieval_runs_claim_id
ON evidence_retrieval_runs(claim_id);

CREATE INDEX IF NOT EXISTS idx_evidence_sources_claim_id
ON evidence_sources(claim_id);

CREATE INDEX IF NOT EXISTS idx_evidence_sources_run_id
ON evidence_sources(run_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_sources_run_url
ON evidence_sources(run_id, url);

CREATE TABLE IF NOT EXISTS scoring_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    verdict TEXT NOT NULL,
    confidence REAL NOT NULL,
    explanation TEXT NOT NULL,
    cited_evidence_ids_json TEXT NOT NULL,
    comparisons_json TEXT NOT NULL,
    safeguards_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(claim_id) REFERENCES claims(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scoring_results_claim_id
ON scoring_results(claim_id);

CREATE TABLE IF NOT EXISTS search_cache (
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    response_json TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(provider, query)
);

CREATE TABLE IF NOT EXISTS pipeline_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    current_stage TEXT,
    transcript_id INTEGER,
    claim_ids_json TEXT NOT NULL DEFAULT '[]',
    report_json TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL,
    queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_status
ON pipeline_jobs(status);

CREATE TABLE IF NOT EXISTS pipeline_stage_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    progress REAL NOT NULL DEFAULT 0,
    started_at TEXT,
    completed_at TEXT,
    duration_ms REAL,
    error_message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES pipeline_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipeline_stage_runs_job_id
ON pipeline_stage_runs(job_id);

CREATE TABLE IF NOT EXISTS pipeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    stage TEXT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES pipeline_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipeline_events_job_id
ON pipeline_events(job_id);
"""

MIGRATIONS: dict[int, str] = {
    1: """
    ALTER TABLE pipeline_jobs
    ADD COLUMN cancelled_at TEXT;
    """,
    2: """
    CREATE TABLE IF NOT EXISTS provider_usage_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_type TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT '',
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        cost_usd REAL NOT NULL DEFAULT 0,
        cache_hit INTEGER NOT NULL DEFAULT 0,
        search_query TEXT NOT NULL DEFAULT '',
        success INTEGER NOT NULL DEFAULT 1,
        error_message TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_provider_usage_events_type_provider
    ON provider_usage_events(provider_type, provider);

    CREATE INDEX IF NOT EXISTS idx_provider_usage_events_created_at
    ON provider_usage_events(created_at);
    """,
}


async def initialize_database(settings: Settings) -> None:
    database_path = settings.sqlite_path
    database_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(database_path) as connection:
        await connection.execute("PRAGMA foreign_keys = ON")
        await connection.executescript(SCHEMA)
        await apply_migrations(connection)
        await connection.commit()


async def apply_migrations(connection: aiosqlite.Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor = await connection.execute("SELECT MAX(version) FROM schema_migrations")
    row = await cursor.fetchone()
    current_version = int(row[0] or 0) if row else 0
    for version in range(current_version + 1, SCHEMA_VERSION + 1):
        await connection.executescript(MIGRATIONS[version])
        await connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (version,),
        )
