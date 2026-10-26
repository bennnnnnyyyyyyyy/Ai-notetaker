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
        launch_args: list[str] = [
            "--use-fake-ui-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
        ]

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
        async def _navigate_and_join():
            try:
                await self._page.goto(meeting_url, wait_until="commit", timeout=60_000)
                logger.info("Meet navigation committed: url=%s", self._page.url)
                await self._auto_join()
            except PlaywrightError as exc:
                logger.warning("Meet navigation or join error: %s", exc)

        asyncio.create_task(_navigate_and_join())
        await asyncio.sleep(3)
        logger.info("Navigation fired; current tab url=%s", self._page.url)

        # Detect an invalid device or an FFmpeg startup failure immediately.
        await asyncio.sleep(0.5)
        if self._process.poll() is not None:
            self._status = "failed"
            raise RuntimeError(
                "FFmpeg exited before recording started. Check FFMPEG_PATH and AUDIO_DEVICE_NAME."
            )

        return str(output_path)

    async def _auto_join(self) -> None:
        """Automate Google Meet pre-join dialogs and join button clicking."""
        page = self._page
        if not page:
            return

        logger.info("Starting automated Google Meet join flow...")
        for _ in range(45):
            if page.is_closed():
                self._status = "meeting_ended"
                return

            try:
                # 1. Handle in-page mic dialog ("Do you want people to hear you in the meeting?")
                for text in ["Continue without microphone", "Dismiss", "Use microphone"]:
                    locator = page.locator(f"button:has-text('{text}'), [role='button']:has-text('{text}')")
                    if await locator.count() > 0 and await locator.first.is_visible():
                        logger.info("Dismissing mic prompt with: %s", text)
                        await locator.first.click()
                        await asyncio.sleep(1)
                        break

                # 2. Check if already inside the call room
                leave_btn = page.locator('[aria-label*="Leave call"], [aria-label*="End call"]')
                if await leave_btn.count() > 0 and await leave_btn.first.is_visible():
                    logger.info("Detected in-call room.")
                    self._status = "recording"
                    return

                # 3. Check for denied admission
                denied = page.locator("text='You can\\'t join this call', text='Someone denied your request', text='You can\\'t join this video call'")
                if await denied.count() > 0 and await denied.first.is_visible():
                    logger.warning("Google Meet admission denied.")
                    self._status = "failed"
                    return

                # 4. Check for waiting-room state
                waiting = page.locator("text='Asking to join', text='Waiting to be let in', text='You\\'ll join the call when someone lets you in'")
                if await waiting.count() > 0 and await waiting.first.is_visible():
                    logger.info("Currently in waiting room (waiting for admission)...")
                    self._status = "waiting_for_admission"
                    await asyncio.sleep(2)
                    continue

                # 5. Look for Join button: "Join now" or "Ask to join"
                join_now = page.locator('button:has-text("Join now"), [role="button"]:has-text("Join now")')
                ask_join = page.locator('button:has-text("Ask to join"), [role="button"]:has-text("Ask to join")')

                if await join_now.count() > 0 and await join_now.first.is_visible():
                    # Turn off mic and camera (silent observer note-taker)
                    try:
                        await page.keyboard.press("Control+d")
                        await page.keyboard.press("Control+e")
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
                    logger.info("Clicking 'Join now'...")
                    await join_now.first.click()
                    self._status = "recording"
                    await asyncio.sleep(2)
                    return
                elif await ask_join.count() > 0 and await ask_join.first.is_visible():
                    try:
                        await page.keyboard.press("Control+d")
                        await page.keyboard.press("Control+e")
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
                    logger.info("Clicking 'Ask to join'...")
                    await ask_join.first.click()
                    self._status = "waiting_for_admission"
                    await asyncio.sleep(2)
                    continue

            except Exception as exc:
                logger.debug("Join step check error: %s", exc)

            await asyncio.sleep(1)

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
        if self._page and self._page.is_closed():
            self._status = "meeting_ended"
            return self._status

        if self._browser:
            try:
                pages = getattr(self._browser, "pages", None)
                pages_list = pages() if callable(pages) else pages
                if pages_list is not None and len(pages_list) == 0:
                    self._status = "meeting_ended"
                    return self._status
            except Exception:
                pass

        if self._page and not self._page.is_closed():
            try:
                # If waiting for admission, check if admitted or denied
                if self._status == "waiting_for_admission":
                    leave_btn = self._page.locator('[aria-label*="Leave call"], [aria-label*="End call"]')
                    if await leave_btn.count() > 0 and await leave_btn.first.is_visible():
                        logger.info("Admitted to Google Meet call room!")
                        self._status = "recording"
                    denied = self._page.locator("text='You can\\'t join this call', text='Someone denied your request', text='You can\\'t join this video call'")
                    if await denied.count() > 0 and await denied.first.is_visible():
                        logger.warning("Google Meet admission denied.")
                        self._status = "failed"

                # If recording, check if meeting ended on screen
                elif self._status == "recording":
                    ended = self._page.locator("text='You left the meeting', text='You\\'ve left the meeting', text='Everyone else left', text='Return to home screen'")
                    if await ended.count() > 0 and await ended.first.is_visible():
                        logger.info("Detected meeting ended on screen.")
                        self._status = "meeting_ended"
            except Exception:
                pass

        return self._status
