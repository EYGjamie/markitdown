from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileMovedEvent
from watchdog.observers import Observer

from markitdown import MarkItDown

from .config import AutoUploadConfig
from .files import move_with_collision_handling, unique_path, wait_for_stable_file
from .outline import OutlineClient


@dataclass
class ProcessResult:
    source_path: Path
    export_path: Path
    final_source_path: Path
    succeeded: bool
    error_message: str | None = None


class Processor:
    def __init__(
        self,
        *,
        config: AutoUploadConfig,
        markitdown: Any,
        outline_client: Any,
        collection_id: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.markitdown = markitdown
        self.outline_client = outline_client
        self.collection_id = collection_id
        self.logger = logger or logging.getLogger(__name__)

    def process_file(self, source_path: Path) -> ProcessResult:
        export_path = unique_path(self.config.export_dir / f"{source_path.stem}.md")
        self.logger.info("Processing %s", source_path)
        try:
            result = self.markitdown.convert(source_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(result.markdown, encoding="utf-8")

            self.outline_client.create_document(
                title=source_path.stem,
                markdown=result.markdown,
                collection_id=self.collection_id,
            )

            final_path = move_with_collision_handling(source_path, self.config.archive_dir)
            self.logger.info("Archived %s to %s", source_path, final_path)
            return ProcessResult(
                source_path=source_path,
                export_path=export_path,
                final_source_path=final_path,
                succeeded=True,
            )
        except Exception as exc:
            self.logger.exception("Failed to process %s", source_path)
            final_path = source_path
            if source_path.exists():
                final_path = move_with_collision_handling(source_path, self.config.error_dir)
            return ProcessResult(
                source_path=source_path,
                export_path=export_path,
                final_source_path=final_path,
                succeeded=False,
                error_message=str(exc),
            )


class _QueueingEventHandler(FileSystemEventHandler):
    def __init__(self, service: "AutoUploadService") -> None:
        self.service = service

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.service.enqueue_from_thread(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self.service.enqueue_from_thread(Path(event.dest_path))


class AutoUploadService:
    def __init__(
        self,
        *,
        config: AutoUploadConfig,
        markitdown: MarkItDown,
        outline_client: OutlineClient,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.markitdown = markitdown
        self.outline_client = outline_client
        self.logger = logger or logging.getLogger(__name__)
        self.queue: asyncio.Queue[Path] = asyncio.Queue()
        self._tracked_paths: set[Path] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._observer: Observer | None = None
        self._processor: Processor | None = None

    @classmethod
    def from_config(cls, config: AutoUploadConfig) -> "AutoUploadService":
        return cls(
            config=config,
            markitdown=MarkItDown(),
            outline_client=OutlineClient(
                base_url=config.outline_base_url,
                api_token=config.outline_api_token,
            ),
        )

    async def run(self) -> None:
        self.config.ensure_directories()
        collection_id = self.outline_client.resolve_collection_id(
            self.config.outline_collection_name
        )
        self._processor = Processor(
            config=self.config,
            markitdown=self.markitdown,
            outline_client=self.outline_client,
            collection_id=collection_id,
            logger=self.logger,
        )
        self._loop = asyncio.get_running_loop()
        self._start_observer()

        worker_count = max(1, self.config.worker_concurrency)
        workers = [asyncio.create_task(self._worker()) for _ in range(worker_count)]
        try:
            await self._enqueue_existing_files()
            await asyncio.Event().wait()
        finally:
            if self._observer is not None:
                self._observer.stop()
                self._observer.join(timeout=5)
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    def enqueue_from_thread(self, path: Path) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._consider_path(path), self._loop)

    async def _enqueue_existing_files(self) -> None:
        for path in sorted(self.config.input_dir.iterdir()):
            await self._consider_path(path)

    async def _consider_path(self, path: Path) -> None:
        resolved_path = path.resolve()
        if not path.exists() or not path.is_file():
            return
        if path.parent.resolve() != self.config.input_dir.resolve():
            return
        if resolved_path in self._tracked_paths:
            return
        is_stable = await wait_for_stable_file(
            path,
            stable_seconds=self.config.file_stable_seconds,
            poll_interval=self.config.poll_interval,
        )
        if not is_stable:
            return
        self._tracked_paths.add(resolved_path)
        await self.queue.put(path)
        self.logger.info("Queued %s", path)

    async def _worker(self) -> None:
        assert self._processor is not None
        while True:
            path = await self.queue.get()
            try:
                self._processor.process_file(path)
            finally:
                self._tracked_paths.discard(path.resolve())
                self.queue.task_done()

    def _start_observer(self) -> None:
        handler = _QueueingEventHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.config.input_dir), recursive=False)
        observer.start()
        self._observer = observer
