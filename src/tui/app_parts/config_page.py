"""Configuration page behavior for the Textual TUI app."""

from __future__ import annotations

import sys
from pathlib import Path

import toml
from textual.css.query import NoMatches
from textual.widgets import Input, Select, Static, Switch, TextArea

from src.tui.config import load_ui_config, save_ui_config
from src.tui.config_schema import (
    CONFIG_FIELDS,
    bool_for_field,
    form_text_for_field,
    normalized_config_from_form,
    parse_integer_value,
    parse_textarea_value,
    select_value_for_field,
)


class ConfigPageMixin:
    """Load, collect, persist, and preview UI configuration form values."""

    def load_config_page(self) -> None:
        """将 UI 配置加载到结构化表单和 TOML 预览区。"""
        config = self._load_ui_config()(Path.cwd())
        self.current_config = dict(config)
        self.loading_config_form = True
        try:
            self._populate_config_form(config)
        finally:
            self.loading_config_form = False
        self._update_config_preview(config)
        self.query_one("#config-error", Static).update("")

    def persist_config_form_change(self) -> None:
        """从当前表单刷新 TOML 预览并立即保存 UI 配置。"""
        if self.loading_config_form:
            return
        try:
            config = self._config_from_form()
        except NoMatches:
            return
        except ValueError as exc:
            self.query_one("#config-error", Static).update(str(exc))
            return
        self._save_ui_config()(Path.cwd(), config)
        self.current_config = dict(config)
        self._update_config_preview(config)
        self.query_one("#config-error", Static).update("")

    def _load_ui_config(self):
        """返回配置加载函数，优先复用 app 模块上的可 patch 入口。"""
        app_module = sys.modules.get("src.tui.app")
        if app_module is not None and hasattr(app_module, "load_ui_config"):
            return app_module.load_ui_config
        return load_ui_config

    def _save_ui_config(self):
        """返回配置保存函数，优先复用 app 模块上的可 patch 入口。"""
        app_module = sys.modules.get("src.tui.app")
        if app_module is not None and hasattr(app_module, "save_ui_config"):
            return app_module.save_ui_config
        return save_ui_config

    def _is_config_widget(self, widget_id: str | None) -> bool:
        """判断事件来源是否为设置页配置控件。"""
        return bool(widget_id and widget_id.startswith("config-") and widget_id != "config-preview")

    def _config_from_form(self) -> dict[str, object]:
        """将当前表单转换为完整配置对象。"""
        values = self._collect_config_form_values()
        return normalized_config_from_form(dict(self.current_config), values)

    def _populate_config_form(self, config: dict[str, object]) -> None:
        """把配置值填入设置页表单控件。"""
        for field in CONFIG_FIELDS:
            if field.kind == "select":
                self.query_one(f"#{field.widget_id}", Select).value = select_value_for_field(field, config)
            elif field.kind == "switch":
                self.query_one(f"#{field.widget_id}", Switch).value = bool_for_field(field, config)
            elif field.kind == "textarea":
                self.query_one(f"#{field.widget_id}", TextArea).text = form_text_for_field(field, config)
            else:
                self.query_one(f"#{field.widget_id}", Input).value = form_text_for_field(field, config)

    def _collect_config_form_values(self) -> dict[tuple[str, ...], object]:
        """从设置页表单控件读取并校验配置值。"""
        values: dict[tuple[str, ...], object] = {}
        for field in CONFIG_FIELDS:
            if field.kind == "select":
                select = self.query_one(f"#{field.widget_id}", Select)
                values[field.path] = "" if select.is_blank() else str(select.value)
            elif field.kind == "switch":
                value = self.query_one(f"#{field.widget_id}", Switch).value
                values[field.path] = "True" if field.path == ("update_term",) and value else (
                    "False" if field.path == ("update_term",) else value
                )
            elif field.kind == "textarea":
                text = self.query_one(f"#{field.widget_id}", TextArea).text
                values[field.path] = parse_textarea_value(field, text)
            elif field.kind == "integer":
                text = self.query_one(f"#{field.widget_id}", Input).value
                values[field.path] = parse_integer_value(field, text)
            else:
                values[field.path] = self.query_one(f"#{field.widget_id}", Input).value
        return values

    def _update_config_preview(self, config: dict[str, object]) -> None:
        """刷新设置页 TOML 预览。"""
        self.query_one("#config-preview", TextArea).text = toml.dumps(config)
