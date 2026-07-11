"""Layout composition for the Textual TUI app."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    ListView,
    RichLog,
    Rule,
    Select,
    Static,
    Switch,
    TabPane,
    TextArea,
)

from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS
from src.tui.app_parts.widgets import (
    ConfigTabbedContent,
    DetailTabbedContent,
    EntryBatchTextArea,
    ErrorReportsTable,
    ResponsiveAppTitle,
    ZoteroResultsTable,
    ZoteroSearchInput,
)
from src.tui.config_schema import ConfigField, grouped_config_fields


class LayoutMixin:
    """Compose the persistent TUI layout and setting field rows."""

    def compose(self) -> ComposeResult:
        """Compose the persistent sidebar, content switcher, and footer."""
        with Horizontal(id="app-body"):
            with Vertical(id="sidebar"):
                yield Button("新建任务", id="new-task-button", flat=True)
                yield Button("项目管理", id="project-manager-button", flat=True)
                yield ListView(id="project-list")
                yield Button("设置", id="settings-button", flat=True)
            yield Rule(orientation="vertical", id="sidebar-rule")
            with ContentSwitcher(initial=PAGE_ENTRY, id="main-switcher"):
                with Vertical(id=PAGE_ENTRY):
                    with Vertical(id="entry-form"):
                        yield Static("", id="entry-top-spacer")
                        yield ResponsiveAppTitle(id="app-title")
                        with Horizontal(id="entry-actions"):
                            yield Select(
                                [
                                    ("arXiv ID / URL", "arxiv"),
                                    ("本地项目/压缩包", "local"),
                                    ("远程压缩包 URL", "remote"),
                                ],
                                id="input-type-select",
                                value="arxiv",
                            )
                            yield EntryBatchTextArea(id="batch-input")
                            yield Button("发送", id="start-task-button", flat=True)
                        yield Static("", id="entry-error")
                        yield Static("", id="entry-bottom-offset")
                        yield Static("", id="entry-bottom-spacer")
                with Vertical(id=PAGE_DETAIL):
                    with DetailTabbedContent(initial="tex-tab", id="detail-tabs"):
                        with TabPane("TeX", id="tex-tab"):
                            with VerticalScroll(id="tex-preview-scroll"):
                                yield Static("", id="tex-preview")
                        with TabPane("术语表", id="terms-tab"):
                            yield DataTable(id="terms-table")
                        with TabPane("错误记录", id="errors-tab"):
                            yield ErrorReportsTable(id="errors-table")
                        with TabPane("日志", id="log-tab"):
                            yield RichLog(id="project-log")
                        with TabPane("Zotero", id="zotero-tab"):
                            with Horizontal(id="zotero-controls"):
                                yield Select([], id="zotero-library-select")
                                yield ZoteroSearchInput(id="zotero-search-input")
                                yield Button("搜索", id="zotero-search-button", flat=True)
                                yield Button("自动匹配", id="zotero-auto-match-button", flat=True)
                                yield Rule(orientation="vertical", id="zotero-import-rule")
                                yield Button("导入", id="import-zotero-button", flat=True)
                            yield ZoteroResultsTable(id="zotero-results", cursor_type="row")
                with Vertical(id=PAGE_TASKS):
                    yield DataTable(id="task-table")
                with Vertical(id=PAGE_CONFIG):
                    with ConfigTabbedContent(initial="config-form-tab", id="config-tabs"):
                        with TabPane("配置", id="config-form-tab"):
                            with VerticalScroll(id="config-form"):
                                for section, fields in grouped_config_fields():
                                    yield Static(section, classes="config-section-title")
                                    for field in fields:
                                        yield from self._compose_config_field(field)
                                yield Static("", id="config-error")
                        with TabPane("预览", id="config-preview-tab"):
                            preview = TextArea(id="config-preview", language="toml")
                            preview.read_only = True
                            yield preview
        yield Footer()

    def _compose_config_field(self, field: ConfigField) -> ComposeResult:
        """组合单个设置项的标签和编辑控件。"""
        with Horizontal(classes="config-field-row"):
            yield Static(field.label, classes="config-field-label")
            if field.kind == "select":
                yield Select(field.options, id=field.widget_id)
            elif field.kind == "switch":
                yield Switch(id=field.widget_id)
            elif field.kind == "textarea":
                yield TextArea(id=field.widget_id)
            else:
                yield Input(id=field.widget_id)
