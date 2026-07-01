import unittest
from unittest.mock import patch

from textual.widgets import ContentSwitcher, Footer, ListView, ProgressBar, RichLog, Select, Static, TextArea

from setup import load_requirements
from src.tui.app import (
    PAGE_CONFIG,
    PAGE_DETAIL,
    PAGE_ENTRY,
    PAGE_PROGRESS,
    PAGE_TASKS,
    LaTeXTransTuiApp,
)
from src.tui.state import TaskViewState


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
        app = LaTeXTransTuiApp()
        async with app.run_test():
            self.assertIsNotNone(app.query_one("#project-list", ListView))
            self.assertIsNotNone(app.query_one("#main-switcher", ContentSwitcher))
            self.assertIsNotNone(app.query_one(Footer))

    async def test_switch_page_updates_content_switcher(self):
        """确认 switch_page 会更新主内容切换器当前页面。"""
        app = LaTeXTransTuiApp()
        async with app.run_test():
            for page_id in [PAGE_ENTRY, PAGE_PROGRESS, PAGE_DETAIL, PAGE_TASKS, PAGE_CONFIG]:
                app.switch_page(page_id)
                self.assertEqual(
                    app.query_one("#main-switcher", ContentSwitcher).current,
                    page_id,
                )


class TuiEntryPageTests(unittest.IsolatedAsyncioTestCase):
    """验证入口页提交会创建任务状态并展示校验错误。"""

    async def test_submit_entry_form_creates_task_and_switches_to_progress(self):
        """确认有效入口表单会创建任务状态并切换到进度页。"""
        app = LaTeXTransTuiApp()
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
        app = LaTeXTransTuiApp()
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
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "remote"
            app.query_one("#batch-input", TextArea).text = "file:///bad.zip"

            app.submit_entry_form()

            self.assertIn("remote input must be", str(app.query_one("#entry-error", Static).content))
            self.assertIsNone(app.current_task)
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_ENTRY)

    async def test_submit_entry_form_requires_input_type_when_select_is_blank(self):
        """确认输入类型为空但文本非空时提示选择输入类型且不创建任务。"""
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.query_one("#input-type-select", Select).clear()
            app.query_one("#batch-input", TextArea).text = "2508.18791"

            app.submit_entry_form()

            self.assertIn("请选择输入类型", str(app.query_one("#entry-error", Static).content))
            self.assertIsNone(app.current_task)
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_ENTRY)


class TuiProgressTests(unittest.IsolatedAsyncioTestCase):
    """验证任务进度页会响应 runtime 事件。"""

    async def test_handle_runtime_event_updates_task_and_log(self):
        """确认 runtime 事件会更新当前任务状态并写入日志控件。"""
        app = LaTeXTransTuiApp()
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
        app = LaTeXTransTuiApp()

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
        app = LaTeXTransTuiApp()
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
        app = LaTeXTransTuiApp()

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


if __name__ == "__main__":
    unittest.main()
