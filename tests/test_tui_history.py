import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.tui.history import (
    TUI_PROJECT_METADATA_FILENAME,
    infer_project_status,
    load_output_history,
    write_project_metadata,
)
from src.tui.state import ProjectStatus


class TuiHistoryTests(unittest.TestCase):
    """验证 TUI 会从 outputs 目录恢复历史项目并推断状态。"""

    def test_load_output_history_adds_legacy_project_with_empty_task_id(self):
        """确认旧版输出目录没有元数据时会以空任务 id 加入历史列表。"""
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            project_dir = output_root / "ch_2308.10248"
            project_dir.mkdir(parents=True)
            (project_dir / "ch_2308.10248.pdf").write_bytes(b"%PDF")
            (project_dir / "errors_report.json").write_text("[]", encoding="utf-8")

            tasks = load_output_history(output_root)

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].task_id, "")
            self.assertEqual(tasks[0].projects[0].project_name, "2308.10248")
            self.assertEqual(tasks[0].projects[0].status, ProjectStatus.COMPLETED)

    def test_load_output_history_restores_task_id_from_metadata(self):
        """确认新版输出目录会从元数据恢复任务 id。"""
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            project_dir = output_root / "ch_paper"
            project_dir.mkdir(parents=True)
            (project_dir / "ch_paper.pdf").write_bytes(b"%PDF")
            (project_dir / "errors_report.json").write_text("[]", encoding="utf-8")
            (project_dir / TUI_PROJECT_METADATA_FILENAME).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "task_id": "20260701T175144.123",
                        "input_type": "local",
                        "input_item": "paper",
                        "project_name": "paper",
                        "status": "completed",
                    }
                ),
                encoding="utf-8",
            )

            tasks = load_output_history(output_root)

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].task_id, "20260701T175144.123")
            self.assertEqual(tasks[0].input_type, "local")
            self.assertEqual(tasks[0].inputs, ["paper"])
            self.assertIsNotNone(tasks[0].projects[0].project_dir)
            self.assertTrue(tasks[0].projects[0].project_dir.endswith("ch_paper"))
            self.assertEqual(tasks[0].projects[0].project_dir, str(project_dir))

    def test_infer_project_status_uses_errors_pdf_terms_and_artifacts(self):
        """确认旧版和新版项目可按产物推断 completed、failed、terms_ready 和 pending。"""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            completed = root / "ch_done"
            completed.mkdir()
            (completed / "ch_done.pdf").write_bytes(b"%PDF")
            (completed / "errors_report.json").write_text("[]", encoding="utf-8")

            failed = root / "ch_failed"
            failed.mkdir()
            (failed / "errors_report.json").write_text('[{"error": "bad"}]', encoding="utf-8")

            terms_ready = root / "ch_terms"
            terms_ready.mkdir()
            (terms_ready / "project_terms.csv").write_text("Source Term,Target Translation\nA,B\n", encoding="utf-8")

            pending = root / "ch_pending"
            pending.mkdir()

            self.assertEqual(infer_project_status(completed), ProjectStatus.COMPLETED)
            self.assertEqual(infer_project_status(failed), ProjectStatus.FAILED)
            self.assertEqual(infer_project_status(terms_ready), ProjectStatus.TERMS_READY)
            self.assertEqual(infer_project_status(pending), ProjectStatus.PENDING)

    def test_running_metadata_is_not_restored_as_running_history(self):
        """确认历史加载不会把上次会话残留的 running 元数据继续显示为 running。"""
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            project_dir = output_root / "ch_running"
            project_dir.mkdir(parents=True)
            (project_dir / "sections_map.json").write_text("[]", encoding="utf-8")
            (project_dir / TUI_PROJECT_METADATA_FILENAME).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "task_id": "20260701T175144.123",
                        "project_name": "running",
                        "status": "running",
                    }
                ),
                encoding="utf-8",
            )

            tasks = load_output_history(output_root)

            self.assertEqual(tasks[0].projects[0].status, ProjectStatus.FAILED)

    def test_write_project_metadata_persists_timestamp_task_id(self):
        """确认新版任务会把时间戳任务 id 写入项目输出目录元数据。"""
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "outputs" / "ch_paper"
            project_dir.mkdir(parents=True)

            write_project_metadata(
                project_dir=project_dir,
                task_id="20260701T175144.123",
                input_type="arxiv",
                input_item="2308.10248",
                project_name="2308.10248",
                status=ProjectStatus.COMPLETED,
            )

            metadata = json.loads((project_dir / TUI_PROJECT_METADATA_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(metadata["task_id"], "20260701T175144.123")
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["input_item"], "2308.10248")


if __name__ == "__main__":
    unittest.main()
