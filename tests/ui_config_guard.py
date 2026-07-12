"""测试期间保护真实 UI 配置文件不被污染。"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from pathlib import Path


class RealUiConfigProtectionMixin:
    """在每个测试前后检测并恢复真实 config/ui.toml。"""

    def setUp(self) -> None:
        """记录真实 UI 配置文件的测试前状态。"""
        super().setUp()
        self._real_ui_config_snapshot = _snapshot_real_ui_config()

    def tearDown(self) -> None:
        """检测测试是否污染真实 UI 配置文件，并在失败前恢复原状态。"""
        try:
            changed = self._restore_real_ui_config_if_changed()
            if changed:
                self.fail("测试意外修改了真实 config/ui.toml")
        finally:
            super().tearDown()

    def _restore_real_ui_config_if_changed(self) -> bool:
        """如果真实 UI 配置发生变化则恢复，并返回是否检测到变化。"""
        return _restore_real_ui_config_if_changed(self._real_ui_config_snapshot)


@contextmanager
def protect_real_ui_config(test_case: unittest.TestCase):
    """在一段测试代码周围检测并恢复真实 UI 配置文件。"""
    snapshot = _snapshot_real_ui_config()
    try:
        yield
    finally:
        changed = _restore_real_ui_config_if_changed(snapshot)
    if changed:
        test_case.fail("测试意外修改了真实 config/ui.toml")


@contextmanager
def temporary_cwd(path: Path):
    """在测试期间切换工作目录，并在退出时恢复原目录。"""
    previous_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous_cwd)


def _snapshot_real_ui_config() -> tuple[Path, bool, bytes | None]:
    """读取真实 UI 配置文件的存在状态和原始字节。"""
    ui_config_path = Path.cwd() / "config" / "ui.toml"
    existed = ui_config_path.exists()
    content = ui_config_path.read_bytes() if existed else None
    return ui_config_path, existed, content


def _restore_real_ui_config_if_changed(
    snapshot: tuple[Path, bool, bytes | None],
) -> bool:
    """检测真实 UI 配置是否变化，变化时恢复原始字节并返回 True。"""
    ui_config_path, existed_before, original_content = snapshot
    exists_after = ui_config_path.exists()
    current_content = ui_config_path.read_bytes() if exists_after else None
    changed = (
        existed_before != exists_after
        or (existed_before and current_content != original_content)
    )
    if not changed:
        return False

    if existed_before and original_content is not None:
        ui_config_path.parent.mkdir(parents=True, exist_ok=True)
        ui_config_path.write_bytes(original_content)
    elif exists_after:
        ui_config_path.unlink()
    return True
