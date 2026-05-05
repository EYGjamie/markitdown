# MarkItDown Outline Auto-Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker-run auto-upload service that watches an input directory, converts incoming files to Markdown with MarkItDown, uploads the result to Outline, and routes originals to archive or error folders.

**Architecture:** Add a second CLI entrypoint inside the existing `markitdown` package for the long-running worker. Keep file watching, Outline API access, and file/path handling isolated in dedicated modules, and ship the runtime with a dedicated Dockerfile plus a sample `docker-compose.yml`.

**Tech Stack:** Python 3.10+, MarkItDown Python API, `requests`, `watchdog`, `pytest`, Docker Compose

---

### Task 1: Add the failing tests for auto-upload behavior

**Files:**
- Create: `packages/markitdown/tests/test_auto_upload.py`
- Modify: `packages/markitdown/pyproject.toml`

- [ ] **Step 1: Write the failing test file**

```python
from pathlib import Path

import pytest

from markitdown.auto_upload.config import AutoUploadConfig
from markitdown.auto_upload.outline import OutlineClient
from markitdown.auto_upload.service import Processor


def test_unique_path_adds_timestamp_when_target_exists(tmp_path: Path):
    ...


def test_outline_client_resolves_collection_id_from_exact_match():
    ...


def test_outline_client_raises_when_collection_missing():
    ...


def test_processor_exports_uploads_and_archives(tmp_path: Path):
    ...


def test_processor_moves_source_to_error_when_upload_fails(tmp_path: Path):
    ...
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `PYTHONPATH=packages/markitdown/src python3 -m pytest packages/markitdown/tests/test_auto_upload.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'markitdown.auto_upload'` or missing dependency/test failures because the new service code does not exist yet.

- [ ] **Step 3: Add the service dependency needed by implementation**

```toml
[project.optional-dependencies]
service = ["watchdog"]
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `PYTHONPATH=packages/markitdown/src python3 -m pytest packages/markitdown/tests/test_auto_upload.py -q`
Expected: still FAIL because production code still does not exist.

- [ ] **Step 5: Commit the red test state**

```bash
git add packages/markitdown/tests/test_auto_upload.py packages/markitdown/pyproject.toml
git commit -m "test: add failing auto-upload service tests"
```

### Task 2: Implement the auto-upload service modules and CLI

**Files:**
- Create: `packages/markitdown/src/markitdown/auto_upload/__init__.py`
- Create: `packages/markitdown/src/markitdown/auto_upload/__main__.py`
- Create: `packages/markitdown/src/markitdown/auto_upload/config.py`
- Create: `packages/markitdown/src/markitdown/auto_upload/files.py`
- Create: `packages/markitdown/src/markitdown/auto_upload/outline.py`
- Create: `packages/markitdown/src/markitdown/auto_upload/service.py`
- Modify: `packages/markitdown/pyproject.toml`

- [ ] **Step 1: Add the package entrypoint and exports**

```python
"""Auto-upload service for MarkItDown."""

from .config import AutoUploadConfig
from .outline import OutlineClient
from .service import AutoUploadService, Processor

__all__ = [
    "AutoUploadConfig",
    "OutlineClient",
    "AutoUploadService",
    "Processor",
]
```

```toml
[project.scripts]
markitdown = "markitdown.__main__:main"
markitdown-auto-upload = "markitdown.auto_upload.__main__:main"
```

- [ ] **Step 2: Implement configuration loading**

```python
from dataclasses import dataclass
from pathlib import Path
import os


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
```

- [ ] **Step 3: Implement file helpers**

```python
def unique_path(path: Path) -> Path:
    ...


async def wait_for_stable_file(path: Path, stable_seconds: float) -> bool:
    ...


def move_with_collision_handling(source: Path, destination_dir: Path) -> Path:
    ...
```

- [ ] **Step 4: Implement the Outline API client**

```python
class OutlineClient:
    def resolve_collection_id(self) -> str:
        ...

    def create_document(self, *, title: str, markdown: str, collection_id: str) -> dict:
        ...
```

- [ ] **Step 5: Implement the processor and watcher-backed service**

```python
class Processor:
    def process_file(self, source_path: Path) -> ProcessResult:
        ...


class AutoUploadService:
    async def run(self) -> None:
        ...
```

- [ ] **Step 6: Implement the CLI main**

```python
def main() -> None:
    config = AutoUploadConfig.from_env()
    service = AutoUploadService.from_config(config)
    asyncio.run(service.run())
```

- [ ] **Step 7: Run the targeted tests to verify they pass**

Run: `PYTHONPATH=packages/markitdown/src python3 -m pytest packages/markitdown/tests/test_auto_upload.py -q`
Expected: PASS

- [ ] **Step 8: Commit the service implementation**

```bash
git add packages/markitdown/src/markitdown/auto_upload packages/markitdown/pyproject.toml
git commit -m "feat: add outline auto-upload service"
```

### Task 3: Add container and compose support for the service

**Files:**
- Create: `Dockerfile.auto-upload`
- Create: `docker-compose.auto-upload.yml`
- Create: `.env.auto-upload.example`

- [ ] **Step 1: Add the dedicated Dockerfile**

```dockerfile
FROM python:3.13-slim-bullseye

WORKDIR /app
COPY . /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg exiftool \
    && rm -rf /var/lib/apt/lists/*
RUN pip --no-cache-dir install /app/packages/markitdown[all,service]

ENTRYPOINT ["markitdown-auto-upload"]
```

- [ ] **Step 2: Add the compose file**

```yaml
services:
  markitdown-auto-upload:
    build:
      context: .
      dockerfile: Dockerfile.auto-upload
    env_file:
      - .env.auto-upload
    volumes:
      - ./data/input:/data/input
      - ./data/export:/data/export
      - ./data/archive:/data/archive
      - ./data/error:/data/error
    restart: unless-stopped
```

- [ ] **Step 3: Add the example env file**

```env
OUTLINE_BASE_URL=https://lernen.rohner-dozent.de
OUTLINE_API_TOKEN=replace-me
OUTLINE_COLLECTION_NAME=Auto-Upload
INPUT_DIR=/data/input
EXPORT_DIR=/data/export
ARCHIVE_DIR=/data/archive
ERROR_DIR=/data/error
```

- [ ] **Step 4: Run the targeted tests again**

Run: `PYTHONPATH=packages/markitdown/src python3 -m pytest packages/markitdown/tests/test_auto_upload.py -q`
Expected: PASS

- [ ] **Step 5: Commit the container setup**

```bash
git add Dockerfile.auto-upload docker-compose.auto-upload.yml .env.auto-upload.example
git commit -m "feat: add docker auto-upload runtime"
```

### Task 4: Document usage and verify the finished feature

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the new auto-upload usage section to the README**

```md
## Auto-upload Service

Use `Dockerfile.auto-upload` and `docker-compose.auto-upload.yml` to run a persistent worker that:

- watches `input/`
- converts files to Markdown
- writes `.md` files to `export/`
- uploads them to Outline
- moves originals to `archive/` or `error/`
```

- [ ] **Step 2: Run the targeted tests and existing CLI smoke tests**

Run: `PYTHONPATH=packages/markitdown/src python3 -m pytest packages/markitdown/tests/test_auto_upload.py packages/markitdown/tests/test_cli_misc.py -q`
Expected: PASS

- [ ] **Step 3: Build the dedicated Docker image**

Run: `docker build -f Dockerfile.auto-upload -t markitdown-auto-upload:test .`
Expected: exit code `0`

- [ ] **Step 4: Commit the documentation update**

```bash
git add README.md
git commit -m "docs: explain auto-upload service usage"
```
