"""Authorize the local Google Sheets export once on this PC."""

from pathlib import Path

from backend.adapters.google_sheets import SCOPES
from backend.config import settings


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = Path(settings.google_sheets_credentials_path)
    if not credentials_path.is_file():
        raise SystemExit(f"Missing {credentials_path}. Download a Google OAuth Desktop credential first.")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path = Path(settings.google_sheets_token_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Google Sheets authorization saved to {token_path}")


if __name__ == "__main__":
    main()
