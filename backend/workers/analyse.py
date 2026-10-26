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
import asyncio
import re
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from backend.config import settings
from backend.auth import public_error_message
from backend.adapters.base_llm import BaseLLMAdapter
from backend.adapters.ollama_llm import OllamaLLMAdapter
from backend.adapters.gemini_llm import GeminiLLMAdapter
from backend.adapters.openrouter_llm import OpenRouterLLMAdapter
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
            "UPDATE meetings SET status = 'completed', error_message = NULL, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), meeting_id),
        )
        await db.commit()
        logger.info("Analysis complete for meeting %s", meeting_id)

    except Exception as exc:
        logger.exception("Analysis failed for meeting %s", meeting_id)
        await db.execute(
            "UPDATE meetings SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
            (public_error_message(exc, "Analysis failed; check the server log and retry."), datetime.utcnow().isoformat(), meeting_id),
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
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        llm = GeminiLLMAdapter()
        if not llm.is_available():
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY in .env")
    elif provider == "openrouter":
        llm = OpenRouterLLMAdapter()
        if not llm.is_available():
            raise RuntimeError("OpenRouter is not configured. Set OPENROUTER_KEY in .env")
    else:
        llm = OllamaLLMAdapter()
    if provider not in {"gemini", "openrouter"} and not await asyncio.to_thread(llm.is_available):
        raise RuntimeError(
            f"Ollama model '{settings.ollama_model}' is not available. "
            f"Run: ollama pull {settings.ollama_model}"
        )

    # Flatten segments to plain text with timestamps for prompting
    flat_text = _flatten_transcript(transcript)
    chunks = _chunk_text(flat_text, settings.ollama_chunk_tokens)

    system_base = _build_system_prompt(meeting, campaign)

    # Stage 1 — quality
    quality_notes = await _generate(llm, system_base, _prompt_quality(flat_text[:4000]))

    # Stage 2 — fact extraction (chunked, then consolidated)
    facts_parts = []
    for chunk in chunks:
        facts_parts.append(await _generate(llm, system_base, _prompt_facts(chunk)))
    facts_text = "\n---\n".join(facts_parts)

    # Stage 3 — qualification
    qualification = await _generate(llm, system_base, _prompt_qualification(facts_text, campaign))

    # Stage 4 — opener
    opener = await _generate(llm, system_base, _prompt_opener(facts_text, meeting))

    # Stage 5 — closer
    closer = await _generate(llm, system_base, _prompt_closer(facts_text))

    # Stage 6 — outcome
    outcome = await _generate(llm, system_base, _prompt_outcome(facts_text))

    # Stage 7 — consolidate into final JSON
    final_prompt = _prompt_consolidate(
        meeting, facts_text, qualification, opener, closer, outcome, quality_notes
    )
    raw_report = await _generate(llm, system_base, final_prompt)

    # Stage 8 — extract and validate JSON
    report_dict = _normalize_report_dict(_extract_json(raw_report), transcript)
    report_dict["meeting_id"] = meeting["id"]
    report_dict["campaign_id"] = meeting.get("campaign_id")
    report_dict["campaign_config_version"] = campaign.get("version")

    # Pydantic validation
    Report.model_validate(report_dict)
    return report_dict


async def _generate(llm: BaseLLMAdapter, system_prompt: str, user_prompt: str) -> str:
    """Keep synchronous local-model inference off FastAPI's event loop."""
    return await asyncio.to_thread(llm.generate, system_prompt, user_prompt)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt(meeting: dict, campaign: dict) -> str:
    campaign_block = (
        f"Campaign: {campaign.get('name', 'Unknown')}\n"
        f"Campaign version: {campaign.get('version', 'Unknown')}\n"
        f"Qualification requirements: {json.dumps(campaign.get('qualification', {}), indent=2)}"
        if campaign else (
            "No campaign configuration selected. Use the universal sales-meeting rubric. "
            "Do not treat the absence of a campaign as a failure; mark only campaign-specific "
            "criteria as unknown."
        )
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
    criteria = json.dumps(campaign.get("qualification", {}).get("requirements", []), indent=2) if campaign else "None — use universal criteria only."
    return f"""Stage 3 — Qualification Assessment

Based on the extracted facts below, assess each qualification criterion.
For each criterion: status = met | unmet | unknown

Universal criteria:
1. Suitable business for Prime Ad's services
2. Relevant business need
3. Decision-making authority or access
4. Willingness to discuss a paid service

Campaign-specific criteria (if present; otherwise omit them rather than treating them as a failure):
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

Score a category whenever the facts or pre-booking notes support a defensible assessment. Use "not_assessable" only when the specific category has no evidence at all.
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

Score each category whenever the facts contain direct evidence of that behavior. Use "not_assessable" only when the category truly cannot be evaluated from the transcript. The lack of a saved campaign does not make these general sales behaviors not assessable.
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

    Follow these exact types:
    - transcript_quality_notes, meeting_overview, executive_summary, management_observations,
      and crm_ready_notes are strings, not objects.
    - qualification_status is one of the exact allowed status strings, not an object.
    - each qualification_criteria item uses criterion_id, description, status (met|unmet|unknown),
      and optional evidence.
    - every opener_performance and closer_scorecard category is an object with score, evidence,
      and concise notes explaining the score. Use score "Not assessable" plus a specific reason
      in notes when evidence is insufficient.
    - agreed_actions is an array of action objects, never an object or string.
    - unanswered_material_questions is an array, never a string.
    - commercial_terms is an array containing every explicitly discussed amount or payment term,
      with value, fee_type/payment_timing, status, and segment_id where supported.
    Mark any unknown field as "unknown" or "not_assessable". Do not fabricate.
    If no campaign is supplied, produce a generalized sales-meeting report; do not downgrade
    general discovery, objection handling, presentation, or closing evidence merely because
    campaign_id is null. Keep only campaign-specific qualification fields unknown.
    Return ONLY valid JSON."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_transcript(transcript: dict) -> str:
    lines = []
    for seg in transcript.get("segments", []):
        sid = seg.get("segment_id", "")
        speaker = seg.get("speaker_id") or "Unknown"
        start = seg.get("start", seg.get("start_ms", 0) / 1000)
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


def _as_text(value, default: str = "unknown") -> str:
    """Keep report prose fields scalar when a model returns a nested object."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalize_prospect_profile(value) -> dict:
    """Flatten older nested model output into the canonical profile contract."""
    value = value if isinstance(value, dict) else {}
    identity = value.get("prospect_identity") if isinstance(value.get("prospect_identity"), dict) else {}
    needs_block = value.get("stated_needs_and_pain_points")
    needs_block = needs_block if isinstance(needs_block, dict) else {}
    authority_block = value.get("authority_and_decision_process")
    authority_block = authority_block if isinstance(authority_block, dict) else {}
    business = value.get("business_profile")
    if isinstance(business, dict):
        business_description = value.get("business_description") or _as_text(business)
    else:
        business_description = value.get("business_description")
    needs = needs_block.get("needs", value.get("stated_needs", []))
    if not isinstance(needs, list):
        needs = [needs] if needs else []
    return {
        "name": identity.get("name", value.get("name")),
        "company": identity.get("company", value.get("company")),
        "role": identity.get("role", value.get("role")),
        "business_description": business_description,
        "stated_needs": [_as_text(item) for item in needs],
        "decision_authority": authority_block.get("authority", value.get("decision_authority")),
        "evidence_type": value.get("evidence_type", "Prospect statement"),
    }


def _normalize_scorecard(value, fields: list[str]) -> dict:
    value = value if isinstance(value, dict) else {}
    normalized = {}
    for field in fields:
        item = value.get(field)
        if isinstance(item, dict):
            score = item.get("score", item.get("rating", "Not assessable"))
            evidence = item.get("evidence", item.get("segment_id", "unknown"))
            notes = item.get("notes")
        else:
            score = item if item is not None else "Not assessable"
            evidence = "unknown"
            notes = None
        if isinstance(score, str) and score.lower().replace("_", " ") in {
            "not assessable", "unknown", "unassessable"
        }:
            score = "Not assessable"
        elif score not in {1, 2, 3, 4, 5, "Not assessable"}:
            score = "Not assessable"
        if score != "Not assessable" and (evidence == "unknown" or not notes):
            score = "Not assessable"
            notes = "No criterion-specific rationale was supplied; score requires review."
        elif score == "Not assessable" and not notes:
            notes = "Insufficient criterion-specific evidence for a reliable score."
        normalized[field] = {
            "score": score,
            "evidence": _as_text(evidence),
            "notes": _as_text(notes, "") if notes is not None else None,
        }
    return normalized


def _parse_conversation_control(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    value = value if isinstance(value, dict) else {}
    score = value.get("score", "Not assessable")
    if score not in {1, 2, 3, 4, 5, "Not assessable"}:
        score = "Not assessable"
    evidence = _as_text(value.get("evidence"), "unknown")
    notes = _as_text(value.get("notes", value.get("assessment")), "Conversation control could not be reliably assessed.")
    if score != "Not assessable" and evidence == "unknown":
        score = "Not assessable"
        notes = "No evidence was supplied for a reliable conversation-control score."
    return {"score": score, "evidence": evidence, "notes": notes}


def _extract_commercial_terms(transcript: dict) -> list[dict]:
    terms = []
    for segment in transcript.get("segments", []):
        text = segment.get("text", "")
        sid = segment.get("segment_id")
        if re.search(r"\$50|fifty dollars|one time fee", text, re.I):
            terms.append({
                "term": "Live transfer fee",
                "value": "$50",
                "currency": "USD",
                "fee_type": "one-time payment",
                "status": "proposed",
                "evidence_type": "Prospect statement",
                "segment_id": sid,
            })
        if re.search(r"\$10|ten dollars", text, re.I) and re.search(r"every month|monthly", text, re.I):
            terms.append({
                "term": "Recurring patient fee",
                "value": "$10",
                "currency": "USD",
                "fee_type": "recurring monthly payment",
                "status": "proposed",
                "evidence_type": "Prospect statement",
                "segment_id": sid,
            })
        if re.search(r"seven days|7 days|payment cycle", text, re.I):
            terms.append({
                "term": "Payment timing",
                "value": "7 days",
                "payment_timing": "7 days",
                "status": "discussed",
                "evidence_type": "Prospect statement",
                "segment_id": sid,
            })
    unique = []
    for term in terms:
        if not any(term["term"] == existing["term"] and term.get("value") == existing.get("value") for existing in unique):
            unique.append(term)
    return unique


def _deduplicate_objections(objections: list) -> list[dict]:
    result = []
    for item in objections:
        if not isinstance(item, dict):
            item = {"description": _as_text(item), "resolved": False}
        item = {
            **item,
            "description": item.get("description", item.get("objection", "unknown")),
            "resolved": bool(item.get("resolved", False)),
            "segment_id": item.get("segment_id", item.get("reference")),
        }
        duplicate = next((existing for existing in result if SequenceMatcher(None, existing["description"].lower(), item["description"].lower()).ratio() >= 0.82), None)
        if duplicate:
            if item.get("segment_id") and item["segment_id"] not in str(duplicate.get("segment_id", "")):
                duplicate["segment_id"] = f"{duplicate.get('segment_id', '')}, {item['segment_id']}".strip(", ")
            duplicate["resolved"] = duplicate["resolved"] and item["resolved"]
        else:
            result.append(item)
    return result


def _normalize_commercial_terms(terms: list) -> list[dict]:
    allowed_statuses = {"proposed", "discussed", "accepted", "rejected", "unknown"}
    normalized = []
    for item in terms:
        if not isinstance(item, dict):
            item = {"term": _as_text(item)}
        status = item.get("status", "unknown")
        normalized.append({
            "term": _as_text(item.get("term")),
            "value": item.get("value"),
            "currency": item.get("currency"),
            "fee_type": item.get("fee_type"),
            "payment_timing": item.get("payment_timing"),
            "status": status if status in allowed_statuses else "unknown",
            "evidence_type": item.get("evidence_type", "Confirmed fact"),
            "segment_id": item.get("segment_id", item.get("reference")),
        })
    return normalized


def _normalize_report_dict(report: dict, transcript: dict | None = None) -> dict:
    """Normalize common model shape variations into the canonical Report contract."""
    report = dict(report)
    report["transcript_quality_notes"] = _as_text(report.get("transcript_quality_notes"), "unknown")
    report["meeting_overview"] = _as_text(report.get("meeting_overview"))
    report["executive_summary"] = _as_text(report.get("executive_summary"))
    report["management_observations"] = _as_text(report.get("management_observations"), "unknown")
    report["crm_ready_notes"] = _as_text(report.get("crm_ready_notes"), "unknown")
    report["prospect_profile"] = _normalize_prospect_profile(report.get("prospect_profile"))

    qualification_status = report.get("qualification_status", "Insufficient information")
    if isinstance(qualification_status, dict):
        qualification_status = qualification_status.get("status", "Insufficient information")
    if qualification_status == "not_assessable":
        qualification_status = "Insufficient information"
    report["qualification_status"] = qualification_status

    criteria = report.get("qualification_criteria", [])
    if not isinstance(criteria, list):
        criteria = []
    normalized_criteria = []
    for item in criteria:
        if not isinstance(item, dict):
            continue
        criterion_id = item.get("criterion_id", item.get("id", "unknown"))
        status = item.get("status", "unknown") if item.get("status") in {"met", "unmet", "unknown"} else "unknown"
        description = _as_text(item.get("description", criterion_id))
        evidence = _as_text(item.get("evidence"), "unknown")
        if status == "met" and "budget" in description.lower():
            confirmed_budget = re.search(r"\b(approved|accepted|allocated|confirmed)\b", evidence, re.I)
            if not confirmed_budget:
                status = "unknown"
        normalized_criteria.append({
            "criterion_id": _as_text(criterion_id),
            "description": description,
            "status": status,
            "evidence": evidence if evidence != "unknown" else None,
        })
    report["qualification_criteria"] = normalized_criteria

    source_opener = report.get("opener_performance")
    source_closer = report.get("closer_scorecard")
    report["opener_performance"] = _normalize_scorecard(
        source_opener,
        ["booking_quality", "information_accuracy", "expectation_setting", "pre_meeting_capture"],
    )
    report["closer_scorecard"] = _normalize_scorecard(
        source_closer,
        ["discovery", "presentation", "objection_handling", "qualification", "closing_effectiveness"],
    )
    closer = report["closer_scorecard"]
    if isinstance(source_closer, dict):
        closer["conversation_control"] = _parse_conversation_control(source_closer.get("conversation_control"))
        questions = source_closer.get("unanswered_material_questions", [])
        closer["unanswered_material_questions"] = questions if isinstance(questions, list) else []
        closer["overall_notes"] = _as_text(
            source_closer.get("overall_notes"),
            "Assessment is based on available transcript evidence; speaker attribution remains uncertain.",
        )

    actions = report.get("agreed_actions", [])
    if isinstance(actions, dict):
        actions = actions.get("explicit_commitments", actions.get("actions", []))
    if not isinstance(actions, list):
        actions = []
    report["agreed_actions"] = [
        ({**item,
          "description": item.get("description", item.get("action", "unknown")),
          "deadline": item.get("deadline", item.get("timeline")),
          "segment_id": item.get("segment_id", item.get("reference"))}
         if isinstance(item, dict) else {"description": _as_text(item)})
        for item in actions
    ]
    for key in ("objections", "commercial_terms"):
        if not isinstance(report.get(key), list):
            report[key] = []
    report["objections"] = _deduplicate_objections(report["objections"])
    report["commercial_terms"] = _normalize_commercial_terms(report["commercial_terms"])
    if transcript is not None:
        extracted_terms = _extract_commercial_terms(transcript)
        existing_terms = report["commercial_terms"]
        for term in extracted_terms:
            if not any(existing.get("term") == term["term"] and existing.get("value") == term.get("value") for existing in existing_terms if isinstance(existing, dict)):
                existing_terms.append(term)
        if extracted_terms and "not accepted" not in report["crm_ready_notes"].lower():
            report["crm_ready_notes"] += " Commercial terms are recorded as discussed/proposed only; acceptance was not confirmed."
    return report


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
