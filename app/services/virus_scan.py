from app.utils.logger import app_logger


class VirusScanService:
    """Placeholder virus scanning service, intended to be wired to a real scanner later."""

    async def scan_file(self, file_path: str) -> bool:
        """Scan a file for malicious content and return True if the file is clean."""
        app_logger.info("Virus scan placeholder invoked for: {}", file_path)
        return True
