"""Textual terminal UI entry point."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import App
from textual import events
from textual.css.query import NoMatches
from textual.widgets import ContentSwitcher, TabbedContent
from src.tui.app_parts.config_page import ConfigPageMixin
from src.tui.app_parts.constants import (
    APP_TITLE_ART,
    APP_TITLE_ART_COMPACT,
    APP_TITLE_LINE_STYLES,
    APP_TITLE_PLAIN,
    PAGE_CONFIG,
    PAGE_DETAIL,
    PAGE_ENTRY,
    PAGE_TASKS,
)
from src.tui.app_parts.error_reports import ErrorReportsMixin
from src.tui.app_parts.layout import LayoutMixin
from src.tui.app_parts.navigation import NavigationMixin
from src.tui.app_parts.project_views import ProjectViewsMixin
from src.tui.app_parts.runner import RunnerMixin
from src.tui.app_parts.task_events import TaskEventsMixin
from src.tui.app_parts.styles import DEFAULT_CSS
from src.tui.app_parts.widgets import (
    ConfigTabbedContent,
    DetailTabbedContent,
    EntryBatchTextArea,
    ErrorReportsTable,
    ResponsiveAppTitle,
    ZoteroResultsTable,
    ZoteroSearchInput,
    app_title_art_width,
    build_app_title,
    build_app_title_for_width,
    build_art_title,
    compact_progress_log_for_display,
)
from src.tui.config import UI_CONFIG_PATH, load_ui_config, save_ui_config
from src.tui.runner import run_tui_task
from src.tui.state import ProjectViewState, TaskViewState
from src.tui.app_parts.zotero_page import ZoteroPageMixin
from src.tui.zotero_adapter import ZoteroAdapter


def _load_ui_config_for_app(project_root: Path) -> dict[str, object]:
    """Load UI config through the module-level hook used by app tests."""
    return load_ui_config(project_root)


def _save_ui_config_for_app(project_root: Path, config: dict[str, object]) -> None:
    """Save UI config through the module-level hook used by app tests."""
    save_ui_config(project_root, config)


def _next_task_timestamp_for_app() -> str:
    """Build the next task timestamp through the module-level datetime hook."""
    return datetime.now().strftime("%Y%m%dT%H%M%S.%f")[:-3]


def _run_tui_task_for_app(
    *,
    config_path: str,
    input_type: str,
    items: list[str],
    overrides: dict[str, object],
    event_callback,
) -> None:
    """Run a UI task through the module-level runner hook used by app tests."""
    run_tui_task(
        config_path=config_path,
        input_type=input_type,
        items=items,
        overrides=overrides,
        event_callback=event_callback,
    )


class LaTeXTransTuiApp(
    LayoutMixin,
    NavigationMixin,
    ConfigPageMixin,
    TaskEventsMixin,
    ProjectViewsMixin,
    ErrorReportsMixin,
    ZoteroPageMixin,
    RunnerMixin,
    App[None],
):
    """Main Textual application for LaTeXTransPlus."""

    DEFAULT_CSS = DEFAULT_CSS

    current_task: TaskViewState | None = None
    tasks: list[TaskViewState]
    selected_project_name: str | None = None
    selected_task_id: str | None = None
    config_loader = staticmethod(_load_ui_config_for_app)
    config_saver = staticmethod(_save_ui_config_for_app)
    task_timestamp_factory = staticmethod(_next_task_timestamp_for_app)
    task_runner = staticmethod(_run_tui_task_for_app)
    zotero_adapter_factory = staticmethod(
        lambda api_key, local_api_base: ZoteroAdapter(
            api_key=api_key,
            local_api_base=local_api_base,
        )
    )

    BINDINGS = [
        ("q", "quit", "退出"),
        ("n", "new_task", "新建任务"),
        ("m", "project_manager", "项目管理"),
        ("s", "settings", "设置"),
    ]

    def __init__(self, load_history_on_mount: bool = True) -> None:
        """Initialize in-memory task history for the terminal UI."""
        super().__init__()
        self.current_task = None
        self.tasks = []
        self.selected_project_name = None
        self.selected_task_id = None
        self.load_history_on_mount = load_history_on_mount
        self.current_config: dict[str, object] = {}
        self.loading_config_form = False
        self.zotero_libraries: list[dict[str, object]] = []
        self.zotero_results: list[dict[str, object]] = []
        self.zotero_selected_keys: set[str] = set()

    def on_mount(self) -> None:
        """Load existing output projects into the sidebar when the app starts."""
        self._initialize_zotero_results_table()
        if not self.load_history_on_mount:
            return
        self.theme = "nord"
        self.load_output_history()

    def on_resize(self, event: events.Resize) -> None:
        """终端尺寸变化后刷新依赖可视宽度的表格列。"""
        if self.screen is None:
            return
        self.call_after_refresh(self._refresh_tables_after_resize)

    def _refresh_tables_after_resize(self) -> None:
        """按当前激活页面重算错误表和 Zotero 结果表的列宽。"""
        try:
            main_switcher = self.query_one("#main-switcher", ContentSwitcher)
            detail_tabs = self.query_one("#detail-tabs", TabbedContent)
        except NoMatches:
            return
        if main_switcher.current != PAGE_TASKS and self.selected_project_name is not None:
            if detail_tabs.active == "errors-tab":
                self._refresh_selected_errors_table()
            if detail_tabs.active == "zotero-tab":
                self._fit_zotero_results_table_columns()

def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
