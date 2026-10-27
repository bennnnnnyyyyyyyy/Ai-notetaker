"""Authorize read-only Google Calendar access once on this PC."""

import sys
from pathlib import Path

# Running ``py -3 scripts/google_calendar_auth.py`` puts scripts/ on sys.path,
# not the repository root where the backend package lives.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.adapters.google_calendar import CALENDAR_READONLY_SCOPE
from backend.config import settings


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = settings.resolve_google_calendar_credentials_path()
    if not credentials_path.is_file():
        raise SystemExit(f"Missing {credentials_path}. Download a Google OAuth Desktop credential first.")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), [CALENDAR_READONLY_SCOPE])
    creds = flow.run_local_server(port=0)
    token_path = Path(settings.google_calendar_token_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Google Calendar authorization saved to {token_path}")


if __name__ == "__main__":
    main()
