import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from textual.css.query import NoMatches
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    ListView,
    ProgressBar,
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TextArea,
)

from setup import load_requirements
from src.tui.app import (
    PAGE_CONFIG,
    PAGE_DETAIL,
    PAGE_ENTRY,
    PAGE_PROGRESS,
    PAGE_TASKS,
    LaTeXTransTuiApp,
)
from src.tui.history import TUI_PROJECT_METADATA_FILENAME
from src.tui.state import ProjectStatus, ProjectViewState, TaskViewState


class TuiPackagingTests(unittest.TestCase):
    """验证 Textual TUI 的打包依赖和入口。"""

    def test_textual_dependency_is_declared(self):
        """确认 requirements 声明 Textual 依赖。"""
        requirements = load_requirements("requirements.txt")
        self.assertTrue(any(item.startswith("textual") for item in requirements))

    def test_tui_run_function_is_importable(self):
        """确认 TUI run 函数可以被 console script 导入。"""
        from src.tui.app import run

        self.assertTrue(callable(run))


class TuiLayoutTests(unittest.IsolatedAsyncioTestCase):
    """验证 Textual TUI 首版主布局和页面切换行为。"""

    async def test_app_composes_sidebar_switcher_and_footer(self):
        """确认应用组合侧栏、主内容切换器和底部快捷键区域。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            self.assertIsNotNone(app.query_one("#project-list", ListView))
            self.assertIsNotNone(app.query_one("#main-switcher", ContentSwitcher))
            self.assertIsNotNone(app.query_one(Footer))

    def test_detail_page_adds_top_padding_above_tabs(self):
        """确认项目详情页顶部和 Tab 标签之间保留间距。"""
        self.assertIn("#detail {", LaTeXTransTuiApp.DEFAULT_CSS)
        self.assertIn("padding-top: 1;", LaTeXTransTuiApp.DEFAULT_CSS)

    async def test_detail_page_applies_top_padding_above_tabs(self):
        """确认项目详情页实际应用顶部间距。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            self.assertEqual(app.query_one("#detail").styles.padding.top, 1)

    async def test_switch_page_updates_content_switcher(self):
        """确认 switch_page 会更新主内容切换器当前页面。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            for page_id in [PAGE_ENTRY, PAGE_PROGRESS, PAGE_DETAIL, PAGE_TASKS, PAGE_CONFIG]:
                app.switch_page(page_id)
                self.assertEqual(
                    app.query_one("#main-switcher", ContentSwitcher).current,
                    page_id,
                )


class TuiEntryPageTests(unittest.IsolatedAsyncioTestCase):
    """验证入口页提交会创建任务状态并展示校验错误。"""

    async def test_entry_page_uses_centered_initial_form_layout(self):
        """确认入口页使用居中的标题、输入框、下拉菜单和发送按钮布局。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            self.assertEqual(str(app.query_one("#app-title", Static).content), "LaTeXTransPlus")
            self.assertIsNotNone(app.query_one("#entry-form"))
            self.assertIsNotNone(app.query_one("#entry-actions"))

            form_children = [child.id for child in app.query_one("#entry-form").children]
            self.assertEqual(
                form_children[:4],
                ["app-title", "batch-input", "entry-actions", "entry-error"],
            )
            action_children = [child.id for child in app.query_one("#entry-actions").children]
            self.assertEqual(action_children, ["input-type-select", "start-task-button"])
            self.assertEqual(str(app.query_one("#start-task-button", Button).label), "发送")

    async def test_submit_entry_form_creates_task_and_switches_to_progress(self):
        """确认有效入口表单会创建任务状态并切换到进度页。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "arxiv"
            app.query_one("#batch-input", TextArea).text = "2508.18791\n2407.01648"

            with patch.object(app, "start_current_task") as start_current_task:
                app.submit_entry_form()

            self.assertIsInstance(app.current_task, TaskViewState)
            self.assertEqual(app.current_task.inputs, ["2508.18791", "2407.01648"])
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_PROGRESS)
            start_current_task.assert_called_once_with()

    async def test_start_button_submits_entry_form(self):
        """确认开始按钮会提交入口表单并进入进度页。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test() as pilot:
            app.query_one("#input-type-select", Select).value = "arxiv"
            app.query_one("#batch-input", TextArea).text = "2508.18791"

            with patch.object(app, "start_current_task") as start_current_task:
                await pilot.click("#start-task-button")

            self.assertIsInstance(app.current_task, TaskViewState)
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_PROGRESS)
            start_current_task.assert_called_once_with()

    async def test_submit_entry_form_shows_validation_errors(self):
        """确认无效入口表单会在入口页展示校验错误。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "remote"
            app.query_one("#batch-input", TextArea).text = "file:///bad.zip"

            app.submit_entry_form()

            self.assertIn("remote input must be", str(app.query_one("#entry-error", Static).content))
            self.assertIsNone(app.current_task)
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_ENTRY)

    async def test_submit_entry_form_requires_input_type_when_select_is_blank(self):
        """确认输入类型为空但文本非空时提示选择输入类型且不创建任务。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            app.query_one("#input-type-select", Select).clear()
            app.query_one("#batch-input", TextArea).text = "2508.18791"

            app.submit_entry_form()

            self.assertIn("请选择输入类型", str(app.query_one("#entry-error", Static).content))
            self.assertIsNone(app.current_task)
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_ENTRY)


