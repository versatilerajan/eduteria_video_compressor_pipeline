import hashlib
from pathlib import Path

import aiofiles


async def compute_sha256(file_path: str, chunk_size: int = 1024 * 1024) -> str:
    """Compute the SHA-256 hash of a file on disk without loading it fully into memory."""
    digest = hashlib.sha256()

    async with aiofiles.open(file_path, "rb") as file_handle:
        while True:
            chunk = await file_handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def file_size_bytes(file_path: str) -> int:
    """Return the size in bytes of a file on disk."""
    return Path(file_path).stat().st_size
