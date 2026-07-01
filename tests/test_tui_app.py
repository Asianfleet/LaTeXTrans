import unittest

from textual.widgets import ContentSwitcher, Footer, ListView, Select, Static, TextArea

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

            app.submit_entry_form()

            self.assertIsInstance(app.current_task, TaskViewState)
            self.assertEqual(app.current_task.inputs, ["2508.18791", "2407.01648"])
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_PROGRESS)

    async def test_start_button_submits_entry_form(self):
        """确认开始按钮会提交入口表单并进入进度页。"""
        app = LaTeXTransTuiApp()
        async with app.run_test() as pilot:
            app.query_one("#input-type-select", Select).value = "arxiv"
            app.query_one("#batch-input", TextArea).text = "2508.18791"

            await pilot.click("#start-task-button")

            self.assertIsInstance(app.current_task, TaskViewState)
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_PROGRESS)

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


if __name__ == "__main__":
    unittest.main()
