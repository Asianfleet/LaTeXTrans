import sys
import unittest
from unittest.mock import patch

import main as cli_main


class CliLanguageArgsTests(unittest.TestCase):
    def test_cli_language_args_override_runtime_config(self):
        """CLI language arguments are forwarded as runtime config overrides."""
        argv = [
            "latextrans",
            "--arxiv",
            "2508.18791",
            "--source_language",
            "de",
            "--target_language",
            "jp",
        ]

        with patch.object(sys, "argv", argv):
            with patch("main.runtime.load_runtime_config") as load_config:
                with patch("main.runtime.prepare_projects") as prepare_projects:
                    with patch("main.runtime.run_projects", return_value={"completed_projects": [], "failed_projects": []}):
                        with patch("main.should_exit_with_failure", return_value=False):
                            load_config.return_value = {
                                "source_language": "de",
                                "target_language": "jp",
                            }
                            prepare_projects.return_value = (["paper"], load_config.return_value, "tex source", "outputs")

                            cli_main.main()

        overrides = load_config.call_args.kwargs["overrides"]
        self.assertEqual(overrides["source_language"], "de")
        self.assertEqual(overrides["target_language"], "jp")


if __name__ == "__main__":
    unittest.main()
