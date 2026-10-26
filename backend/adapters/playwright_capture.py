"""
Playwright + FFmpeg capture adapter.

Milestone 1 implementation:
  - Launches a visible Chrome browser using the user's existing profile.
  - Navigates to the Google Meet URL.
  - Starts FFmpeg DirectShow audio recording in a subprocess.
  - Monitors the browser for meeting end or admission failure.
  - Stops FFmpeg and returns the recording path.

Prerequisites (checked at runtime):
  - VB-Audio Virtual Cable or Stereo Mix enabled in Windows Sound settings.
  - FFmpeg available at settings.ffmpeg_path.
  - A Chrome profile with an active Google session at settings.browser_profile_path.
"""

import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page, Error as PlaywrightError

from backend.adapters.base_capture import BaseCaptureAdapter
from backend.config import settings

logger = logging.getLogger(__name__)


class PlaywrightCaptureAdapter(BaseCaptureAdapter):

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._page: Optional[Page] = None
        self._recording_path: Optional[Path] = None
        self._ffmpeg_log_handle = None
        self._status: str = "idle"

    async def start(self, meeting_url: str, meeting_id: str) -> str:
        self._status = "joining"
        output_path = Path(settings.recordings_dir) / f"{meeting_id}.wav"
        self._recording_path = output_path

        # ── Start FFmpeg loopback recording ───────────────────────────────
        ffmpeg_path = settings.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self._status = "failed"
            raise RuntimeError(
                f"FFmpeg not found at '{settings.ffmpeg_path}'. "
                "Install FFmpeg and set FFMPEG_PATH in .env."
            )
        ffmpeg_cmd = [
            ffmpeg_path,
            "-y",
            "-f", "dshow",
            "-i", f"audio={settings.audio_device_name}",
            "-ar", "16000",
            "-ac", "1",
            str(output_path),
        ]
        ffmpeg_log_path = Path(settings.logs_dir) / f"{meeting_id}.ffmpeg.log"
        self._ffmpeg_log_handle = ffmpeg_log_path.open("w", encoding="utf-8")
        logger.info("Starting FFmpeg: %s", " ".join(ffmpeg_cmd))
        try:
            self._process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._ffmpeg_log_handle,
            )
        except FileNotFoundError as exc:
            self._status = "failed"
            raise RuntimeError(
                f"FFmpeg not found at '{settings.ffmpeg_path}'. "
                "Install FFmpeg and set FFMPEG_PATH in .env."
            ) from exc

        # ── Launch browser and join meeting ───────────────────────────────
        self._playwright = await async_playwright().start()
        # Do not bypass Google Meet's permission or consent prompts. The user
        # must approve microphone/camera access in the visible browser.
        launch_args: list[str] = []

        browser_args: dict = {
            "headless": False,
            "args": launch_args,
        }
        browser_executable = settings.resolve_browser_executable_path()
        if browser_executable:
            browser_args["executable_path"] = browser_executable
        try:
            if settings.browser_profile_path:
                # Use the existing signed-in Chrome profile. Chrome must be
                # closed first because its profile lock cannot be shared.
                launch_args.append(f"--profile-directory={settings.browser_profile_name}")
                persistent_args = {
                    "user_data_dir": settings.browser_profile_path,
                    "headless": False,
                    "args": launch_args,
                }
                if browser_executable:
                    persistent_args["executable_path"] = browser_executable
                self._browser = await self._playwright.chromium.launch_persistent_context(**persistent_args)
                # Chrome may expose a startup/restore tab as about:blank. Do
                # not reuse it: create a dedicated capture tab so navigation
                # is deterministic and the meeting URL is visible to the user.
                existing_pages = list(self._browser.pages)
                self._page = await self._browser.new_page()
                for page in existing_pages:
                    if page.url in {"about:blank", "chrome://newtab/"}:
                        try:
                            await page.close()
                        except PlaywrightError:
                            pass
            else:
                self._browser = await self._playwright.chromium.launch(**browser_args)
                self._page = await self._browser.new_page()
        except PlaywrightError as exc:
            self._status = "failed"
            raise RuntimeError(
                "Chrome profile could not be opened. Close every Chrome window, "
                "wait a few seconds, and retry the capture."
            ) from exc

        logger.info("Navigating capture tab to %s", meeting_url)
        # Fire navigation as a background task so we are not blocked waiting
        # for Google Meet's auth redirects or slow application-shell load.
        # Chrome will continue loading the URL visibly; the user joins manually.
        async def _navigate():
            try:
                await self._page.goto(meeting_url, wait_until="commit", timeout=60_000)
                logger.info("Meet navigation committed: url=%s", self._page.url)
            except PlaywrightError as exc:
                logger.warning("Meet navigation error (non-fatal, browser still open): %s", exc)

        asyncio.create_task(_navigate())
        # Give Chrome a moment to pick up the navigation request before we
        # check FFmpeg health and return. The tab will load in the background.
        await asyncio.sleep(3)
        logger.info("Navigation fired; current tab url=%s", self._page.url)

        # Detect an invalid device or an FFmpeg startup failure immediately.
        await asyncio.sleep(0.5)
        if self._process.poll() is not None:
            self._status = "failed"
            raise RuntimeError(
                "FFmpeg exited before recording started. Check FFMPEG_PATH and AUDIO_DEVICE_NAME."
            )

        # Give the page time to settle; actual join logic is handled in the worker
        self._status = "recording"
        return str(output_path)

    async def stop(self) -> float:
        duration = 0.0

        if self._process and self._process.poll() is None:
            logger.info("Stopping FFmpeg recording")
            try:
                self._process.stdin.write(b"q")
                self._process.stdin.flush()
                self._process.wait(timeout=10)
            except Exception:
                self._process.kill()

            # Estimate duration from file size (16 kHz, 16-bit mono = 32 kB/s)
            if self._recording_path and self._recording_path.exists():
                size_bytes = self._recording_path.stat().st_size
                duration = size_bytes / 32_000

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        if self._ffmpeg_log_handle:
            try:
                self._ffmpeg_log_handle.close()
            except Exception:
                pass
            self._ffmpeg_log_handle = None

        self._status = "meeting_ended"
        return duration

    async def get_status(self) -> str:
        if self._status == "recording":
            if self._page and self._page.is_closed():
                self._status = "meeting_ended"
            elif self._browser and not self._browser.is_connected():
                self._status = "meeting_ended"
        return self._status
