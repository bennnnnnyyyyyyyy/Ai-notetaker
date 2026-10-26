from backend.schemas.report import Report
from backend.workers.analyse import _normalize_report_dict


def _report_with_legacy_shapes():
    category = {"score": 4, "evidence": "seg_0010"}
    return {
        "meeting_overview": "General discovery meeting.",
        "executive_summary": "Interest was discussed; no purchase commitment was made.",
        "prospect_profile": {
            "prospect_identity": {"company": "Example DME", "role": "Owner"},
            "stated_needs_and_pain_points": {"needs": ["More qualified leads"]},
            "authority_and_decision_process": {"authority": "Unknown"},
        },
        "qualification_status": "Potential fit — unconfirmed",
        "qualification_criteria": [{
            "id": "budget",
            "description": "Commercial alignment / budget",
            "status": "met",
            "evidence": "seg_0077: price was discussed",
        }],
        "opener_performance": {field: category for field in (
            "booking_quality", "information_accuracy", "expectation_setting", "pre_meeting_capture"
        )},
        "closer_scorecard": {
            field: category for field in (
                "discovery", "presentation", "objection_handling", "qualification", "closing_effectiveness"
            )
        } | {
            "conversation_control": '{"score": 3, "evidence": "seg_0020", "assessment": "The discussion stayed focused."}',
            "unanswered_material_questions": [],
        },
        "outcome": "Interested — no confirmed next meeting",
        "objections": [
            {"objection": "Concern about fake leads", "reference": "seg_0040", "resolved": False},
            {"description": "Concern about fake leads", "reference": "seg_0041", "resolved": False},
            {"description": "Reluctance to try ads", "reference": "seg_0042", "resolved": False},
        ],
        "commercial_terms": [],
        "agreed_actions": [{"action": "Send information", "timeline": "Later", "reference": "seg_0050"}],
    }


def _transcript():
    return {"segments": [
        {"segment_id": "seg_0077", "text": "The live transfer is fifty dollars one time."},
        {"segment_id": "seg_0080", "text": "It is ten dollars every month per patient."},
        {"segment_id": "seg_0107", "text": "The payment cycle is seven days."},
    ]}


def test_report_normalization_repairs_legacy_shapes_and_requires_score_rationale():
    report = _normalize_report_dict(_report_with_legacy_shapes(), _transcript())
    report.update({"meeting_id": "fixture", "campaign_id": None, "campaign_config_version": None})

    assert report["prospect_profile"]["company"] == "Example DME"
    assert report["qualification_criteria"][0]["status"] == "unknown"
    assert report["closer_scorecard"]["conversation_control"]["score"] == 3
    assert len(report["objections"]) == 2
    assert report["agreed_actions"][0]["segment_id"] == "seg_0050"
    assert {term["term"] for term in report["commercial_terms"]} == {
        "Live transfer fee", "Recurring patient fee", "Payment timing"
    }
    assert next(term for term in report["commercial_terms"] if term["term"] == "Recurring patient fee")["segment_id"] == "seg_0080"
    assert all(term["status"] in {"proposed", "discussed"} for term in report["commercial_terms"])
    assert "acceptance was not confirmed" in report["crm_ready_notes"]
    Report.model_validate(report)


def test_numeric_score_without_rationale_is_not_assessable():
    report = _report_with_legacy_shapes()
    report["opener_performance"]["booking_quality"] = {"score": 5, "evidence": "seg_0001"}
    normalized = _normalize_report_dict(report)
    category = normalized["opener_performance"]["booking_quality"]
    assert category["score"] == "Not assessable"
    assert "rationale" in category["notes"]


def test_old_string_conversation_control_can_still_validate_after_normalization():
    report = _normalize_report_dict(_report_with_legacy_shapes())
    report.update({"meeting_id": "fixture", "campaign_id": None, "campaign_config_version": None})
    validated = Report.model_validate(report)
    assert validated.closer_scorecard.conversation_control.score == 3
