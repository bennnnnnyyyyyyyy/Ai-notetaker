# Capture Setup Handoff

Current state as of 2026-10-26:

- Playwright Chromium is installed.
- Full FFmpeg Essentials is installed locally and DirectShow works.
- The PC exposes `Microphone (2- Logi USB Headset)`.
- The configured `CABLE Output (VB-Audio Virtual Cable)` device is not present.
- Chrome is installed and has local profiles, but no profile is configured for this app.

## To prepare an authorized meeting test

1. Enable a legitimate loopback source in Windows sound settings, such as Stereo Mix, or install/configure VB-Audio Cable according to its documentation.
2. Re-run the dashboard readiness check and confirm the intended device appears.
3. Set `AUDIO_DEVICE_NAME` in `.env` to the exact DirectShow device name.
4. Set `BROWSER_PROFILE_PATH` to the authorized Chrome user-data directory. Do not copy cookies or credentials into the repository.
5. Start the app, register a meeting, and manually approve any browser permissions/admission prompts.
6. End the test by closing the visible meeting browser; the capture worker treats that as the local stop signal.

The first test should be short and authorized. Verify that the WAV file is playable and contains the intended audio before enabling transcription.
