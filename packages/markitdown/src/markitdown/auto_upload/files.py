from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import shutil


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    timestamp = _timestamp()
    candidate = path.with_name(f"{path.stem}-{timestamp}{path.suffix}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{timestamp}-{counter}{path.suffix}")
        counter += 1
    return candidate


def move_with_collision_handling(source: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_path(destination_dir / source.name)
    shutil.move(str(source), str(destination))
    return destination


async def wait_for_stable_file(
    path: Path,
    stable_seconds: float,
    poll_interval: float = 0.5,
) -> bool:
    while True:
        if not path.exists() or not path.is_file():
            return False

        first_stat = path.stat()
        await asyncio.sleep(stable_seconds)

        if not path.exists() or not path.is_file():
            return False

        second_stat = path.stat()
        if (
            first_stat.st_size == second_stat.st_size
            and first_stat.st_mtime_ns == second_stat.st_mtime_ns
        ):
            return True

        await asyncio.sleep(poll_interval)
