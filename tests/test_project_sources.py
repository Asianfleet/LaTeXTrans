import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

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
        for chunk in self._chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

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

    def test_download_remote_archive_accepts_lowercase_headers(self):
        response = _FakeResponse(
            headers={
                "content-type": "application/octet-stream",
                "content-disposition": 'attachment; filename="paper.zip"',
            },
            chunks=[b"ZIPDATA"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.project_sources.requests.get", return_value=response):
                archive_path = download_remote_archive(
                    "https://example.test/download",
                    tmp_dir,
                )

            saved = Path(archive_path)
            self.assertTrue(saved.exists())
            self.assertEqual(saved.name, "paper.zip")
            self.assertEqual(saved.read_bytes(), b"ZIPDATA")

    def test_download_remote_archive_renames_duplicate_tar_gz_archive(self):
        first_response = _FakeResponse(
            headers={"Content-Type": "application/gzip"},
            chunks=[b"FIRST"],
        )
        second_response = _FakeResponse(
            headers={"Content-Type": "application/gzip"},
            chunks=[b"SECOND"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "src.project_sources.requests.get",
                side_effect=[first_response, second_response],
            ):
                first_archive = download_remote_archive(
                    "https://example.test/paper.tar.gz",
                    tmp_dir,
                )
                second_archive = download_remote_archive(
                    "https://example.test/paper.tar.gz",
                    tmp_dir,
                )

            self.assertEqual(Path(first_archive).name, "paper.tar.gz")
            self.assertEqual(Path(second_archive).name, "paper_1.tar.gz")

    def test_download_remote_archive_cleans_partial_file_on_request_exception(self):
        response = _FakeResponse(
            headers={"Content-Type": "application/zip"},
            chunks=[
                b"PARTIAL",
                requests.RequestException("connection reset"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.project_sources.requests.get", return_value=response):
                with self.assertRaisesRegex(
                    RemoteArchiveDownloadError,
                    "Failed to download remote archive",
                ):
                    download_remote_archive("https://example.test/paper.zip", tmp_dir)

            self.assertEqual(list(Path(tmp_dir).iterdir()), [])

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
