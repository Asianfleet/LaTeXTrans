import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.project_sources import RemoteArchiveDownloadError, download_remote_archive


class _FakeResponse:
    def __init__(self, headers=None, chunks=None, status_error=None):
        self.headers = headers or {}
        self._chunks = chunks or []
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error

    def iter_content(self, chunk_size=8192):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ProjectSourcesTests(unittest.TestCase):
    def test_download_remote_archive_rejects_non_http_scheme(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(
                RemoteArchiveDownloadError,
                "Only http/https URLs are supported",
            ):
                download_remote_archive("ftp://example.test/paper.zip", tmp_dir)

    def test_download_remote_archive_saves_supported_archive(self):
        response = _FakeResponse(
            headers={"Content-Type": "application/zip"},
            chunks=[b"PK", b"DATA"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.project_sources.requests.get", return_value=response):
                archive_path = download_remote_archive("https://example.test/paper.zip", tmp_dir)

            saved = Path(archive_path)
            self.assertTrue(saved.exists())
            self.assertEqual(saved.read_bytes(), b"PKDATA")
            self.assertEqual(saved.suffix, ".zip")

    def test_download_remote_archive_rejects_html_response(self):
        response = _FakeResponse(
            headers={"Content-Type": "text/html; charset=utf-8"},
            chunks=[b"<html></html>"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.project_sources.requests.get", return_value=response):
                with self.assertRaisesRegex(
                    RemoteArchiveDownloadError,
                    "HTML pages are not supported",
                ):
                    download_remote_archive("https://example.test/download", tmp_dir)
