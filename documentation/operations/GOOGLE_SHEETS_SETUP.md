# Google Sheets Export Setup

The first integration is a controlled export, not an autonomous CRM writer. It appends one row per manual export to a spreadsheet you choose.

## What is exported

The `Meetings` worksheet receives meeting identity/status, URL, campaign, opener/closer, prospect profile, qualification, outcome, pipeline stage, executive summary, and error information.

## One-time Google setup

1. Create or choose a Google Cloud project.
2. Enable the Google Sheets API.
3. Configure the OAuth consent screen for the intended Google account/domain.
4. Create an OAuth client of type **Desktop app**.
5. Download the JSON credential and save it at the project root as `credentials.json`.
6. Put the spreadsheet ID and worksheet name in the ignored `.env` file:

   ```text
   GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id
   GOOGLE_SHEETS_WORKSHEET=Meetings
   ```

7. Install dependencies:

   ```powershell
   py -3 -m pip install -r requirements.txt
   ```

8. Authorize the local account once:

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
