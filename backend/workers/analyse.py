"""
Analysis worker — Milestone 3.

Implements the 8-stage analysis pipeline defined in MAIN.md §10.
Uses OllamaLLMAdapter with phi3:mini by default.

Stages:
  1  Transcript quality assessment
  2  Fact extraction
  3  Qualification assessment
  4  Opener assessment
  5  Closer scorecard
  6  Outcome assessment
  7  Report consolidation
  8  Schema validation (Pydantic)
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from backend.config import settings
from backend.adapters.ollama_llm import OllamaLLMAdapter
from backend.schemas.report import Report

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def run_analysis(meeting_id: str) -> None:
    """Entry point from the /analyze API endpoint."""
    from backend.database import get_db
    db_path = str(settings.database_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await run_analysis_with_db(meeting_id, db)


async def run_analysis_with_db(meeting_id: str, db: aiosqlite.Connection) -> None:
    """Called internally after transcription completes."""
    try:
        meeting, transcript, campaign = await _load_inputs(meeting_id, db)
        report_json = await _run_pipeline(meeting, transcript, campaign)
        await _save_report(meeting_id, report_json, campaign, db)
        await db.execute(
            "UPDATE meetings SET status = 'completed', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), meeting_id),
        )
        await db.commit()
        logger.info("Analysis complete for meeting %s", meeting_id)

    except Exception as exc:
        logger.exception("Analysis failed for meeting %s", meeting_id)
        await db.execute(
            "UPDATE meetings SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
            (str(exc), datetime.utcnow().isoformat(), meeting_id),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def _load_inputs(meeting_id: str, db: aiosqlite.Connection):
    async with db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)) as cur:
        meeting = dict(await cur.fetchone())

    async with db.execute(
        "SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY created_at DESC LIMIT 1",
        (meeting_id,),
    ) as cur:
        t_row = await cur.fetchone()
    if not t_row:
        raise ValueError("No transcript found for this meeting")

    with open(t_row["file_path"]) as f:
        transcript = json.load(f)

    campaign = {}
    if meeting.get("campaign_id"):
        async with db.execute(
            "SELECT * FROM campaigns WHERE id = ?", (meeting["campaign_id"],)
        ) as cur:
            c_row = await cur.fetchone()
        if c_row:
            with open(c_row["config_path"]) as f:
                import yaml
                campaign = yaml.safe_load(f)

    return meeting, transcript, campaign


async def _run_pipeline(meeting: dict, transcript: dict, campaign: dict) -> dict:
    llm = OllamaLLMAdapter()
    if not llm.is_available():
        raise RuntimeError(
            f"Ollama model '{settings.ollama_model}' is not available. "
            f"Run: ollama pull {settings.ollama_model}"
        )

    # Flatten segments to plain text with timestamps for prompting
    flat_text = _flatten_transcript(transcript)
    chunks = _chunk_text(flat_text, settings.ollama_chunk_tokens)

    system_base = _build_system_prompt(meeting, campaign)

    # Stage 1 — quality
    quality_notes = llm.generate(system_base, _prompt_quality(flat_text[:4000]))

    # Stage 2 — fact extraction (chunked, then consolidated)
    facts_parts = []
    for chunk in chunks:
        facts_parts.append(llm.generate(system_base, _prompt_facts(chunk)))
    facts_text = "\n---\n".join(facts_parts)

    # Stage 3 — qualification
    qualification = llm.generate(system_base, _prompt_qualification(facts_text, campaign))

    # Stage 4 — opener
    opener = llm.generate(system_base, _prompt_opener(facts_text, meeting))

    # Stage 5 — closer
    closer = llm.generate(system_base, _prompt_closer(facts_text))

    # Stage 6 — outcome
    outcome = llm.generate(system_base, _prompt_outcome(facts_text))

    # Stage 7 — consolidate into final JSON
    final_prompt = _prompt_consolidate(
        meeting, facts_text, qualification, opener, closer, outcome, quality_notes
    )
    raw_report = llm.generate(system_base, final_prompt)

    # Stage 8 — extract and validate JSON
    report_dict = _extract_json(raw_report)
    report_dict["meeting_id"] = meeting["id"]
    report_dict["campaign_id"] = meeting.get("campaign_id")
    report_dict["campaign_config_version"] = campaign.get("version")

    # Pydantic validation
    Report.model_validate(report_dict)
    return report_dict


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt(meeting: dict, campaign: dict) -> str:
    campaign_block = (
        f"Campaign: {campaign.get('name', 'Unknown')}\n"
        f"Campaign version: {campaign.get('version', 'Unknown')}\n"
        f"Qualification requirements: {json.dumps(campaign.get('qualification', {}), indent=2)}"
        if campaign else "No campaign configuration provided — flag report for review."
    )
    return f"""You are a sales meeting analyst for Prime Ad.
