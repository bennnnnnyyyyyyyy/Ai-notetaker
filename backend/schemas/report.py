from pydantic import BaseModel
from typing import Optional, Literal


# ── Evidence types ────────────────────────────────────────────────────────────

EvidenceType = Literal[
    "Confirmed fact",
    "Prospect statement",
    "Prime Ad statement",
    "AI assessment",
    "Explicit commitment",
    "Unknown",
    "Unresolved",
]

QualificationStatus = Literal[
    "Confirmed fit",
    "Potential fit — unconfirmed",
    "Outside ICP",
    "Insufficient information",
]

MeetingOutcome = Literal[
    "Closed / purchase committed",
    "Qualified opportunity — second meeting booked",
    "Interested — no confirmed next meeting",
    "Follow-up required",
    "Unqualified",
    "Lost or declined",
    "Inconclusive — insufficient evidence",
]

Score = Literal[1, 2, 3, 4, 5, "Not assessable"]


# ── Sub-models ────────────────────────────────────────────────────────────────

class ScorecardCategory(BaseModel):
    score: Score
    evidence: str  # transcript segment ID or quote
    notes: Optional[str] = None


class OpenerScorecard(BaseModel):
    booking_quality: ScorecardCategory
    information_accuracy: ScorecardCategory
    expectation_setting: ScorecardCategory
    pre_meeting_capture: ScorecardCategory
    overall_notes: Optional[str] = None


class CloserScorecard(BaseModel):
    discovery: ScorecardCategory
    presentation: ScorecardCategory
    objection_handling: ScorecardCategory
    qualification: ScorecardCategory
    closing_effectiveness: ScorecardCategory
    conversation_control: Optional[str] = None
    unanswered_material_questions: list[str] = []
    overall_notes: Optional[str] = None


class QualificationCriterion(BaseModel):
    criterion_id: str
    description: str
    status: Literal["met", "unmet", "unknown"]
    evidence: Optional[str] = None


class Objection(BaseModel):
    description: str
    raised_by: Optional[str] = None
    resolved: bool
    resolution: Optional[str] = None
    evidence_type: EvidenceType = "Prospect statement"
    segment_id: Optional[str] = None


class CommercialTerm(BaseModel):
    term: str
    value: Optional[str] = None
    evidence_type: EvidenceType = "Confirmed fact"
    segment_id: Optional[str] = None


class Action(BaseModel):
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    evidence_type: EvidenceType = "Explicit commitment"
    segment_id: Optional[str] = None


class ProspectProfile(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    business_description: Optional[str] = None
    stated_needs: list[str] = []
    decision_authority: Optional[str] = None
    evidence_type: EvidenceType = "Prospect statement"


# ── Top-level report ──────────────────────────────────────────────────────────

class Report(BaseModel):
    meeting_id: str
    campaign_id: Optional[str]
    campaign_config_version: Optional[str]
    schema_version: str = "1.0"

    # Stage 1 – quality
    transcript_quality_notes: Optional[str] = None

    # Stage 2 – facts
    meeting_overview: str
    executive_summary: str
    prospect_profile: ProspectProfile

    # Stage 3 – qualification
    qualification_status: QualificationStatus
    qualification_criteria: list[QualificationCriterion] = []

    # Stage 4 – opener
    opener_performance: OpenerScorecard

    # Stage 5 – closer
    closer_scorecard: CloserScorecard

    # Stage 6 – outcome
    outcome: MeetingOutcome
    pipeline_stage: Optional[str] = None

    # Supporting fields
    objections: list[Objection] = []
    commercial_terms: list[CommercialTerm] = []
    agreed_actions: list[Action] = []
    management_observations: Optional[str] = None
    crm_ready_notes: Optional[str] = None


class ReportResponse(BaseModel):
    id: str
    meeting_id: str
    version: int
    status: str
    created_at: str
    report: Optional[Report] = None


class ReportReviewCreate(BaseModel):
    reviewer: str
    feedback: Optional[str] = None
    corrections: Optional[dict] = None
