import shutil
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

    # Audio capture
    audio_device_name: str = "CABLE Output (VB-Audio Virtual Cable)"
    ffmpeg_path: str = "ffmpeg"

    # Transcription
    whisper_model: str = "base"

    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3:mini"
    ollama_chunk_tokens: int = 3000

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


settings = Settings()
