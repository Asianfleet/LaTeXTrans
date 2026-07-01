import unittest

from textual.widgets import ContentSwitcher, Footer, ListView

from setup import load_requirements
from src.tui.app import (
    PAGE_CONFIG,
    PAGE_DETAIL,
    PAGE_ENTRY,
    PAGE_PROGRESS,
    PAGE_TASKS,
    LaTeXTransTuiApp,
)


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


if __name__ == "__main__":
    unittest.main()