class TuiTaskProjectSemanticsTests(unittest.IsolatedAsyncioTestCase):
    """验证任务历史和项目列表遵循一次提交一个任务的语义。"""

    async def test_sequential_single_id_tasks_keep_both_projects_in_sidebar(self):
        """确认连续提交两个单项目任务后，侧栏项目列表不会丢失第一个项目。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)

        async with app.run_test() as pilot:
            for arxiv_id in ["2308.10248", "2311.06668"]:
                app.query_one("#input-type-select", Select).value = "arxiv"
                app.query_one("#batch-input", TextArea).text = arxiv_id
                with patch.object(app, "start_current_task"):
                    app.submit_entry_form()
                app.handle_runtime_event(
                    {"type": "project_complete", "project_name": arxiv_id},
                    app.current_task,
                )

            await pilot.pause()
            list_view = app.query_one("#project-list", ListView)
            labels = [str(item.query_one(Static).content) for item in list_view.children]

            self.assertEqual(len(app.tasks), 2)
            self.assertEqual(len(list_view.children), 2)
            self.assertIn("2308.10248", labels[0])
            self.assertIn("2311.06668", labels[1])

    async def test_batch_ids_are_one_task_with_multiple_project_rows(self):
        """确认一次输入多个 ID 会创建一个任务，并在项目管理中展开多个项目。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)

        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "arxiv"
            app.query_one("#batch-input", TextArea).text = "2308.10248\n2311.06668"
            with patch.object(app, "start_current_task"):
                app.submit_entry_form()

            task = app.current_task
            app.handle_runtime_event({"type": "project_start", "project_name": "2308.10248"}, task)
            app.handle_runtime_event({"type": "project_complete", "project_name": "2308.10248"}, task)
            app.handle_runtime_event({"type": "project_start", "project_name": "2311.06668"}, task)

            table = app.query_one("#task-table", DataTable)

            self.assertEqual(len(app.tasks), 1)
            self.assertEqual(str(table.ordered_columns[0].label), "项目")
            self.assertEqual(str(table.ordered_columns[1].label), "状态")
            self.assertEqual(str(table.ordered_columns[2].label), "任务 id")
            self.assertEqual(len(table.ordered_columns), 3)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(table.get_cell_at((0, 2)), task.task_id)
            self.assertEqual(table.get_cell_at((1, 2)), task.task_id)

    async def test_sidebar_selection_uses_project_task_identity(self):
        """确认侧栏选择项目时按任务 id 和项目名定位详情。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)

        async with app.run_test():
            first_task = TaskViewState(input_type="arxiv", inputs=["paper"], task_id="task-1")
            first_task.projects.append(ProjectViewState(project_name="paper", status=ProjectStatus.COMPLETED))
            second_task = TaskViewState(input_type="arxiv", inputs=["paper"], task_id="task-2")
            second_task.projects.append(ProjectViewState(project_name="paper", status=ProjectStatus.RUNNING))
            app.tasks = [first_task, second_task]
            app.current_task = second_task
            app.refresh_project_list()

            event = Mock()
            event.list_view = app.query_one("#project-list", ListView)
            event.index = 1
            app.on_list_view_selected(event)

            self.assertEqual(app.selected_task_id, "task-2")
            self.assertEqual(app.selected_project_name, "paper")
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_DETAIL)

    async def test_mount_loads_existing_outputs_into_sidebar(self):
        """确认打开 TUI 时左侧列表会包含 outputs 中已有项目。"""
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            project_dir = output_root / "ch_2308.10248"
            project_dir.mkdir(parents=True)
            (project_dir / "ch_2308.10248.pdf").write_bytes(b"%PDF")
            (project_dir / "errors_report.json").write_text("[]", encoding="utf-8")

            app = LaTeXTransTuiApp()
            with patch.object(LaTeXTransTuiApp, "_history_output_root", return_value=output_root):
                async with app.run_test() as pilot:
                    await pilot.pause()

                    list_view = app.query_one("#project-list", ListView)
                    table = app.query_one("#task-table", DataTable)

                    self.assertEqual(len(list_view.children), 1)
                    self.assertIn("2308.10248", str(list_view.children[0].query_one(Static).content))
                    self.assertEqual(table.get_cell_at((0, 0)), "2308.10248")
                    self.assertEqual(table.get_cell_at((0, 1)), "completed")
                    self.assertEqual(table.get_cell_at((0, 2)), "")

    async def test_selecting_history_project_loads_tex_preview(self):
        """确认点击历史项目时右侧 TeX 页能显示项目源码。"""
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            project_dir = output_root / "ch_2308.10248"
            source_dir = project_dir / "2308.10248"
            source_dir.mkdir(parents=True)
            (source_dir / "main.tex").write_text("\\documentclass{article}", encoding="utf-8")
            (project_dir / "errors_report.json").write_text("[]", encoding="utf-8")
            (project_dir / "ch_2308.10248.pdf").write_bytes(b"%PDF")

            app = LaTeXTransTuiApp()
            with patch.object(LaTeXTransTuiApp, "_history_output_root", return_value=output_root):
                async with app.run_test() as pilot:
                    await pilot.pause()
                    app.select_project("2308.10248")
                    await pilot.pause()

                    self.assertIn("\\documentclass{article}", app.query_one("#tex-preview", TextArea).text)
                    self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_DETAIL)

    async def test_submit_entry_form_uses_timestamp_task_id(self):
        """确认新任务 id 使用时间戳格式而不是递增序号。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)

        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "arxiv"
            app.query_one("#batch-input", TextArea).text = "2308.10248"
            with patch.object(app, "start_current_task"), patch(
                "src.tui.app.datetime"
            ) as datetime_module:
                datetime_module.now.return_value.strftime.return_value = "20260701T175144.123000"
                app.submit_entry_form()

            self.assertEqual(app.current_task.task_id, "20260701T175144.123")

    async def test_project_completion_writes_tui_metadata(self):
        """确认新版项目完成事件会在输出目录写入 TUI 元数据。"""
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "outputs" / "ch_2308.10248"
            output_dir.mkdir(parents=True)
            app = LaTeXTransTuiApp(load_history_on_mount=False)

            async with app.run_test():
                app.current_task = TaskViewState(
                    input_type="arxiv",
                    inputs=["2308.10248"],
                    task_id="20260701T175144.123",
                )
                app.tasks = [app.current_task]

                app.handle_runtime_event(
                    {
                        "type": "project_complete",
                        "project_name": "2308.10248",
                        "output_dir": str(output_dir),
                    },
                    app.current_task,
                )

            self.assertTrue((output_dir / TUI_PROJECT_METADATA_FILENAME).is_file())