Your job is to produce an evidence-based meeting analysis report.

Rules:
- Distinguish: Confirmed fact | Prospect statement | Prime Ad statement | AI assessment | Explicit commitment | Unknown | Unresolved.
- Interest is NOT a commitment.
- A second meeting is confirmed ONLY when a specific date and time are agreed.
- Commercial terms are recorded only when discussed — do not calculate ROI.
- If speaker identity is uncertain, state the uncertainty; do not invent a name.
- Mark any field you cannot establish as "unknown", "unresolved", or "not_assessable".
- Do NOT fabricate details.
- Reference segment IDs (e.g. seg_0001) as evidence wherever possible.

Meeting type: {meeting.get('meeting_type', 'unknown')}
Opener: {meeting.get('opener_name', 'Unknown')}
Closer: {meeting.get('closer_name', 'Unknown')}

{campaign_block}
"""


def _prompt_quality(sample: str) -> str:
    return f"""Stage 1 — Transcript Quality

Review the following transcript excerpt and report:
- Missing or unclear sections
- Unclear speaker attribution
- Audio gaps or overlapping speech
- Any other quality limitations

Transcript excerpt:
{sample}

Respond in plain text."""


def _prompt_facts(chunk: str) -> str:
    return f"""Stage 2 — Fact Extraction

Extract all relevant facts from this transcript chunk. For each fact, note:
- The segment ID reference (e.g. seg_0001)
- The evidence type (Confirmed fact / Prospect statement / Prime Ad statement / etc.)

Extract:
- Prospect identity, role, company
- Stated needs and pain points
- Business profile
- Authority and decision process
- Objections raised
- Commercial terms mentioned
- Explicit commitments
- Proposed or agreed next steps
- Unresolved questions

Transcript chunk:
{chunk}

Respond in plain text."""


def _prompt_qualification(facts: str, campaign: dict) -> str:
    criteria = json.dumps(campaign.get("qualification", {}).get("requirements", []), indent=2)
    return f"""Stage 3 — Qualification Assessment

Based on the extracted facts below, assess each qualification criterion.
For each criterion: status = met | unmet | unknown

Universal criteria:
1. Suitable business for Prime Ad's services
2. Relevant business need
3. Decision-making authority or access
4. Willingness to discuss a paid service

Campaign-specific criteria:
{criteria}

Facts:
{facts}

Respond with a JSON object: {{"status": "<Confirmed fit|Potential fit — unconfirmed|Outside ICP|Insufficient information>", "criteria": [{{"id": "...", "status": "...", "evidence": "..."}}]}}"""


def _prompt_opener(facts: str, meeting: dict) -> str:
    return f"""Stage 4 — Opener Assessment

Opener name: {meeting.get('opener_name', 'Unknown')}
Pre-booking notes: {meeting.get('pre_booking_notes', 'None provided')}

Based on the facts extracted from the meeting, score the opener (1–5) on:
- booking_quality: Was the right type of prospect booked?
- information_accuracy: Was the pre-booking information correct?
- expectation_setting: Were prospect expectations set appropriately?
- pre_meeting_capture: Was relevant information recorded before the meeting?

Use "not_assessable" if there is insufficient evidence.
Do not penalise the opener for information unavailable before the meeting.

