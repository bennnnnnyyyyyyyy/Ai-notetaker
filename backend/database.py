import aiosqlite
from pathlib import Path
import yaml
from backend.config import settings

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS campaigns (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    config_path     TEXT NOT NULL,
    config_version  TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meetings (
    id                  TEXT PRIMARY KEY,
    url                 TEXT NOT NULL,
    campaign_id         TEXT REFERENCES campaigns(id),
    meeting_type        TEXT NOT NULL CHECK(meeting_type IN ('discovery','negotiation','onboarding')),
    opener_name         TEXT,
    closer_name         TEXT,
    scheduled_at        TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK(status IN (
                                'pending','joining','waiting_for_admission',
                                'recording','meeting_ended','processing',
                                'completed','failed','cancelled'
                            )),
    pre_booking_notes   TEXT,
    error_message       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recordings (
    id                  TEXT PRIMARY KEY,
    meeting_id          TEXT NOT NULL REFERENCES meetings(id),
    file_path           TEXT NOT NULL,
    duration_seconds    REAL,
    captured_at         TEXT NOT NULL DEFAULT (datetime('now')),
    error               TEXT
);

CREATE TABLE IF NOT EXISTS transcripts (
    id          TEXT PRIMARY KEY,
    meeting_id  TEXT NOT NULL REFERENCES meetings(id),
    file_path   TEXT NOT NULL,
    model_used  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id              TEXT PRIMARY KEY,
    transcript_id   TEXT NOT NULL REFERENCES transcripts(id),
    segment_index   INTEGER NOT NULL,
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER,
    speaker_id      TEXT,
    text            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id                      TEXT PRIMARY KEY,
    meeting_id              TEXT NOT NULL REFERENCES meetings(id),
    version                 INTEGER NOT NULL DEFAULT 1,
    campaign_config_version TEXT,
    file_path               TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'draft'
                                CHECK(status IN ('draft','validated','reviewed')),
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS report_reviews (
    id              TEXT PRIMARY KEY,
    report_id       TEXT NOT NULL REFERENCES reports(id),
    reviewer        TEXT NOT NULL,
    feedback        TEXT,
    corrections     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    id              TEXT PRIMARY KEY,
    token_hash      TEXT NOT NULL UNIQUE,
    csrf_hash       TEXT NOT NULL,
    username        TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    revoked_at      TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id              TEXT PRIMARY KEY,
    actor           TEXT,
    action          TEXT NOT NULL,
    result          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    detail          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

async def get_db() -> aiosqlite.Connection:
    """Dependency: yields a connected aiosqlite connection with row_factory set."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def init_db() -> None:
    """Create tables if they don't exist. Called once at startup."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(_DDL)
        await seed_campaigns(conn)
        await recover_interrupted_meetings(conn)
        await conn.commit()


async def seed_campaigns(conn: aiosqlite.Connection) -> None:
    """Register bundled campaign YAML files without overwriting local edits."""
    campaigns_dir = Path(__file__).resolve().parent / "campaigns"
    for config_path in sorted(campaigns_dir.glob("*.yaml")):
        with config_path.open(encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        campaign_id = config.get("campaign_id")
        if not campaign_id or campaign_id == "example_campaign":
            continue
        await conn.execute(
            """
            INSERT OR IGNORE INTO campaigns (id, name, config_path, config_version)
            VALUES (?, ?, ?, ?)
            """,
            (
                campaign_id,
                config.get("name", campaign_id),
                str(config_path),
                str(config.get("version", "1.0")),
            ),
        )
    # Retain the earlier scaffold record for historical meeting references,
    # but prevent it from being selected for new meetings.
    await conn.execute(
        "UPDATE campaigns SET active = 0 WHERE id IN ('cgm_healthcare', 'example_campaign')"
    )


async def recover_interrupted_meetings(conn: aiosqlite.Connection) -> None:
    """Make jobs interrupted by a server stop explicitly retryable."""
    await conn.execute(
        """
        UPDATE meetings
        SET status = 'failed',
            error_message = 'Capture was interrupted when the application stopped; retry is available.',
            updated_at = datetime('now')
        WHERE status IN ('joining', 'recording', 'processing')
        """
    )
