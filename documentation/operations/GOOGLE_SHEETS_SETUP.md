# Google Sheets Export Setup

The first integration is a controlled export, not an autonomous CRM writer. It appends one row per manual export to a spreadsheet you choose.

## What is exported

The `AI` worksheet receives one compact summary row with these columns, in order:

`DATE | CAMPAIGN | CLIENTS NAME | COMPANY NAME | OPENER | CLOSER | STATUS | SUMMARY NOTES`

Detailed evidence remains in the local report and transcript. The `STATUS` cell uses the report outcome when a report exists, otherwise the meeting status.

## Preferred setup: service account

1. In Google Cloud, enable the Google Sheets API for the project that owns the service account.
2. Create or use a Google Sheet and copy its ID from the URL. It is the value between `/d/` and `/edit`.
3. Share that Sheet with the service-account email as **Editor**:

   `test1-898@ainotetakerprimead.iam.gserviceaccount.com`

4. Keep the downloaded service-account JSON in the project directory only as a local secret. It is ignored by Git.
5. Put the local path and Sheet ID in the ignored `.env` file:

   ```text
   GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id
   GOOGLE_SHEETS_WORKSHEET=AI
   GOOGLE_SHEETS_SERVICE_ACCOUNT_PATH=C:\\path\\to\\service-account.json
   ```

No browser OAuth flow is required for this route. The Sheet must be shared with the service account or Google will reject the export.

## Optional OAuth fallback

If a service account is not desired, save an OAuth Desktop client JSON as `credentials.json`, set the OAuth paths in `.env`, and run:

```powershell
py -3 scripts\google_sheets_auth.py
```

The refresh token is stored only in `data/google_sheets_token.json`, which is Git-ignored.

## Verify setup

Check `GET /api/v1/integrations/google-sheets/status`, then manually export with:

```text
POST /api/v1/integrations/google-sheets/meetings/{meeting_id}/export
```

No automatic CRM mutations, email, booking, or meeting scheduling are included.
