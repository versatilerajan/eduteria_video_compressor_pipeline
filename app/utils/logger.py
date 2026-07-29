import sys
from pathlib import Path

from loguru import logger

from app.config.settings import settings


def configure_logger() -> "logger":
    """Configure and return the application-wide structured logger instance."""
    logger.remove()

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=False,
        diagnose=False,
    )

    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        level=settings.log_level,
        rotation="50 MB",
        retention="14 days",
        compression="zip",
        serialize=True,
        backtrace=False,
        diagnose=False,
    )

    return logger


app_logger = configure_logger()
