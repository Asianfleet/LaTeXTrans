from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlparse

import requests
from requests.structures import CaseInsensitiveDict

SUPPORTED_ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")


class RemoteArchiveDownloadError(ValueError):
    pass


def _filename_from_content_disposition(value: str) -> str | None:
    extended_match = re.search(r"filename\*\s*=\s*([^;]+)", value or "", re.IGNORECASE)
    if extended_match:
        raw_filename = extended_match.group(1).strip().strip('"')
        if "''" in raw_filename:
            raw_filename = raw_filename.split("''", 1)[1]
        return Path(unquote(raw_filename)).name

    match = re.search(r'filename\s*=\s*"?([^";]+)"?', value or "", re.IGNORECASE)
    if match:
        return Path(match.group(1)).name
    return None


def _suffix_from_content_type(content_type: str) -> str | None:
    content_type = content_type.lower()
    if "zip" in content_type:
        return ".zip"
    if "gzip" in content_type:
        return ".tar.gz"
    if "x-tar" in content_type or "tar" in content_type:
        return ".tar"
    return None


def _guess_archive_name(url: str, headers: Mapping[str, str]) -> str:
    content_suffix = _suffix_from_content_type(headers.get("Content-Type", ""))
    disposition_name = _filename_from_content_disposition(
        headers.get("Content-Disposition", "")
    )
    if disposition_name:
        if not disposition_name.lower().endswith(SUPPORTED_ARCHIVE_SUFFIXES) and content_suffix:
            return f"{disposition_name}{content_suffix}"
        return disposition_name
    path_name = Path(urlparse(url).path).name
    if path_name:
        if not path_name.lower().endswith(SUPPORTED_ARCHIVE_SUFFIXES) and content_suffix:
            return f"{path_name}{content_suffix}"
        return path_name
    return f"downloaded-archive{content_suffix or '.zip'}"


def _looks_like_supported_archive(url: str, headers: Mapping[str, str]) -> bool:
    filename = _guess_archive_name(url, headers).lower()
    content_type = headers.get("Content-Type", "").lower()
    if filename.endswith(SUPPORTED_ARCHIVE_SUFFIXES):
        return True
    return any(token in content_type for token in ("zip", "gzip", "x-tar", "tar"))


def _split_archive_name(filename: str) -> tuple[str, str]:
    lower_filename = filename.lower()
    for suffix in sorted(SUPPORTED_ARCHIVE_SUFFIXES, key=len, reverse=True):
        if lower_filename.endswith(suffix):
            return filename[: -len(suffix)], filename[-len(suffix) :]
    path = Path(filename)
    return path.stem, path.suffix


def download_remote_archive(url: str, projects_dir: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteArchiveDownloadError("Only http/https URLs are supported.")

    target_dir = Path(projects_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    destination: Path | None = None
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            headers = CaseInsensitiveDict(response.headers)
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
                stem, suffix = _split_archive_name(destination.name)
                index = 1
                while destination.exists():
                    destination = target_dir / f"{stem}_{index}{suffix}"
                    index += 1

            with destination.open("wb") as handle:
                for chunk in response.iter_content(8192):
                    if chunk:
                        handle.write(chunk)
    except RemoteArchiveDownloadError:
        raise
    except (requests.RequestException, OSError) as exc:
        if destination is not None and destination.exists():
            destination.unlink()
        raise RemoteArchiveDownloadError(
            f"Failed to download remote archive: {exc}"
        ) from exc

    return str(destination)
