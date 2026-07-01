import unittest

from setup import load_requirements


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


if __name__ == "__main__":
    unittest.main()
