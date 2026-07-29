import shutil
from pathlib import Path
from typing import Iterable

from app.utils.logger import app_logger


class CleanupService:
    """Removes temporary local files and directories created during processing."""

    def delete_files(self, file_paths: Iterable[str]) -> None:
        """Delete a collection of local files, ignoring files that do not exist."""
        for file_path in file_paths:
            path = Path(file_path)
            if path.is_file():
                path.unlink(missing_ok=True)
                app_logger.info("Deleted temporary file: {}", file_path)

    def delete_directory(self, directory_path: str) -> None:
        """Recursively delete a local directory if it exists."""
        path = Path(directory_path)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            app_logger.info("Deleted temporary directory: {}", directory_path)