class TuiConfigPageTests(unittest.IsolatedAsyncioTestCase):
    """验证配置页会加载、编辑并保存 UI 配置。"""

    async def test_settings_button_loads_structured_config_tabs(self):
        """确认设置按钮会打开配置 tabs 并按字段类型填充表单。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        config = {
            "sys_name": "LaTeXTransPlus",
            "version": "0.1.0",
            "source_language": "en",
            "target_language": "ja",
            "paper_list": ["2508.18791", "2407.01648"],
            "tex_sources_dir": "tex source",
            "output_dir": "outputs",
            "category": {"cs": ["cs.LG"]},
            "update_term": "True",
            "mode": "plain",
            "user_term": "terms/user.csv",
            "terminology": {
                "enabled": True,
                "review_before_translate": False,
                "max_llm_candidates": 30,
            },
            "validation": {
                "retry": {
                    "max_attempts": 3,
                    "generate_pdf_on_error": True,
                    "fail_on_error": True,
                },
                "issues": {
                    "command_mismatch": {"severity": "error", "retryable": True},
                    "placeholder_mismatch": {"severity": "warning", "retryable": False},
                    "bracket_mismatch": {"severity": "error", "retryable": True},
                },
            },
            "llm_config": {
                "model": "deepseek-v4-flash",
                "api_key_env": "DEEPSEEK_API_KEY",
                "base_url": "https://api.deepseek.com/chat/completions",
            },
        }
        async with app.run_test() as pilot:
            with patch("src.tui.app.load_ui_config", return_value=config):
                await pilot.click("#settings-button")

            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_CONFIG)
            self.assertIsNotNone(app.query_one("#config-tabs", TabbedContent))
            self.assertEqual(app.query_one("#config-target_language", Select).value, "ja")
            self.assertEqual(app.query_one("#config-source_language", Select).value, "en")
            self.assertEqual(app.query_one("#config-paper_list", TextArea).text, "2508.18791\n2407.01648")
            self.assertTrue(app.query_one("#config-update_term", Switch).value)
            self.assertEqual(app.query_one("#config-validation-issues-placeholder_mismatch-severity", Select).value, "warning")
            self.assertFalse(app.query_one("#config-validation-issues-placeholder_mismatch-retryable", Switch).value)
            self.assertIn('target_language = "ja"', app.query_one("#config-preview", TextArea).text)
            with self.assertRaises(NoMatches):
                app.query_one("#config-sys_name", Input)
            with self.assertRaises(NoMatches):
                app.query_one("#config-version", Input)

    async def test_config_page_has_no_manual_save_or_reload_buttons(self):
        """确认配置页不再提供保存或重载按钮，避免手动保存语义漂移。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            self.assertIsNotNone(app.query_one("#config-tabs", TabbedContent))
            with self.assertRaises(NoMatches):
                app.query_one("#save-config-button")
            with self.assertRaises(NoMatches):
                app.query_one("#reload-config-button")

    async def test_config_field_change_persists_immediately_and_refreshes_preview(self):
        """确认配置字段变化后会即时保存 UI 配置并刷新 TOML 预览。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            with patch("src.tui.app.load_ui_config", return_value={"target_language": "ja"}):
                app.load_config_page()

            app.query_one("#config-target_language", Select).value = "fr"
            with patch("src.tui.app.save_ui_config") as save_config:
                app.persist_config_form_change()

            self.assertEqual(save_config.call_args.args[1]["target_language"], "fr")
            preview = app.query_one("#config-preview", TextArea).text
            self.assertIn('target_language = "fr"', preview)

    async def test_config_change_collects_form_fields_and_preserves_metadata(self):
        """确认即时保存会从结构化表单写回配置并保留不可编辑元数据。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        config = {
            "sys_name": "LaTeXTransPlus",
            "version": "0.1.0",
            "source_language": "en",
            "target_language": "ja",
            "paper_list": [],
            "tex_sources_dir": "tex source",
            "output_dir": "outputs",
            "category": {},
            "update_term": "False",
            "mode": "plain",
            "user_term": "",
            "terminology": {"enabled": True, "review_before_translate": False, "max_llm_candidates": 30},
            "validation": {
                "retry": {"max_attempts": 3, "generate_pdf_on_error": True, "fail_on_error": True},
                "issues": {
                    "command_mismatch": {"severity": "error", "retryable": True},
                    "placeholder_mismatch": {"severity": "error", "retryable": True},
                    "bracket_mismatch": {"severity": "error", "retryable": True},
                },
            },
            "llm_config": {"model": "deepseek-v4-flash", "api_key_env": "DEEPSEEK_API_KEY", "base_url": ""},
        }
        async with app.run_test():
            with patch("src.tui.app.load_ui_config", return_value=config):
                app.load_config_page()

            app.query_one("#config-target_language", Select).value = "fr"
            app.query_one("#config-source_language", Select).value = "de"
            app.query_one("#config-paper_list", TextArea).text = "2508.18791\n2407.01648\n"
            app.query_one("#config-category", TextArea).text = '{"cs": ["cs.LG"]}'
            app.query_one("#config-update_term", Switch).value = True
            app.query_one("#config-terminology-max_llm_candidates", Input).value = "12"
            app.query_one("#config-validation-retry-max_attempts", Input).value = "2"
            app.query_one("#config-validation-issues-command_mismatch-severity", Select).value = "warning"
            app.query_one("#config-validation-issues-command_mismatch-retryable", Switch).value = False
            app.query_one("#config-llm_config-model", Input).value = "model-x"
            with patch("src.tui.app.save_ui_config") as save_config:
                app.persist_config_form_change()

            saved = save_config.call_args.args[1]
            self.assertEqual(saved["sys_name"], "LaTeXTransPlus")
            self.assertEqual(saved["version"], "0.1.0")
            self.assertEqual(saved["target_language"], "fr")
            self.assertEqual(saved["source_language"], "de")
            self.assertEqual(saved["paper_list"], ["2508.18791", "2407.01648"])
            self.assertEqual(saved["category"], {"cs": ["cs.LG"]})
            self.assertEqual(saved["update_term"], "True")
            self.assertEqual(saved["terminology"]["max_llm_candidates"], 12)
            self.assertEqual(saved["validation"]["retry"]["max_attempts"], 2)
            self.assertEqual(saved["validation"]["issues"]["command_mismatch"]["severity"], "warning")
            self.assertFalse(saved["validation"]["issues"]["command_mismatch"]["retryable"])
            self.assertEqual(saved["llm_config"]["model"], "model-x")
            self.assertIn('target_language = "fr"', app.query_one("#config-preview", TextArea).text)

    async def test_config_change_rejects_invalid_integer_fields(self):
        """确认非法整数配置会显示错误并阻止即时保存。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            with patch("src.tui.app.load_ui_config", return_value={"terminology": {"max_llm_candidates": 30}}):
                app.load_config_page()

            app.query_one("#config-terminology-max_llm_candidates", Input).value = "-1"
            with patch("src.tui.app.save_ui_config") as save_config:
                app.persist_config_form_change()

            save_config.assert_not_called()
            self.assertIn("非负整数", str(app.query_one("#config-error", Static).content))


class TuiProgressTests(unittest.IsolatedAsyncioTestCase):
    """验证任务进度页会响应 runtime 事件。"""

    async def test_handle_runtime_event_updates_task_and_log(self):
        """确认 runtime 事件会更新当前任务状态并写入日志控件。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])

            app.handle_runtime_event({"type": "run_start", "total": 1})
            app.handle_runtime_event({"type": "project_start", "project_name": "2508.18791"})
            app.handle_runtime_event(
                {"type": "project_complete", "project_name": "2508.18791", "pdf_path": "paper.pdf"}
            )

            self.assertEqual(app.current_task.completed, 1)
            self.assertGreaterEqual(len(app.current_task.events), 3)
            progress_bar = app.query_one("#task-progress", ProgressBar)
            self.assertEqual(progress_bar.total, 1)
            self.assertEqual(progress_bar.progress, 1)
            self.assertIsNotNone(app.query_one("#event-log", RichLog))

    async def test_start_current_task_initializes_total_without_run_start(self):
        """确认真实启动路径不依赖 runner 发送 run_start 也会初始化总数。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)

        def fake_runner(**kwargs):
            """模拟 runner 只发送项目完成事件，避免真实下载或翻译。"""
            kwargs["event_callback"](
                {"type": "project_complete", "project_name": "2508.18791", "pdf_path": "paper.pdf"}
            )
            return {"completed_projects": ["2508.18791"], "failed_projects": []}

        async with app.run_test() as pilot:
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])

            with patch("src.tui.app.run_tui_task", side_effect=fake_runner) as runner:
                app.start_current_task()
                await app.workers.wait_for_complete()
                await pilot.pause()

            runner.assert_called_once()
            call_kwargs = runner.call_args.kwargs
            self.assertEqual(call_kwargs["input_type"], "arxiv")
            self.assertEqual(call_kwargs["items"], ["2508.18791"])
            self.assertEqual(app.current_task.completed, 1)
            progress_bar = app.query_one("#task-progress", ProgressBar)
            self.assertEqual(app.current_task.total, 1)
            self.assertEqual(progress_bar.total, 1)
            self.assertEqual(progress_bar.progress, 1)

    async def test_stale_worker_events_do_not_update_new_current_task(self):
        """确认旧任务 worker 回调不会污染新的 current_task。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            old_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"], total=1)
            new_task = TaskViewState(input_type="arxiv", inputs=["2407.01648"], total=1)
            app.current_task = old_task
            app.current_task = new_task

            app.handle_runtime_event(
                {"type": "project_complete", "project_name": "2508.18791", "pdf_path": "old.pdf"},
                old_task,
            )

            self.assertEqual(old_task.completed, 0)
            self.assertEqual(new_task.completed, 0)
            self.assertEqual(new_task.events, [])

    async def test_worker_exception_is_reported_in_current_task(self):
        """确认 runner 异常会转成当前任务的可见失败事件。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)

        def failing_runner(**kwargs):
            """模拟 runner 抛出异常，避免真实下载或翻译。"""
            raise RuntimeError("runner failed")

        async with app.run_test() as pilot:
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])

            with patch("src.tui.app.run_tui_task", side_effect=failing_runner):
                app.start_current_task()
                await app.workers.wait_for_complete()
                await pilot.pause()

            self.assertEqual(app.current_task.failed, 1)
            self.assertEqual(app.current_task.total, 1)
            self.assertIn("runner failed", str(app.query_one("#progress-summary", Static).content))
            self.assertEqual(app.query_one("#task-progress", ProgressBar).progress, 1)
            self.assertTrue(any("runner failed" in str(event) for event in app.current_task.events))

    async def test_remote_prepare_failure_does_not_remap_error_to_input_url(self):
        """确认 remote prepare 全失败后不会再补发绑定到输入 URL 的 project_error。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        remote_inputs = [
            "https://example.test/first.zip",
            "https://example.test/second.zip",
        ]

        def failing_remote_runner(**kwargs):
            """模拟 remote prepare 全失败时 runner 先发 run_start total=0 再抛错。"""
            kwargs["event_callback"]({"type": "run_start", "total": 0})
            raise RuntimeError("No valid TeX projects available for processing.")

        async with app.run_test() as pilot:
            app.current_task = TaskViewState(input_type="remote", inputs=remote_inputs)

            with patch("src.tui.app.run_tui_task", side_effect=failing_remote_runner):
                app.start_current_task()
                await app.workers.wait_for_complete()
                await pilot.pause()

            self.assertEqual(app.current_task.total, 0)
            self.assertEqual(app.current_task.failed, 0)
            self.assertEqual(app.current_task.projects, [])
            self.assertEqual(app.current_task.events, [{"type": "run_start", "total": 0}])
            self.assertFalse(
                any(project.project_name in remote_inputs for project in app.current_task.projects)
            )


