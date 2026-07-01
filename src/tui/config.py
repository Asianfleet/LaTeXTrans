"""TUI 专用配置文件的初始化、加载和保存。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import toml

UI_CONFIG_PATH = Path("config") / "ui.toml"


def ensure_ui_config(project_root: Path) -> Path:
    """确保 UI 配置文件存在，并返回其路径。"""
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    ui_path = project_root / UI_CONFIG_PATH
    if ui_path.exists():
        return ui_path

    default_path = config_dir / "default.toml"
    template_path = config_dir / "template.toml"
    source_path = default_path if default_path.exists() else template_path
    if not source_path.exists():
        raise FileNotFoundError("Missing config/default.toml and config/template.toml.")

    shutil.copyfile(source_path, ui_path)
    return ui_path


def load_ui_config(project_root: Path) -> dict[str, Any]:
    """加载 UI 配置，必要时先从默认配置或模板初始化。"""
    return toml.load(ensure_ui_config(project_root))


def save_ui_config(project_root: Path, config: dict[str, Any]) -> Path:
    """将 UI 配置保存到 config/ui.toml，并返回保存路径。"""
    ui_path = project_root / UI_CONFIG_PATH
    ui_path.parent.mkdir(parents=True, exist_ok=True)
    ui_path.write_text(toml.dumps(config), encoding="utf-8")
    return ui_path
