import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from src.runtime import (
    classify_project_result,
    load_runtime_config,
    run_projects,
    should_exit_with_failure,
)


class RuntimeProjectResultTests(unittest.TestCase):
    def test_load_runtime_config_applies_retranslate_with_terms_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.toml"
            config_path.write_text(
                """
[llm_config]
model = "test-model"
api_key = "test-key"
base_url = "https://example.test/v1/chat/completions"

paper_list = []
retranslate_with_terms = false
""".strip(),
                encoding="utf-8",
            )

            config = load_runtime_config(
                str(config_path),
                overrides={"retranslate_with_terms": True},
            )

        self.assertTrue(config["retranslate_with_terms"])

    def test_cli_uses_runtime_prepare_and_run_projects(self):
        import main

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_path = tmp_path / "config.toml"
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            project_dir = tmp_path / "paper"
            project_dir.mkdir()
            config_path.write_text(
                f"""
[llm_config]
model = "test-model"
api_key = "test-key"
base_url = "https://example.test/v1/chat/completions"

paper_list = []
tex_sources_dir = {str(source_dir)!r}
output_dir = {str(output_dir)!r}
target_language = "ch"
""".strip(),
                encoding="utf-8",
            )
            runtime_config = {"target_language": "ch", "paper_list": []}

            with patch.object(
                main.sys,
                "argv",
                ["latextrans", "--config", str(config_path), "--project", str(project_dir)],
            ):
                with patch("src.runtime.load_runtime_config", return_value=runtime_config):
                    with patch(
                        "src.runtime.prepare_projects",
                        return_value=([str(project_dir)], runtime_config, str(source_dir), str(output_dir)),
                    ) as prepare_projects:
                        with patch(
                            "src.runtime.run_projects",
                            return_value={"completed_projects": [{"project_name": "paper"}], "failed_projects": []},
                        ) as run_projects_mock:
                            with redirect_stdout(StringIO()):
                                main.main()

        prepare_projects.assert_called_once_with(
            config=runtime_config,
            project_items=[str(project_dir)],
            project_url_items=[],
            all_existing=False,
        )
        run_projects_mock.assert_called_once()
        self.assertEqual(run_projects_mock.call_args.kwargs["config"], runtime_config)
        self.assertEqual(run_projects_mock.call_args.kwargs["projects"], [str(project_dir)])
        self.assertEqual(run_projects_mock.call_args.kwargs["output_dir"], str(output_dir))

    def test_cli_does_not_disable_config_retranslate_when_flag_absent(self):
        import main

        runtime_config = {"target_language": "ch", "paper_list": []}

        with patch.object(main.sys, "argv", ["latextrans", "--config", "config/test.toml"]):
            with patch("src.runtime.load_runtime_config", return_value=runtime_config) as load_config:
                with patch(
                    "src.runtime.prepare_projects",
                    return_value=(["paper"], runtime_config, "tex-source", "outputs"),
                ):
                    with patch(
                        "src.runtime.run_projects",
                        return_value={"completed_projects": [{"project_name": "paper"}], "failed_projects": []},
                    ):
                        with redirect_stdout(StringIO()):
                            main.main()

        overrides = load_config.call_args.kwargs["overrides"]
        self.assertNotEqual(overrides.get("retranslate_with_terms"), False)

    def test_cli_passes_project_url_items_to_prepare_projects(self):
        import main

        runtime_config = {"target_language": "ch", "paper_list": []}
        argv = [
            "latextrans",
            "--config",
            "config/test.toml",
            "--project-url",
            "https://example.test/paper.tar.gz,https://example.test/paper2.zip",
        ]

        with patch.object(main.sys, "argv", argv):
            with patch("src.runtime.load_runtime_config", return_value=runtime_config):
                with patch(
                    "src.runtime.prepare_projects",
                    return_value=(["paper"], runtime_config, "tex-source", "outputs"),
                ) as prepare_projects:
                    with patch(
                        "src.runtime.run_projects",
                        return_value={
                            "completed_projects": [{"project_name": "paper"}],
                            "failed_projects": [],
                        },
                    ):
                        with redirect_stdout(StringIO()):
                            main.main()

        prepare_projects.assert_called_once_with(
            config=runtime_config,
            project_items=[],
            project_url_items=[
                "https://example.test/paper.tar.gz",
                "https://example.test/paper2.zip",
            ],
            all_existing=False,
        )

    def test_prepare_projects_downloads_remote_archives(self):
        from src.runtime import prepare_projects

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }
            downloaded_archive = source_dir / "paper.tar.gz"
            extracted_project = source_dir / "paper"

            with patch("src.runtime.download_remote_archive", return_value=str(downloaded_archive)) as download_mock:
                with patch("src.runtime.extract_local_archive", return_value=str(extracted_project)) as extract_mock:
                    projects, returned_config, projects_dir, returned_output_dir = prepare_projects(
                        config=config,
                        project_items=[],
                        project_url_items=["https://example.test/paper.tar.gz"],
                        all_existing=False,
                    )

        download_mock.assert_called_once_with("https://example.test/paper.tar.gz", str(source_dir))
        extract_mock.assert_called_once_with(str(downloaded_archive), str(source_dir))
        self.assertEqual(projects, [str(extracted_project.resolve())])
        self.assertEqual(returned_config, config)
        self.assertEqual(projects_dir, str(source_dir.resolve()))
        self.assertEqual(returned_output_dir, str(output_dir.resolve()))

    def test_prepare_projects_combines_local_and_remote_inputs(self):
        from src.runtime import prepare_projects

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            local_project = tmp_path / "local-paper"
            local_project.mkdir()
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            extracted_project = source_dir / "remote-paper"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }

            with patch("src.runtime.download_remote_archive", return_value=str(source_dir / "remote-paper.zip")):
                with patch("src.runtime.extract_local_archive", return_value=str(extracted_project)):
                    projects, _, _, _ = prepare_projects(
                        config=config,
                        project_items=[str(local_project)],
                        project_url_items=["https://example.test/remote-paper.zip"],
                        all_existing=False,
                    )

        self.assertEqual(
            projects,
            [
                str(local_project.resolve()),
                str(extracted_project.resolve()),
            ],
        )

    def test_prepare_projects_removes_downloaded_remote_archive_after_extract(self):
        from src.runtime import prepare_projects

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }
            source_dir.mkdir()
            downloaded_archive = source_dir / "paper.tar.gz"
            downloaded_archive.write_bytes(b"archive-bytes")
            extracted_project = source_dir / "paper"

            with patch("src.runtime.download_remote_archive", return_value=str(downloaded_archive)):
                with patch("src.runtime.extract_local_archive", return_value=str(extracted_project)):
                    prepare_projects(
                        config=config,
                        project_items=[],
                        project_url_items=["https://example.test/paper.tar.gz"],
                        all_existing=False,
                    )

            self.assertFalse(downloaded_archive.exists())

    def test_prepare_projects_removes_downloaded_remote_archive_after_extract_failure(self):
        from src.runtime import prepare_projects

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }
            source_dir.mkdir()
            downloaded_archive = source_dir / "paper.tar.gz"
            downloaded_archive.write_bytes(b"archive-bytes")

            with patch("src.runtime.download_remote_archive", return_value=str(downloaded_archive)):
                with patch("src.runtime.extract_local_archive", side_effect=ValueError("broken archive")):
                    with self.assertRaisesRegex(ValueError, "No valid TeX projects available for processing."):
                        with redirect_stdout(StringIO()) as stdout:
                            prepare_projects(
                                config=config,
                                project_items=[],
                                project_url_items=["https://example.test/paper.tar.gz"],
                                all_existing=False,
                            )

            self.assertFalse(downloaded_archive.exists())
            self.assertIn(
                "[SKIP] Failed to extract remote archive https://example.test/paper.tar.gz: broken archive",
                stdout.getvalue(),
            )

    def test_prepare_projects_skips_failed_remote_archives(self):
        from src.runtime import prepare_projects
        from src.project_sources import RemoteArchiveDownloadError

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = {
                "paper_list": [],
                "tex_sources_dir": str(tmp_path / "tex-source"),
                "output_dir": str(tmp_path / "outputs"),
            }

            with patch(
                "src.runtime.download_remote_archive",
                side_effect=RemoteArchiveDownloadError("Response is not a supported archive."),
            ):
                with self.assertRaisesRegex(ValueError, "No valid TeX projects available for processing."):
                    with redirect_stdout(StringIO()) as stdout:
                        prepare_projects(
                            config=config,
                            project_items=[],
                            project_url_items=["https://example.test/download"],
                            all_existing=False,
                        )

        self.assertIn("[SKIP] Failed to download remote archive https://example.test/download", stdout.getvalue())

    def test_prepare_projects_continues_after_one_remote_archive_fails(self):
        from src.runtime import prepare_projects
        from src.project_sources import RemoteArchiveDownloadError

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            extracted_project = source_dir / "paper"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }

            with patch(
                "src.runtime.download_remote_archive",
                side_effect=[
                    RemoteArchiveDownloadError("Response is not a supported archive."),
                    str(source_dir / "paper.zip"),
                ],
            ) as download_mock:
                with patch("src.runtime.extract_local_archive", return_value=str(extracted_project)) as extract_mock:
                    with redirect_stdout(StringIO()) as stdout:
                        projects, _, _, _ = prepare_projects(
                            config=config,
                            project_items=[],
                            project_url_items=[
                                "https://example.test/bad",
                                "https://example.test/paper.zip",
                            ],
                            all_existing=False,
                        )

        self.assertEqual(projects, [str(extracted_project.resolve())])
        self.assertEqual(download_mock.call_count, 2)
        extract_mock.assert_called_once_with(str(source_dir / "paper.zip"), str(source_dir))
        self.assertIn("[SKIP] Failed to download remote archive https://example.test/bad", stdout.getvalue())

    def test_run_translation_passes_project_url_items_to_prepare_projects(self):
        from src.runtime import run_translation

        runtime_config = {"target_language": "ch", "paper_list": []}
        prepared_projects = [r"D:\paper"]

        with patch("src.runtime.load_runtime_config", return_value=runtime_config):
            with patch(
                "src.runtime.prepare_projects",
                return_value=(prepared_projects, runtime_config, "tex-source", "outputs"),
            ) as prepare_projects:
                with patch(
                    "src.runtime.run_projects",
                    return_value={"completed_projects": [], "failed_projects": []},
                ):
                    run_translation(project_url_items=["https://example.test/paper.tar.gz"])

        prepare_projects.assert_called_once_with(
            config=runtime_config,
            project_items=None,
            project_url_items=["https://example.test/paper.tar.gz"],
            all_existing=False,
        )

    def test_cli_passes_runtime_config_overrides(self):
        import main

        runtime_config = {"target_language": "ch", "paper_list": []}
        argv = [
            "latextrans",
            "--config",
            "config/test.toml",
            "--url",
            "https://example.test/v1",
            "--model",
            "test-model",
            "--key",
            "test-key",
            "--source",
            "tex-source",
            "--output",
            "outputs",
            "--arxiv",
            "2501.00001,2501.00002",
            "--retranslate-with-terms",
        ]

        with patch.object(main.sys, "argv", argv):
            with patch("src.runtime.load_runtime_config", return_value=runtime_config) as load_config:
                with patch(
                    "src.runtime.prepare_projects",
                    return_value=(["paper"], runtime_config, "tex-source", "outputs"),
                ):
                    with patch(
                        "src.runtime.run_projects",
                        return_value={"completed_projects": [{"project_name": "paper"}], "failed_projects": []},
                    ):
                        with redirect_stdout(StringIO()):
                            main.main()

        load_config.assert_called_once()
        self.assertEqual(load_config.call_args.kwargs["config_path"], "config/test.toml")
        self.assertEqual(
            load_config.call_args.kwargs["overrides"],
            {
                "url": "https://example.test/v1",
                "model": "test-model",
                "key": "test-key",
                "source": "tex-source",
                "output": "outputs",
                "source_language": "",
                "target_language": "",
                "retranslate_with_terms": True,
                "paper_list": ["2501.00001", "2501.00002"],
            },
        )

    def test_classify_project_result_completed(self):
        result = classify_project_result(
            index=1,
            total=2,
            project_name="paper",
            project_dir=r"D:\paper",
            workflow_result={
                "ok": True,
                "pdf_path": r"outputs\ch_paper\ch_paper.pdf",
                "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
            },
        )

        self.assertEqual(result["type"], "completed")
        self.assertTrue(result["ok"])

    def test_classify_project_result_failed(self):
        result = classify_project_result(
            index=1,
            total=2,
            project_name="paper",
            project_dir=r"D:\paper",
            workflow_result={
                "ok": False,
                "pdf_path": r"outputs\ch_paper\ch_paper.pdf",
                "validation_summary": {"warnings": 0, "errors": 1, "total": 1},
            },
        )

        self.assertEqual(result["type"], "failed")
        self.assertFalse(result["ok"])
        self.assertEqual(result["validation_summary"]["errors"], 1)

    def test_classify_project_result_preserves_term_review_status(self):
        result = classify_project_result(
            index=1,
            total=2,
            project_name="paper",
            project_dir=r"D:\paper",
            workflow_result={
                "ok": False,
                "status": "needs_term_review",
                "project_terms_path": r"outputs\ch_paper\project_terms.csv",
                "project_terms_decisions_path": r"outputs\ch_paper\project_terms_decisions.json",
                "error": "review terms",
            },
        )

        self.assertEqual(result["type"], "failed")
        self.assertEqual(result["status"], "needs_term_review")
        self.assertEqual(result["project_terms_path"], r"outputs\ch_paper\project_terms.csv")
        self.assertEqual(
            result["project_terms_decisions_path"],
            r"outputs\ch_paper\project_terms_decisions.json",
        )

    def test_should_exit_with_failure_when_any_project_failed(self):
        self.assertTrue(should_exit_with_failure({
            "completed_projects": [{"project_name": "a"}],
            "failed_projects": [{"project_name": "b"}],
        }))
        self.assertFalse(should_exit_with_failure({
            "completed_projects": [{"project_name": "a"}],
            "failed_projects": [],
        }))

    def test_run_projects_continues_after_workflow_failure_result(self):
        workflow_results = [
            {
                "ok": False,
                "pdf_path": None,
                "validation_summary": {"warnings": 0, "errors": 1, "total": 1},
                "error": None,
            },
            {
                "ok": True,
                "pdf_path": r"outputs\ch_second\ch_second.pdf",
                "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
                "error": None,
            },
        ]
        processed_projects = []

        class FakeCoordinatorAgent:
            def __init__(self, config, project_dir, output_dir):
                processed_projects.append(project_dir)

            def workflow_latextrans(self):
                return workflow_results.pop(0)

        with patch("src.runtime.CoordinatorAgent", FakeCoordinatorAgent):
            with redirect_stdout(StringIO()):
                status = run_projects(
                    config={},
                    projects=[r"D:\first", r"D:\second"],
                    output_dir="outputs",
                )

        self.assertEqual(processed_projects, [r"D:\first", r"D:\second"])
        self.assertEqual(len(status["failed_projects"]), 1)
        self.assertEqual(len(status["completed_projects"]), 1)
        self.assertEqual(status["failed_projects"][0]["project_name"], "first")
        self.assertEqual(status["completed_projects"][0]["project_name"], "second")

    def test_run_projects_uses_retranslation_workflow_when_requested(self):
        calls = []

        class FakeCoordinatorAgent:
            def __init__(self, config, project_dir, output_dir):
                self.project_dir = project_dir

            def workflow_latextrans_with_existing_terms(self):
                calls.append(("retranslate", self.project_dir))
                return {
                    "ok": True,
                    "pdf_path": r"outputs\ch_paper\ch_paper.pdf",
                    "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
                    "error": None,
                }

            def workflow_latextrans(self):
                calls.append(("normal", self.project_dir))
                return {"ok": False, "error": "wrong path"}

        with patch("src.runtime.CoordinatorAgent", FakeCoordinatorAgent):
            with redirect_stdout(StringIO()):
                status = run_projects(
                    config={"retranslate_with_terms": True},
                    projects=[r"D:\paper"],
                    output_dir="outputs",
                )

        self.assertEqual(calls, [("retranslate", r"D:\paper")])
        self.assertEqual(len(status["completed_projects"]), 1)

    def test_run_projects_event_payload_preserves_term_review_status(self):
        events = []

        class FakeCoordinatorAgent:
            def __init__(self, config, project_dir, output_dir):
                pass

            def workflow_latextrans(self):
                return {
                    "ok": False,
                    "status": "needs_term_review",
                    "project_terms_path": r"outputs\ch_paper\project_terms.csv",
                    "project_terms_decisions_path": r"outputs\ch_paper\project_terms_decisions.json",
                    "error": "review terms",
                }

        with patch("src.runtime.CoordinatorAgent", FakeCoordinatorAgent):
            with redirect_stdout(StringIO()):
                run_projects(
                    config={},
                    projects=[r"D:\paper"],
                    output_dir="outputs",
                    event_callback=events.append,
                )

        final_event = events[-1]
        self.assertEqual(final_event["type"], "project_error")
        self.assertEqual(final_event["status"], "needs_term_review")
        self.assertEqual(final_event["project_terms_path"], r"outputs\ch_paper\project_terms.csv")
        self.assertEqual(
            final_event["project_terms_decisions_path"],
            r"outputs\ch_paper\project_terms_decisions.json",
        )


if __name__ == "__main__":
    unittest.main()
