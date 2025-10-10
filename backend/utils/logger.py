from loguru import logger

from backend.config import settings


def configure_logging() -> None:
    """Configure application-wide logging."""
    logger.remove()
    logger.add(
        settings.app.log_dir / "app.log",
        rotation="10 MB",
        retention="14 days",
        enqueue=True,
        level=settings.app.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level=settings.app.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )


configure_logging()
