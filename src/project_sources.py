from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

SUPPORTED_ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")


class RemoteArchiveDownloadError(ValueError):
    pass


def _filename_from_content_disposition(value: str) -> str | None:
    match = re.search(r'filename="?([^";]+)"?', value or "")
    if match:
        return Path(match.group(1)).name
    return None


def _guess_archive_name(url: str, headers: dict[str, str]) -> str:
    disposition_name = _filename_from_content_disposition(
        headers.get("Content-Disposition", "")
    )
    if disposition_name:
        return disposition_name
    path_name = Path(urlparse(url).path).name
    if path_name:
        return path_name
    return "downloaded-archive.zip"


def _looks_like_supported_archive(url: str, headers: dict[str, str]) -> bool:
    filename = _guess_archive_name(url, headers).lower()
    content_type = headers.get("Content-Type", "").lower()
    if filename.endswith(SUPPORTED_ARCHIVE_SUFFIXES):
        return True
    return any(token in content_type for token in ("zip", "gzip", "x-tar", "tar"))


def download_remote_archive(url: str, projects_dir: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteArchiveDownloadError("Only http/https URLs are supported.")

    target_dir = Path(projects_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            headers = dict(response.headers)
            content_type = headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                raise RemoteArchiveDownloadError(
                    "HTML pages are not supported for --project-url."
                )
            if not _looks_like_supported_archive(url, headers):
                raise RemoteArchiveDownloadError(
                    "Response is not a supported archive."
                )

            filename = Path(_guess_archive_name(url, headers)).name
            destination = target_dir / filename
            if destination.exists():
                stem = destination.stem
                suffix = "".join(destination.suffixes)
                index = 1
                while destination.exists():
                    destination = target_dir / f"{stem}_{index}{suffix}"
                    index += 1

            with destination.open("wb") as handle:
                for chunk in response.iter_content(8192):
                    if chunk:
                        handle.write(chunk)
    except requests.RequestException as exc:
        raise RemoteArchiveDownloadError(
            f"Failed to download remote archive: {exc}"
        ) from exc

    return str(destination)
