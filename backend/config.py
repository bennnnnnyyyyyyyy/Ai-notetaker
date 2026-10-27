import shutil
import ipaddress
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = False
    app_public: bool = False
    app_https: bool = False
    admin_username: str = "admin"
    admin_password_hash: str = ""
    admin_session_ttl_seconds: int = 28800
    admin_secure_cookies: bool = False

    # Database
    database_path: Path = PROJECT_ROOT / "data/app.db"

    # Data directories
    recordings_dir: Path = PROJECT_ROOT / "data/recordings"
    transcripts_dir: Path = PROJECT_ROOT / "data/transcripts"
    reports_dir: Path = PROJECT_ROOT / "data/reports"
    logs_dir: Path = PROJECT_ROOT / "data/logs"

    # Browser
    browser_profile_path: str = ""
    browser_profile_name: str = "Default"
    browser_executable_path: str = ""

    # Audio capture
    audio_device_name: str = "CABLE Output (VB-Audio Virtual Cable)"
    ffmpeg_path: str = "ffmpeg"

    # Transcription
    whisper_model: str = "base"

    # LLM
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3:mini"
    ollama_chunk_tokens: int = 3000
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: int = 120
    openrouter_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: int = 120

    # Google Sheets export
    google_sheets_spreadsheet_id: str = ""
    google_sheets_worksheet: str = "AI"
    google_sheets_service_account_path: Path = PROJECT_ROOT / "service-account.json"
    google_sheets_credentials_path: Path = PROJECT_ROOT / "credentials.json"
    google_sheets_token_path: Path = PROJECT_ROOT / "data/google_sheets_token.json"

    # Read-only Google Calendar OAuth uses a separate token and scope.
    google_calendar_credentials_path: Path = PROJECT_ROOT / "credentials.json"
    google_calendar_token_path: Path = PROJECT_ROOT / "data/google_calendar_token.json"

    # Read-only BD Meetings workbook import
    bd_meetings_workbook_path: Path = Path(r"C:\Users\ben.arthur\Desktop\BD MEETINGS 2026\BD MEETINGS 2026.xlsx")
    bd_meetings_worksheet: str = "New Meetings"

    # Optional paid adapters (empty = disabled)
    openai_api_key: str = ""
    recall_ai_api_key: str = ""

    def ensure_data_dirs(self) -> None:
        """Create all local data directories if they don't exist."""
        for d in (
            self.recordings_dir,
            self.transcripts_dir,
            self.reports_dir,
            self.logs_dir,
            self.database_path.parent,
        ):
            Path(d).mkdir(parents=True, exist_ok=True)

    def validate_security_config(self) -> None:
        """Fail closed before a non-loopback deployment can start insecurely."""
        try:
            is_loopback = ipaddress.ip_address(self.app_host).is_loopback
        except ValueError:
            is_loopback = self.app_host.lower() in {"localhost", "localhost.localdomain"}
        if not is_loopback and not self.app_public:
            raise RuntimeError("Non-loopback APP_HOST requires APP_PUBLIC=true and an explicit HTTPS deployment.")
        if self.app_public and (not self.app_https or not self.admin_secure_cookies):
            raise RuntimeError("Public deployment requires APP_HTTPS=true and ADMIN_SECURE_COOKIES=true.")

    def resolve_ffmpeg_path(self) -> str | None:
        """Resolve a full FFmpeg build; Playwright's helper lacks DirectShow."""
        configured = Path(self.ffmpeg_path)
        if configured.is_file():
            return str(configured)
        discovered = shutil.which(self.ffmpeg_path)
        if discovered:
            return discovered
        # Convenient no-admin fallback for a user-local Gyan ZIP install.
        user_local_candidates = sorted(
            (Path.home() / "ffmpeg").glob("**/bin/ffmpeg.exe"),
            reverse=True,
        )
        if user_local_candidates:
            return str(user_local_candidates[0])
        return None

    def resolve_browser_executable_path(self) -> str | None:
        """Prefer the installed Chrome that owns the configured profile."""
        configured = Path(self.browser_executable_path)
        if configured.is_file():
            return str(configured)
        candidates = (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None

    def resolve_google_calendar_credentials_path(self) -> Path:
        """Use the configured OAuth file, then an existing Sheets/client-secret file."""
        candidates = [
            Path(self.google_calendar_credentials_path),
            Path(self.google_sheets_credentials_path),
        ]
        for candidate in candidates[:2]:
            if candidate.is_file():
                return candidate
        discovered = sorted(PROJECT_ROOT.glob("client_secret*.json"))
        return discovered[0] if discovered else Path(self.google_calendar_credentials_path)


settings = Settings()
