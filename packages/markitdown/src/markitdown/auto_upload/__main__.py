import asyncio
import logging

from .config import AutoUploadConfig
from .service import AutoUploadService


def main() -> None:
    config = AutoUploadConfig.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    service = AutoUploadService.from_config(config)
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Auto-upload service stopped by user.")


if __name__ == "__main__":
    main()
