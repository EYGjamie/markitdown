from pathlib import Path

import pytest

from markitdown import DocumentConverterResult
from markitdown.auto_upload.config import AutoUploadConfig
from markitdown.auto_upload.files import unique_path
from markitdown.auto_upload.outline import OutlineClient, OutlineError
from markitdown.auto_upload.service import Processor


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = responses
        self.calls: list[tuple[str, dict, dict]] = []

    def post(self, url: str, json: dict, headers: dict, timeout: float) -> FakeResponse:
        self.calls.append((url, json, headers))
        return self._responses.pop(0)


class FakeMarkItDown:
    def __init__(self, markdown: str):
        self.markdown = markdown

    def convert(self, source: Path) -> DocumentConverterResult:
        return DocumentConverterResult(markdown=self.markdown, title=source.stem)


class RecordingOutlineClient:
    def __init__(self):
        self.created: list[tuple[str, str, str]] = []

    def create_document(self, *, title: str, markdown: str, collection_id: str) -> dict:
        self.created.append((title, markdown, collection_id))
        return {"id": "doc-123"}


class FailingOutlineClient:
    def create_document(self, *, title: str, markdown: str, collection_id: str) -> dict:
        raise OutlineError("upload failed")


def make_config(tmp_path: Path) -> AutoUploadConfig:
    return AutoUploadConfig(
        input_dir=tmp_path / "input",
        export_dir=tmp_path / "export",
        archive_dir=tmp_path / "archive",
        error_dir=tmp_path / "error",
        outline_base_url="https://lernen.rohner-dozent.de",
        outline_api_token="token",
        outline_collection_name="Auto-Upload",
    )


def test_unique_path_adds_timestamp_when_target_exists(tmp_path: Path):
    existing = tmp_path / "example.md"
    existing.write_text("old", encoding="utf-8")

    resolved = unique_path(existing)

    assert resolved != existing
    assert resolved.parent == existing.parent
    assert resolved.suffix == ".md"
    assert resolved.stem.startswith("example-")


def test_outline_client_resolves_collection_id_from_exact_match():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "ok": True,
                    "data": [
                        {"id": "partial", "name": "Auto-Upload Copy"},
                        {"id": "target", "name": "Auto-Upload"},
                    ],
                }
            )
        ]
    )
    client = OutlineClient(
        base_url="https://lernen.rohner-dozent.de",
        api_token="token",
        session=session,
    )

    collection_id = client.resolve_collection_id("Auto-Upload")

    assert collection_id == "target"
    assert session.calls[0][0].endswith("/api/collections.list")
    assert session.calls[0][1] == {"query": "Auto-Upload"}


def test_outline_client_raises_when_collection_missing():
    session = FakeSession([FakeResponse({"ok": True, "data": []})])
    client = OutlineClient(
        base_url="https://lernen.rohner-dozent.de",
        api_token="token",
        session=session,
    )

    with pytest.raises(OutlineError, match="Auto-Upload"):
        client.resolve_collection_id("Auto-Upload")


def test_processor_exports_uploads_and_archives(tmp_path: Path):
    config = make_config(tmp_path)
    for path in (config.input_dir, config.export_dir, config.archive_dir, config.error_dir):
        path.mkdir(parents=True, exist_ok=True)

    source = config.input_dir / "lesson-plan.docx"
    source.write_text("source", encoding="utf-8")

    outline_client = RecordingOutlineClient()
    processor = Processor(
        config=config,
        markitdown=FakeMarkItDown("# Lesson Plan\n\nContent"),
        outline_client=outline_client,
        collection_id="collection-123",
    )

    result = processor.process_file(source)

    assert result.succeeded is True
    assert result.export_path.read_text(encoding="utf-8") == "# Lesson Plan\n\nContent"
    assert result.final_source_path.parent == config.archive_dir
    assert result.final_source_path.exists()
    assert not source.exists()
    assert outline_client.created == [
        ("lesson-plan", "# Lesson Plan\n\nContent", "collection-123")
    ]


def test_processor_moves_source_to_error_when_upload_fails(tmp_path: Path):
    config = make_config(tmp_path)
    for path in (config.input_dir, config.export_dir, config.archive_dir, config.error_dir):
        path.mkdir(parents=True, exist_ok=True)

    source = config.input_dir / "broken.docx"
    source.write_text("source", encoding="utf-8")

    processor = Processor(
        config=config,
        markitdown=FakeMarkItDown("# Broken"),
        outline_client=FailingOutlineClient(),
        collection_id="collection-123",
    )

    result = processor.process_file(source)

    assert result.succeeded is False
    assert result.final_source_path.parent == config.error_dir
    assert result.final_source_path.exists()
    assert result.export_path.read_text(encoding="utf-8") == "# Broken"