class TuiResultViewsTests(unittest.IsolatedAsyncioTestCase):
    """验证任务结果列表、表格和项目详情页会读取项目状态。"""

    async def test_select_project_updates_detail_page(self):
        """确认选择项目会记录名称并切换到详情页。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
            app.current_task.projects.append(
                ProjectViewState(
                    project_name="paper",
                    status=ProjectStatus.COMPLETED,
                    output_dir="outputs/ch_paper",
                    pdf_path="paper.pdf",
                )
            )

            app.select_project("paper")

            self.assertEqual(app.selected_project_name, "paper")
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_DETAIL)
            self.assertIn("paper.pdf", str(app.query_one("#detail-paths", Static).content))

    async def test_refresh_task_table_adds_project_rows(self):
        """确认任务管理表会展示当前任务下的项目行。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test():
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
            app.current_task.projects.append(ProjectViewState(project_name="paper", status=ProjectStatus.COMPLETED))

            app.refresh_task_table()

            table = app.query_one("#task-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(table.get_cell_at((0, 0)), "paper")
            self.assertEqual(table.get_cell_at((0, 1)), "completed")

    async def test_refresh_project_list_adds_selectable_items(self):
        """确认侧栏项目列表会展示当前任务下的项目。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        async with app.run_test() as pilot:
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
            app.current_task.projects.append(ProjectViewState(project_name="paper", status=ProjectStatus.RUNNING))

            app.refresh_project_list()
            await pilot.pause()

            list_view = app.query_one("#project-list", ListView)
            self.assertEqual(len(list_view.children), 1)
            self.assertIn("paper", str(list_view.children[0].query_one(Static).content))

    async def test_refresh_detail_page_populates_project_artifacts(self):
        """确认详情页会展示路径、错误、日志，并保持 TeX 预览只读。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            tex_file = project_dir / "main.tex"
            log_file = project_dir / "paper.log"
            tex_file.write_text("\\section{Result}", encoding="utf-8")
            log_file.write_text("compile ok", encoding="utf-8")

            async with app.run_test() as pilot:
                app.current_task = TaskViewState(input_type="local", inputs=[str(project_dir)])
                app.current_task.projects.append(
                    ProjectViewState(
                        project_name="paper",
                        status=ProjectStatus.FAILED,
                        project_dir=str(project_dir),
                        output_dir=str(project_dir / "out"),
                        pdf_path=str(project_dir / "paper.pdf"),
                        errors_report_path=str(project_dir / "errors.md"),
                        log_path=str(log_file),
                        error="compile failed",
                    )
                )
                app.selected_project_name = "paper"

                app.refresh_detail_page()
                await pilot.pause()

                self.assertIn("paper.pdf", str(app.query_one("#detail-paths", Static).content))
                self.assertIn("compile failed", str(app.query_one("#detail-paths", Static).content))
                tex_preview = app.query_one("#tex-preview", TextArea)
                self.assertTrue(tex_preview.read_only)
                self.assertIn("\\section{Result}", tex_preview.text)
                self.assertIn("compile ok", str(app.query_one("#project-log-summary", Static).content))
                errors_table = app.query_one("#errors-table", DataTable)
                self.assertEqual(errors_table.row_count, 1)
                self.assertEqual(errors_table.get_cell_at((0, 0)), str(project_dir / "errors.md"))
                self.assertEqual(errors_table.get_cell_at((0, 1)), "compile failed")

    async def test_refresh_detail_page_populates_terms_table(self):
        """确认详情页会从项目状态中的术语表路径渲染术语行和路径。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            terms_path = project_dir / "project_terms.csv"
            decisions_path = project_dir / "project_terms_decisions.json"
            terms_path.write_text(
                "Source Term,Target Translation\nGraph,图\nModel,模型\n",
                encoding="utf-8",
            )
            decisions_path.write_text('{"decisions": []}', encoding="utf-8")

            async with app.run_test():
                app.current_task = TaskViewState(input_type="local", inputs=[str(project_dir)])
                app.current_task.projects.append(
                    ProjectViewState(
                        project_name="paper",
                        status=ProjectStatus.COMPLETED,
                        project_terms_path=str(terms_path),
                        project_terms_decisions_path=str(decisions_path),
                    )
                )
                app.selected_project_name = "paper"

                app.refresh_detail_page()

                terms_table = app.query_one("#terms-table", DataTable)
                self.assertEqual(terms_table.row_count, 4)
                self.assertEqual(terms_table.get_cell_at((0, 0)), "术语表路径")
                self.assertEqual(terms_table.get_cell_at((0, 1)), str(terms_path))
                self.assertEqual(terms_table.get_cell_at((1, 0)), "决策记录路径")
                self.assertEqual(terms_table.get_cell_at((1, 1)), str(decisions_path))
                self.assertEqual(terms_table.get_cell_at((2, 0)), "Graph")
                self.assertEqual(terms_table.get_cell_at((2, 1)), "图")


class TuiZoteroImportTests(unittest.IsolatedAsyncioTestCase):
    """验证 Zotero 导入按钮只对选中项目的 PDF 调用 adapter 并反馈状态。"""

    async def test_import_zotero_button_attaches_selected_project_pdf(self):
        """确认导入 Zotero 按钮会用显式条目信息附加当前项目 PDF。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        adapter = Mock()
        adapter.attach_pdf.return_value = {"attachment_key": "ATTACH1", "status": "uploaded"}

        async with app.run_test() as pilot:
            app.zotero_adapter_factory = lambda api_key, script_path: adapter
            app.current_task = TaskViewState(input_type="local", inputs=["paper"])
            app.current_task.projects.append(
                ProjectViewState(
                    project_name="paper",
                    status=ProjectStatus.COMPLETED,
                    pdf_path=r"D:\out\paper.pdf",
                )
            )
            app.selected_project_name = "paper"
            app.switch_page(PAGE_DETAIL)
            app.query_one("#zotero-api-key-input", Input).value = "ui-key"
            app.query_one("#zotero-script-path-input", Input).value = "zotero.py"
            app.query_one("#zotero-library-id-input", Input).value = "42"
            app.query_one("#zotero-library-type-select", Select).value = "group"
            app.query_one("#zotero-item-key-input", Input).value = "ITEM123"

            app.import_selected_project_to_zotero()

            adapter.attach_pdf.assert_called_once_with("ITEM123", r"D:\out\paper.pdf", "42", "group")
            project = app.current_task.projects[0]
            self.assertEqual(project.zotero_status, "uploaded: ATTACH1")
            self.assertIn("uploaded", str(app.query_one("#zotero-status", Static).content))

    async def test_import_zotero_button_reports_failure_without_changing_task_result(self):
        """确认 Zotero 导入失败会展示错误，但不改变翻译完成状态。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        adapter = Mock()
        adapter.attach_pdf.side_effect = RuntimeError("zotero failed")

        async with app.run_test() as pilot:
            app.zotero_adapter_factory = lambda api_key, script_path: adapter
            app.current_task = TaskViewState(input_type="local", inputs=["paper"])
            app.current_task.projects.append(
                ProjectViewState(
                    project_name="paper",
                    status=ProjectStatus.COMPLETED,
                    pdf_path=r"D:\out\paper.pdf",
                )
            )
            app.current_task.completed = 1
            app.selected_project_name = "paper"
            app.switch_page(PAGE_DETAIL)
            app.query_one("#zotero-api-key-input", Input).value = "ui-key"
            app.query_one("#zotero-script-path-input", Input).value = "zotero.py"
            app.query_one("#zotero-library-id-input", Input).value = "42"
            app.query_one("#zotero-library-type-select", Select).value = "group"
            app.query_one("#zotero-item-key-input", Input).value = "ITEM123"

            app.import_selected_project_to_zotero()

            project = app.current_task.projects[0]
            self.assertEqual(project.status, ProjectStatus.COMPLETED)
            self.assertEqual(app.current_task.completed, 1)
            self.assertIn("失败", project.zotero_status)
            self.assertIn("zotero failed", str(app.query_one("#zotero-status", Static).content))

    async def test_import_zotero_button_branch_calls_import_method(self):
        """确认 Zotero 按钮分支会同步调用导入方法。"""
        app = LaTeXTransTuiApp(load_history_on_mount=False)
        event = Mock()
        event.button.id = "import-zotero-button"

        async with app.run_test():
            with patch.object(app, "import_selected_project_to_zotero") as import_method:
                app.on_button_pressed(event)

        import_method.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
