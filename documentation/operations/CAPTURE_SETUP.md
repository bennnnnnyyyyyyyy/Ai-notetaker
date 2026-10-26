# Capture Setup Handoff

Current state as of 2026-10-26:

- Playwright is installed and the adapter now prefers the installed Google Chrome executable for the configured Chrome profile.
- Full FFmpeg Essentials is installed locally and DirectShow works.
- The PC exposes `Microphone (2- Logi USB Headset)` and `CABLE Output (VB-Audio Virtual Cable)`.
- FFmpeg successfully opened the CABLE device for a one-second discard-only test.
- Chrome is installed and the authorized `Default` profile is configured for this app.

## To prepare an authorized meeting test

1. Keep the verified `CABLE Output (VB-Audio Virtual Cable)` device selected as the Windows playback/recording route for the test.
2. Re-run the dashboard readiness check before the meeting.
3. Keep `AUDIO_DEVICE_NAME` set to the exact DirectShow device name.
4. Set `BROWSER_PROFILE_PATH` to the authorized Chrome `User Data` directory and `BROWSER_PROFILE_NAME` to the profile name, usually `Default`. Do not copy cookies or credentials into the repository.
5. Close every normal Chrome window before starting capture; Chrome locks the profile while it is running. The dashboard may remain open in Edge.
6. Start the app, register a meeting, and manually approve any browser permissions/admission prompts.
7. End the test by closing the visible meeting browser; the capture worker treats that as the local stop signal.

The first test should be short and authorized. Verify that the WAV file is playable and contains the intended audio before enabling transcription.
