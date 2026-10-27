"""Authorize read-only access to the shared BD Meetings Google Sheet."""

from pathlib import Path

from backend.config import settings

BD_SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = settings.resolve_bd_meetings_credentials_path()
    if not credentials_path.is_file():
        raise SystemExit(f"Missing {credentials_path}. Download a Google OAuth Desktop credential first.")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), [BD_SHEETS_READONLY_SCOPE])
    creds = flow.run_local_server(port=0)
    token_path = Path(settings.bd_meetings_token_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"BD Google Sheet read-only authorization saved to {token_path}")


if __name__ == "__main__":
    main()
