import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import aiosqlite

from backend.database import get_db
from backend.schemas.report import ReportResponse, ReportReviewCreate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/meetings/{meeting_id}/report", response_model=ReportResponse)
async def get_report(
    meeting_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT * FROM reports WHERE meeting_id = ? ORDER BY version DESC LIMIT 1",
        (meeting_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No report found for this meeting")

    report_data = None
    if row["file_path"]:
        try:
            with open(row["file_path"]) as f:
                report_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return {
        "id": row["id"],
        "meeting_id": row["meeting_id"],
        "version": row["version"],
        "status": row["status"],
        "created_at": row["created_at"],
        "report": report_data,
    }


@router.post("/meetings/{meeting_id}/analyze", status_code=202)
async def analyze_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Start or restart the analysis pipeline for a meeting."""
    async with db.execute(
        "SELECT status FROM meetings WHERE id = ?", (meeting_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if row["status"] not in ("meeting_ended", "completed", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot analyse from status '{row['status']}'",
        )

    from backend.workers.analyse import run_analysis
    background_tasks.add_task(run_analysis, meeting_id)
    return {"detail": "Analysis started", "meeting_id": meeting_id}


@router.post("/{report_id}/review", status_code=201)
async def submit_review(
    report_id: str,
    body: ReportReviewCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT id FROM reports WHERE id = ?", (report_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    review_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO report_reviews (id, report_id, reviewer, feedback, corrections)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            review_id,
            report_id,
            body.reviewer,
            body.feedback,
            json.dumps(body.corrections) if body.corrections else None,
        ),
    )
    await db.execute(
        "UPDATE reports SET status = 'reviewed' WHERE id = ?", (report_id,)
    )
    await db.commit()
    return {"detail": "Review saved", "review_id": review_id}
