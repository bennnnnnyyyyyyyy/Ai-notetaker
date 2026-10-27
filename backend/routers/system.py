import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.diagnostics import get_readiness
from backend.config import settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/readiness")
async def readiness():
    """Report local capture prerequisites without starting a capture."""
    return await get_readiness()


@router.get("/status")
async def system_status():
    """Return safe local configuration status for the authenticated Settings view."""
    return {
        "host": settings.app_host,
        "public_access": settings.app_public,
        "https_enabled": settings.app_https,
        "scheduled_capture_enabled": settings.scheduled_capture_enabled,
        "scheduled_capture_poll_seconds": settings.scheduled_capture_poll_seconds,
        "browser_profile_configured": bool(settings.browser_profile_path),
        "browser_profile_name": settings.browser_profile_name,
        "audio_device_name": settings.audio_device_name,
        "ffmpeg_configured": bool(settings.resolve_ffmpeg_path()),
        "calendar_credentials_configured": settings.resolve_google_calendar_credentials_path().is_file(),
        "calendar_token_configured": Path(settings.google_calendar_token_path).is_file(),
        "bd_sheet_configured": bool(settings.bd_meetings_spreadsheet_id),
        "bd_sheet_token_configured": Path(settings.bd_meetings_token_path).is_file(),
    }


@router.post("/setup-browser")
async def setup_browser():
    """
    Open Chrome with the dedicated capture profile so the user can sign into
    Google once.  Close the browser when done; then refresh readiness.
    Fire-and-forget: the browser stays open for the user.
    """
    profile_dir = Path(settings.browser_profile_path)
    profile_dir.mkdir(parents=True, exist_ok=True)

    chrome_exe = settings.resolve_browser_executable_path()
    if not chrome_exe:
        raise HTTPException(status_code=500, detail="Google Chrome not found on this PC.")

    cmd = [
        chrome_exe,
        f"--user-data-dir={profile_dir}",
        f"--profile-directory={settings.browser_profile_name}",
        "https://accounts.google.com",
    ]
    # Launch detached so the server is not blocked.
    await asyncio.to_thread(
        lambda: __import__("subprocess").Popen(cmd)
    )
    return {
        "status": "launched",
        "detail": (
            "Chrome has opened with the capture profile. "
            "Sign into your Google account, then close this Chrome window. "
            "Click 'Refresh' on the dashboard to confirm readiness."
        ),
    }
