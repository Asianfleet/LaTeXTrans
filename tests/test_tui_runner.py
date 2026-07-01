"""Tests for the TUI runtime runner bridge."""

import unittest
from unittest.mock import patch

from src.tui.runner import run_tui_task


class TuiRunnerTests(unittest.TestCase):
    """Verify that TUI tasks are routed into the shared runtime workflow."""

    def test_run_tui_task_passes_arxiv_inputs_as_paper_list(self):
        """ArXiv UI inputs should be passed to runtime as paper_list overrides."""
        config = {"target_language": "ch", "paper_list": []}
        events = []

        with patch("src.tui.runner.runtime.load_runtime_config", return_value=config) as load_config:
            with patch(
                "src.tui.runner.runtime.prepare_projects",
                return_value=([r"D:\paper"], config, "tex-source", "outputs"),
            ) as prepare_projects:
                with patch(
                    "src.tui.runner.runtime.run_projects",
                    return_value={"completed_projects": [], "failed_projects": []},
                ) as run_projects:
                    result = run_tui_task(
                        config_path="config/ui.toml",
                        input_type="arxiv",
                        items=["2508.18791"],
                        overrides={"target_language": "ja"},
                        event_callback=events.append,
                    )

        self.assertEqual(load_config.call_args.kwargs["overrides"]["paper_list"], ["2508.18791"])
        prepare_projects.assert_called_once_with(config=config, project_items=[], project_url_items=[], all_existing=False)
        run_projects.assert_called_once()
        self.assertEqual(result["projects"], [r"D:\paper"])

    def test_run_tui_task_routes_local_and_remote_inputs(self):
        """Local and remote UI inputs should be routed to runtime project arguments."""
        config = {"target_language": "ch", "paper_list": []}

        with patch("src.tui.runner.runtime.load_runtime_config", return_value=config):
            with patch("src.tui.runner.runtime.prepare_projects", return_value=([], config, "src", "out")) as prepare_projects:
                with patch("src.tui.runner.runtime.run_projects", return_value={"completed_projects": [], "failed_projects": []}):
                    run_tui_task("config/ui.toml", "local", [r"D:\paper"], {}, lambda event: None)
                    run_tui_task("config/ui.toml", "remote", ["https://example.test/paper.zip"], {}, lambda event: None)

        self.assertEqual(prepare_projects.call_args_list[0].kwargs["project_items"], [r"D:\paper"])
        self.assertEqual(prepare_projects.call_args_list[1].kwargs["project_url_items"], ["https://example.test/paper.zip"])


if __name__ == "__main__":
    unittest.main()