Facts: {facts}

Respond with JSON matching the OpenerScorecard schema."""


def _prompt_closer(facts: str) -> str:
    return f"""Stage 5 — Closer Scorecard

Score the closer (1–5) on:
- discovery: Did the closer understand the prospect's real needs?
- presentation: Did the closer explain the service clearly?
- objection_handling: Did the closer address concerns?
- qualification: Did the closer establish need, readiness, and commitment?
- closing_effectiveness: Did the closer ask for the sale or secure a confirmed second meeting?

Also note:
- conversation_control
- unanswered_material_questions

Use "not_assessable" if evidence is insufficient.
Do not infer quality from the deal outcome alone.

Facts: {facts}

Respond with JSON matching the CloserScorecard schema."""


def _prompt_outcome(facts: str) -> str:
    return f"""Stage 6 — Outcome Assessment

Based on the facts, identify the meeting outcome. Choose one:
- Closed / purchase committed
- Qualified opportunity — second meeting booked  (only if specific date AND time agreed)
- Interested — no confirmed next meeting
- Follow-up required
- Unqualified
- Lost or declined
- Inconclusive — insufficient evidence

Also identify the current pipeline stage:
meeting booked | attended | contract sent | invoice sent | signed | onboarded

Facts: {facts}

Respond with JSON: {{"outcome": "...", "pipeline_stage": "..."}}"""


def _prompt_consolidate(meeting, facts, qualification, opener, closer, outcome, quality) -> str:
    return f"""Stage 7 — Final Report

Produce the complete meeting analysis report as a single valid JSON object.
Use the following assembled analysis:

Quality notes: {quality}

Facts: {facts}

Qualification: {qualification}

Opener: {opener}

Closer: {closer}

Outcome: {outcome}

The JSON must include all required sections:
meeting_overview, executive_summary, prospect_profile, qualification_status,
qualification_criteria, opener_performance, closer_scorecard, objections,
commercial_terms, outcome, pipeline_stage, agreed_actions,
management_observations, crm_ready_notes, transcript_quality_notes.

Mark any unknown field as "unknown" or "not_assessable". Do not fabricate.
Return ONLY valid JSON."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_transcript(transcript: dict) -> str:
    lines = []
    for seg in transcript.get("segments", []):
        sid = seg.get("segment_id", "")
        speaker = seg.get("speaker_id") or "Unknown"
        start = seg.get("start_ms", 0) / 1000
        text = seg.get("text", "")
        lines.append(f"[{sid} {start:.1f}s {speaker}] {text}")
    return "\n".join(lines)


def _chunk_text(text: str, max_tokens: int) -> list[str]:
    """Rough chunking by character count (≈ 4 chars/token)."""
    max_chars = max_tokens * 4
    words = text.split()
    chunks, current = [], []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_chars and current:
            chunks.append(" ".join(current))
            current, current_len = [], 0
        current.append(word)
        current_len += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a string."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in LLM response:\n{text[:500]}")
    return json.loads(text[start:end])


# ---------------------------------------------------------------------------
# Report save
# ---------------------------------------------------------------------------

async def _save_report(
    meeting_id: str,
    report_dict: dict,
    campaign: dict,
    db: aiosqlite.Connection,
) -> None:
    # Determine next version number
    async with db.execute(
        "SELECT MAX(version) as v FROM reports WHERE meeting_id = ?", (meeting_id,)
    ) as cur:
        row = await cur.fetchone()
    version = (row["v"] or 0) + 1

    report_path = Path(settings.reports_dir) / f"{meeting_id}_v{version}.json"
    report_path.write_text(json.dumps(report_dict, indent=2))

    report_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO reports (id, meeting_id, version, campaign_config_version, file_path, status)
        VALUES (?, ?, ?, ?, ?, 'validated')
        """,
        (
            report_id,
            meeting_id,
            version,
            campaign.get("version"),
            str(report_path),
        ),
    )
    await db.commit()
    logger.info("Report v%d saved to %s", version, report_path)
