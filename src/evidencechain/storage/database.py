import aiosqlite

from evidencechain.core.config import Settings

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
"""


async def initialize_database(settings: Settings) -> None:
    database_path = settings.sqlite_path
    database_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(database_path) as connection:
        await connection.executescript(SCHEMA)
        await connection.commit()
