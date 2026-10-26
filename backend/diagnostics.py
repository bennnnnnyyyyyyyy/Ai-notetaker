"""Read-only local environment checks for the capture proof of concept."""

from __future__ import annotations

import platform
import subprocess
from playwright.async_api import async_playwright
from pathlib import Path

from backend.config import settings


def _audio_device_check(ffmpeg: str | None) -> dict:
    if not ffmpeg:
        return {"status": "blocked", "detail": "FFmpeg is not available; audio devices cannot be enumerated."}
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "blocked", "detail": f"Could not enumerate DirectShow devices: {exc}"}

    output = f"{result.stdout}\n{result.stderr}"
    audio_lines = [
        line.strip()
        for line in output.splitlines()
        if "audio=" in line or "(audio)" in line
    ]
    configured = settings.audio_device_name
    matched = any(configured.lower() in line.lower() for line in audio_lines)
    return {
        "status": "ready" if matched else "needs_setup",
        "configured_device": configured,
        "configured_device_found": matched,
        "audio_devices": audio_lines,
        "detail": "Configured audio device found." if matched else "Configured audio device was not found.",
    }

def _browser_profile_check(profile: Path | None) -> dict:
    if not profile or not profile.is_dir():
        return {
            "status": "needs_setup",
            "detail": (
                "Capture profile not set up yet. "
                "Click 'Setup capture browser' on the dashboard to sign in once."
            ),
        }
    # Proxy for a completed Google sign-in: the Cookies file exists in Default/.
    cookies = profile / "Default" / "Cookies"
    signed_in = cookies.is_file()
    return {
        "status": "ready" if signed_in else "needs_setup",
        "profile_dir": str(profile),
        "detail": (
            "Capture profile is ready."
            if signed_in
            else "Profile folder exists but no Google session found. "
                 "Click 'Setup capture browser' to sign in."
        ),
    }

async def get_readiness() -> dict:
    """Return safe, local-only checks without starting a browser or recording."""
    ffmpeg = settings.resolve_ffmpeg_path()
    profile = Path(settings.browser_profile_path) if settings.browser_profile_path else None
    try:
        playwright = await async_playwright().start()
        chromium_path = playwright.chromium.executable_path
        await playwright.stop()
        chromium_available = Path(chromium_path).is_file()
    except Exception as exc:  # pragma: no cover - depends on local browser install
        chromium_path = None
        chromium_available = False
        chromium_error = str(exc)
    else:
        chromium_error = None

    checks = {
        "python": {"status": "ready", "version": platform.python_version()},
        "playwright_chromium": {
            "status": "ready" if chromium_available else "blocked",
            "executable": chromium_path,
            "detail": chromium_error or ("Playwright Chromium is installed." if chromium_available else "Playwright is installed, but its Chromium executable is missing. Run: py -3 -m playwright install chromium"),
        },
        "ffmpeg": {
            "status": "ready" if ffmpeg else "blocked",
            "configured_path": settings.ffmpeg_path,
            "resolved_path": ffmpeg,
            "detail": "FFmpeg is available." if ffmpeg else "Install FFmpeg or set FFMPEG_PATH to ffmpeg.exe.",
        },
        "browser_profile": _browser_profile_check(profile),
        "audio": _audio_device_check(ffmpeg),
    }
    ready = all(check["status"] == "ready" for check in checks.values())
    return {"status": "ready" if ready else "needs_setup", "checks": checks}
