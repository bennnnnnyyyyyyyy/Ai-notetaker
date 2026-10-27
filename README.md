# AI Notetaker

Local-first meeting capture and analysis for authorized Google Meet sessions.

## Start here

1. Read [`AGENTS.md`](AGENTS.md).
2. Read the [documentation index](documentation/README.md).
3. Read the [current architecture](documentation/architecture/ARCHITECTURE.md).
4. Check the [master plan](documentation/plans/MASTER_PLAN.md) and [worklog](documentation/operations/WORKLOG.md).

## Current implementation

- `backend/` — FastAPI API, SQLite persistence, capture/transcription/analysis adapters.
- `frontend/` — static local dashboard served by FastAPI.
- `data/` — ignored runtime data: database, recordings, transcripts, reports, and logs.
- `ARCHITECTURE.md`, `MAIN.md`, and `dump.md` — original design material retained as reference while the organized documentation is maintained.

## Local run

```powershell
py -3 -m uvicorn backend.main:app
```

Open `http://127.0.0.1:8000`.

The project is still a prototype. A real capture test requires a visible browser, an authorized signed-in session, explicit consent, FFmpeg, and a working Stereo Mix or VB-Audio device.

## Architecture and data flow

The application is local-first. The FastAPI process runs on this Windows PC and serves both the authenticated dashboard and the local API. Runtime records, recordings, transcripts, reports, OAuth tokens, and the SQLite database stay under the ignored `data/` directory.

```text
Shared Google Sheet (read-only API)             Google Calendar (read-only API)
        │                                                   │
        │ New Meetings row + Calendar event URL              │ events.get by decoded event ID
        ▼                                                   ▼
backend/adapters/bd_meetings.py       backend/adapters/google_calendar.py
        │                                                   │
        └────────────── operator review + confirmation ─────┘
                                │
                                ▼
                         local SQLite meeting
                    (Meet URL, time, campaign, event IDs)
                                │
                                ▼
        local scheduler → visible Chrome/Playwright → FFmpeg audio
                                │
                                ▼
                    local transcription → local analysis
```

### Where each piece of data comes from

- **Booking information** comes from the shared Google Sheet `1uicpBruuFeno2ES4hNw-TIAwNkGEI37gw8Z-A4yMpC8`, worksheet `New Meetings`, through the Google Sheets API with `spreadsheets.readonly`. The sheet is shared to `meetings.dmedeskai@gmail.com`; the adapter reads rows only and never writes back.
- **Calendar event identity** comes from the Google Calendar event/edit URL stored in a workbook row. The app decodes the event reference to obtain the Calendar ID and event ID. It does not scrape the Calendar web page.
- **Meeting time and Meet URL** come from the authorized Google Calendar API response. The app accepts only a genuine HTTPS `https://meet.google.com/...` video entry point or `hangoutLink`; it does not guess a URL from an event URL.
- **Campaign mapping** comes from the workbook label and existing local campaigns: `CGM`, `Roofing`, `ORT`, and `ORT+CGM` have explicit mappings. Unknown or ambiguous labels require operator selection.
- **Local meeting state** is stored in `data/app.db`. It includes the resolved Meet URL, scheduled time, campaign, Calendar ID, Calendar event ID, status, and error state. Calendar ID plus event ID prevents duplicate imports.
- **Google authentication** uses separate local OAuth tokens: `data/google_bd_sheets_token.json` for the shared BD Sheet with `spreadsheets.readonly`, and `data/google_calendar_token.json` for Calendar with `calendar.readonly`. The client files are referenced by `.env`.
- **Capture data** comes from the visible authorized Chrome profile and local FFmpeg audio capture. Transcripts and reports are produced locally by the configured processing adapters.

### Current Calendar boundary

The current integration is **booking-driven**, not a full Calendar inbox. It reads `New Meetings` rows from the shared Google Sheet, resolves a selected row's Calendar event, and requires operator confirmation before creating a local meeting. It does not currently list every event in Google Calendar automatically. Calendar events shown in Google Calendar but absent from the Sheet will not appear in the app until a separate Calendar discovery flow is added.

Importing never starts capture immediately. If the confirmed local meeting has a valid scheduled time and scheduled capture is enabled, the local scheduler opens the visible browser at that time. Google sign-in, browser permission prompts, waiting-room admission, and recording consent remain user-controlled.

### What the system does not do

- It does not scrape Google Calendar edit pages.
- It does not modify Calendar events or the BD workbook.
- It does not grant browser media permissions or bypass Google authentication/admission.
- It does not send recordings, transcripts, credentials, or tokens to a public server.
- It does not start a capture merely because an event was imported; scheduling requires the local server to remain running.
# Ai-notetaker
