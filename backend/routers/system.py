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

