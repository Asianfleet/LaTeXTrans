import io
import sys
import tempfile
import unittest
from pathlib import Path

from main import _project_log_path, _redirect_console_to_log, _tee_console_to_log


class CliLogTests(unittest.TestCase):
    def test_project_log_path_uses_translated_project_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = _project_log_path(
                output_dir=tmp_dir,
                target_language="ch",
                project_dir=str(Path("tex source") / "2510.14901"),
            )

        self.assertEqual(log_path, Path(tmp_dir) / "ch_2510.14901" / "latextrans.log")

    def test_tee_console_to_log_preserves_console_output_and_writes_log(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "latextrans.log"

            with _tee_console_to_log(log_path, stdout=stdout, stderr=stderr):
                print("stdout message")
                print("stderr message", file=sys.stderr)

            log_text = log_path.read_text(encoding="utf-8")

        self.assertIn("stdout message", stdout.getvalue())
        self.assertIn("stderr message", stderr.getvalue())
        self.assertIn("stdout message", log_text)
        self.assertIn("stderr message", log_text)

    def test_redirect_console_to_log_does_not_write_to_console_streams(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "latextrans.log"

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            try:
                sys.stdout = stdout
                sys.stderr = stderr
                with _redirect_console_to_log(log_path):
                    print("stdout message")
                    print("stderr message", file=sys.stderr)
                self.assertIs(sys.stdout, stdout)
                self.assertIs(sys.stderr, stderr)
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("stdout message", log_text)
        self.assertIn("stderr message", log_text)

    def test_redirect_console_to_log_restores_console_streams_after_exception(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "latextrans.log"

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            try:
                sys.stdout = stdout
                sys.stderr = stderr
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    with _redirect_console_to_log(log_path):
                        print("stdout before boom")
                        print("stderr before boom", file=sys.stderr)
                        raise RuntimeError("boom")

                self.assertIs(sys.stdout, stdout)
                self.assertIs(sys.stderr, stderr)
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("stdout before boom", log_text)
        self.assertIn("stderr before boom", log_text)


if __name__ == "__main__":
    unittest.main()
