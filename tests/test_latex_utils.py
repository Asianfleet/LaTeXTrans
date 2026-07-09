import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.formats.latex.utils import LatexNodes2Text, batch_download_arxiv_tex, is_already_downloaded, replace_href


class LatexUtilsTests(unittest.TestCase):
    def test_replace_href_handles_nested_braces_in_url_argument(self):
        latex = (
            r"\href{https://example.com/plain}{Plain} "
            r"\href{https://example.com/\model{}}{\model{}}"
        )

        cleaned = replace_href(latex)

        self.assertEqual(cleaned, r"Plain \model{}")
        LatexNodes2Text().latex_to_text(cleaned)

    def test_empty_arxiv_source_directory_is_not_already_downloaded(self):
        """确认空的 arXiv 源码目录不会被当作已下载项目。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_root = Path(tmp_dir)
            (source_root / "2512.16912").mkdir()

            self.assertFalse(is_already_downloaded("2512.16912", str(source_root)))

    def test_batch_download_redownloads_empty_arxiv_source_directory(self):
        """确认空的 arXiv 源码目录会触发重新下载源码。"""
        class FakePdfResponse:
            """模拟 arXiv PDF 下载响应，避免测试访问真实网络。"""

            content = b"%PDF"

            def raise_for_status(self):
                """模拟成功的 HTTP 状态检查。"""
                return None

        with tempfile.TemporaryDirectory() as tmp_dir:
            source_root = Path(tmp_dir)
            stale_dir = source_root / "2512.16912"
            stale_dir.mkdir()

            def fake_download(arxiv_id, tex_url, save_dir, headers):
                """记录重新下载请求并返回预期源码目录。"""
                self.assertEqual(arxiv_id, "2512.16912")
                self.assertEqual(tex_url, "https://arxiv.org/e-print/2512.16912")
                self.assertEqual(save_dir, str(source_root))
                return str(source_root / arxiv_id)

            with patch(
                "src.formats.latex.utils.get_tex_url",
                return_value="https://arxiv.org/e-print/2512.16912",
            ):
                with patch("src.formats.latex.utils.download_tex", side_effect=fake_download) as download_tex:
                    with patch("src.formats.latex.utils.requests.get", return_value=FakePdfResponse()):
                        source_dirs = batch_download_arxiv_tex(["2512.16912"], str(source_root))

            download_tex.assert_called_once()
            self.assertEqual(source_dirs, [str(stale_dir)])


if __name__ == "__main__":
    unittest.main()
