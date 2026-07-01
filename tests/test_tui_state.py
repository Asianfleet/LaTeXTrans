"""Tests for Textual UI task state merging."""

import unittest

from src.tui.state import ProjectStatus, TaskViewState


class TuiStateTests(unittest.TestCase):
    """Regression tests for runtime event merging into UI state."""

    def test_apply_run_start_sets_total(self):
        """run_start events should set the task total."""
        state = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
        state.apply_event({"type": "run_start", "total": 2})
        self.assertEqual(state.total, 2)

    def test_project_lifecycle_events_update_counts_and_paths(self):
        """Project lifecycle events should update status, counts, and paths."""
        state = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
        state.apply_event(
            {
                "type": "project_start",
                "project_name": "2508.18791",
                "project_dir": r"D:\src",
                "output_dir": r"D:\out",
                "log_path": r"D:\out\latextrans.log",
            }
        )
        self.assertEqual(state.projects[0].status, ProjectStatus.RUNNING)

        state.apply_event(
            {
                "type": "project_complete",
                "project_name": "2508.18791",
                "project_dir": r"D:\src",
                "output_dir": r"D:\out",
                "pdf_path": r"D:\out\ch_2508.18791.pdf",
                "errors_report_path": r"D:\out\errors_report.json",
                "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
                "log_path": r"D:\out\latextrans.log",
            }
        )

        self.assertEqual(state.completed, 1)
        self.assertEqual(state.failed, 0)
        self.assertEqual(state.projects[0].status, ProjectStatus.COMPLETED)
        self.assertEqual(state.projects[0].pdf_path, r"D:\out\ch_2508.18791.pdf")

    def test_project_lifecycle_events_copy_terms_paths(self):
        """Project lifecycle events should preserve generated terminology paths."""
        state = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
        state.apply_event(
            {
                "type": "project_complete",
                "project_name": "2508.18791",
                "project_terms_path": r"D:\out\project_terms.csv",
                "project_terms_decisions_path": r"D:\out\project_terms_decisions.json",
            }
        )

        self.assertEqual(state.projects[0].project_terms_path, r"D:\out\project_terms.csv")
        self.assertEqual(
            state.projects[0].project_terms_decisions_path,
            r"D:\out\project_terms_decisions.json",
        )

    def test_project_error_updates_failed_count(self):
        """project_error events should mark failed projects and count them."""
        state = TaskViewState(input_type="remote", inputs=["https://example.test/paper.zip"])
        state.apply_event({"type": "project_error", "project_name": "paper", "error": "boom"})
        self.assertEqual(state.failed, 1)
        self.assertEqual(state.projects[0].status, ProjectStatus.FAILED)
        self.assertEqual(state.projects[0].error, "boom")


if __name__ == "__main__":
    unittest.main()
