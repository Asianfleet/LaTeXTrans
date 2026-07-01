import unittest

from setup import load_requirements


class TuiPackagingTests(unittest.TestCase):
    def test_textual_dependency_is_declared(self):
        requirements = load_requirements("requirements.txt")
        self.assertTrue(any(item.startswith("textual") for item in requirements))

    def test_tui_run_function_is_importable(self):
        from src.tui.app import run

        self.assertTrue(callable(run))


if __name__ == "__main__":
    unittest.main()
