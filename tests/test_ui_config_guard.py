"""真实 UI 配置保护工具的测试。"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.ui_config_guard import protect_real_ui_config, temporary_cwd


class UiConfigGuardTests(unittest.TestCase):
    """验证测试保护工具能检测并恢复 UI 配置污染。"""

    def test_protect_real_ui_config_detects_and_restores_changes(self):
        """确认保护上下文会报告并恢复 config/ui.toml 的意外修改。"""
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            ui_config_path = project_root / "config" / "ui.toml"
            ui_config_path.parent.mkdir()
            ui_config_path.write_text('target_language = "sentinel"\n', encoding="utf-8")
            original_content = ui_config_path.read_text(encoding="utf-8")

            with temporary_cwd(project_root):
                with self.assertRaises(AssertionError):
                    with protect_real_ui_config(self):
                        ui_config_path.write_text('target_language = "changed"\n', encoding="utf-8")

            self.assertEqual(ui_config_path.read_text(encoding="utf-8"), original_content)
