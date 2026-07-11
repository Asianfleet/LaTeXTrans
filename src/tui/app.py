"""Textual terminal UI entry point."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App
from textual.widgets import (
    Button,
    DataTable,
    Input,
    RichLog,
    Rule,
    Select,
    Static,
    Switch,
    TabbedContent,
    TextArea,
)
from src.tui.app_parts.error_reports import ErrorReportsMixin
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
from src.tui.app_parts.layout import LayoutMixin
from src.tui.app_parts.navigation import NavigationMixin
from src.tui.app_parts.project_views import ProjectViewsMixin
from src.tui.app_parts.zotero_page import ZoteroPageMixin
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
from src.tui.input_parser import parse_input_items, validate_input_items
from src.tui.runner import run_tui_task
from src.tui.state import ProjectViewState, TaskViewState
from src.tui.zotero_adapter import ZoteroAdapter


def _load_ui_config_for_app(project_root: Path) -> dict[str, object]:
    """Load UI config through the module-level hook used by app tests."""
    return load_ui_config(project_root)


def _save_ui_config_for_app(project_root: Path, config: dict[str, object]) -> None:
    """Save UI config through the module-level hook used by app tests."""
    save_ui_config(project_root, config)


class LaTeXTransTuiApp(
    LayoutMixin,
    NavigationMixin,
    ConfigPageMixin,
    TaskEventsMixin,
    ProjectViewsMixin,
    ErrorReportsMixin,
    ZoteroPageMixin,
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

    def submit_entry_form(self) -> None:
        """校验入口页表单并创建任务视图状态。"""
        input_type_select = self.query_one("#input-type-select", Select)
        input_type = "" if input_type_select.is_blank() else str(input_type_select.value)
        input_text = self.query_one("#batch-input", TextArea).text
        items = parse_input_items(input_type, input_text)
        errors = validate_input_items(input_type, items)
        error_widget = self.query_one("#entry-error", Static)

        if not input_type or not items:
            error_widget.update("请选择输入类型并输入至少一个条目。")
            return
        if errors:
            error_widget.update("\n".join(errors))
            return

        error_widget.update("")
        self.current_task = TaskViewState(input_type=input_type, inputs=items, task_id=self._next_task_id())
        self.tasks.append(self.current_task)
        self.switch_page(PAGE_ENTRY)
        self.notify(
            f"任务已开始：{self.current_task.task_id}（{len(items)} 个条目）",
            title="LaTeXTransPlus",
        )
        self.start_current_task()

    def _next_task_id(self) -> str:
        """Return the next stable task identifier for a submitted UI task."""
        return datetime.now().strftime("%Y%m%dT%H%M%S.%f")[:-3]

    def start_current_task(self) -> None:
        """通过 Textual worker 启动当前任务。"""
        if self.current_task is None:
            return
        task = self.current_task
        task.total = len(task.inputs)
        self.run_current_task(task)

    @work(thread=True, exclusive=True)
    def run_current_task(self, task: TaskViewState) -> None:
        """在后台线程运行当前任务，避免阻塞 Textual UI。"""
        if task is not self.current_task:
            return

        def callback(event: dict[str, object]) -> None:
            """把后台 runner 事件转回 Textual UI 线程处理。"""
            self.call_from_thread(self.handle_runtime_event, event, task)

        try:
            run_tui_task(
                config_path=str(UI_CONFIG_PATH),
                input_type=task.input_type,
                items=task.inputs,
                overrides={},
                event_callback=callback,
            )
        except Exception as exc:
            if task.input_type == "remote" and task.total == 0:
                self.call_from_thread(self._notify_empty_task_failure, task, str(exc))
                return
            project_name = task.running_project or (task.inputs[0] if task.inputs else "task")
            self.call_from_thread(
                self.handle_runtime_event,
                {"type": "project_error", "project_name": project_name, "error": str(exc)},
                task,
            )

def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
