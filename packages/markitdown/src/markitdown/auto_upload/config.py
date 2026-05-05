from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AutoUploadConfig:
    input_dir: Path
    export_dir: Path
    archive_dir: Path
    error_dir: Path
    outline_base_url: str
    outline_api_token: str
    outline_collection_name: str
    file_stable_seconds: float = 3.0
    poll_interval: float = 2.0
    worker_concurrency: int = 1
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AutoUploadConfig":
        required = {
            "OUTLINE_BASE_URL": os.getenv("OUTLINE_BASE_URL"),
            "OUTLINE_API_TOKEN": os.getenv("OUTLINE_API_TOKEN"),
            "OUTLINE_COLLECTION_NAME": os.getenv("OUTLINE_COLLECTION_NAME"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            missing_names = ", ".join(sorted(missing))
            raise ValueError(f"Missing required environment variables: {missing_names}")

        return cls(
            input_dir=Path(os.getenv("INPUT_DIR", "/data/input")),
            export_dir=Path(os.getenv("EXPORT_DIR", "/data/export")),
            archive_dir=Path(os.getenv("ARCHIVE_DIR", "/data/archive")),
            error_dir=Path(os.getenv("ERROR_DIR", "/data/error")),
            outline_base_url=required["OUTLINE_BASE_URL"].rstrip("/"),
            outline_api_token=required["OUTLINE_API_TOKEN"],
            outline_collection_name=required["OUTLINE_COLLECTION_NAME"],
            file_stable_seconds=float(os.getenv("FILE_STABLE_SECONDS", "3")),
            poll_interval=float(os.getenv("POLL_INTERVAL", "2")),
            worker_concurrency=max(1, int(os.getenv("WORKER_CONCURRENCY", "1"))),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.input_dir,
            self.export_dir,
            self.archive_dir,
            self.error_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
