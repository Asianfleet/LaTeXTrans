"""Textual terminal UI entry point."""

from __future__ import annotations

import os
import re
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
    ZOTERO_MAX_COLLECTION_COLUMN_WIDTH,
    ZOTERO_MAX_LIBRARY_COLUMN_WIDTH,
    ZOTERO_MIN_COLLECTION_COLUMN_WIDTH,
    ZOTERO_MIN_LIBRARY_COLUMN_WIDTH,
    ZOTERO_MIN_TITLE_COLUMN_WIDTH,
    ZOTERO_SELECTION_COLUMN_WIDTH,
)
from src.tui.app_parts.layout import LayoutMixin
from src.tui.app_parts.navigation import NavigationMixin
from src.tui.app_parts.project_views import ProjectViewsMixin
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

    def _initialize_zotero_results_table(self) -> None:
        """初始化 Zotero 结果表的固定列。"""
        table = self.query_one("#zotero-results", DataTable)
        table.cursor_type = "row"
        table.clear(columns=True)
        selection_width, title_width, library_width, collection_width = self._zotero_column_widths(table)
        table.add_column("选中", width=selection_width)
        table.add_column("标题", width=title_width)
        table.add_column("所在库", width=library_width)
        table.add_column("所在分类", width=collection_width)

    def _zotero_column_widths(self, table: DataTable) -> tuple[int, int, int, int]:
        """按表格可视宽度分配 Zotero 结果列宽，避免触发水平滚动。"""
        visible_width = table.size.width or 100
        padding_budget = 2 * table.cell_padding * 4
        content_budget = max(
            visible_width - padding_budget,
            ZOTERO_SELECTION_COLUMN_WIDTH + ZOTERO_MIN_TITLE_COLUMN_WIDTH,
        )
        remaining = max(content_budget - ZOTERO_SELECTION_COLUMN_WIDTH, ZOTERO_MIN_TITLE_COLUMN_WIDTH)
        library_width = min(
            ZOTERO_MAX_LIBRARY_COLUMN_WIDTH,
            max(ZOTERO_MIN_LIBRARY_COLUMN_WIDTH, remaining // 5),
        )
        collection_width = min(
            ZOTERO_MAX_COLLECTION_COLUMN_WIDTH,
            max(ZOTERO_MIN_COLLECTION_COLUMN_WIDTH, remaining // 4),
        )
        title_width = remaining - library_width - collection_width

        if title_width < ZOTERO_MIN_TITLE_COLUMN_WIDTH:
            shortage = ZOTERO_MIN_TITLE_COLUMN_WIDTH - title_width
            collection_reduction = min(shortage, max(collection_width - ZOTERO_MIN_COLLECTION_COLUMN_WIDTH, 0))
            collection_width -= collection_reduction
            shortage -= collection_reduction
            library_reduction = min(shortage, max(library_width - ZOTERO_MIN_LIBRARY_COLUMN_WIDTH, 0))
            library_width -= library_reduction
            title_width = remaining - library_width - collection_width

        return (
            ZOTERO_SELECTION_COLUMN_WIDTH,
            max(title_width, ZOTERO_MIN_TITLE_COLUMN_WIDTH),
            library_width,
            collection_width,
        )

    def _fit_zotero_results_table_columns(self) -> None:
        """在布局稳定后重新收紧 Zotero 结果列宽。"""
        table = self.query_one("#zotero-results", DataTable)
        widths = self._zotero_column_widths(table)
        for column, width in zip(table.ordered_columns, widths):
            column.width = width
            column.auto_width = False
        table._require_update_dimensions = True
        table._line_cache.clear()
        table.refresh(layout=True)

    def _refresh_zotero_controls(self) -> None:
        """按当前项目是否已有 PDF 刷新 Zotero 导入控件可见性。"""
        project = self._selected_project()
        has_pdf = bool(project and project.pdf_path)
        self.query_one("#zotero-import-rule", Rule).display = has_pdf
        self.query_one("#import-zotero-button", Button).display = has_pdf

    def load_zotero_libraries(self) -> None:
        """从本地 Zotero API 加载可选库到搜索范围下拉框。"""
        try:
            libraries = self._zotero_adapter().list_libraries()
        except Exception as exc:
            self.zotero_libraries = []
            self._set_zotero_status(f"本地 API 不可用：{exc}")
            return

        self.zotero_libraries = libraries
        options = [
            (str(item.get("name") or item.get("library_id")), self._zotero_library_value(item))
            for item in libraries
        ]
        select = self.query_one("#zotero-library-select", Select)
        select.set_options(options)
        if options:
            select.value = options[0][1]
            self._set_zotero_status("")
        else:
            self._set_zotero_status("没有可选库。")

    def search_zotero_items(self) -> None:
        """使用搜索框文本和当前库执行 Zotero 本地 API 搜索。"""
        query = self.query_one("#zotero-search-input", Input).value.strip()
        if not query:
            self._set_zotero_status("搜索框为空。")
            return
        library = self._selected_zotero_library()
        if library is None:
            self._set_zotero_status("未选择库。")
            return

        try:
            results = self._zotero_adapter().search_items(
                query,
                str(library["library_id"]),
                str(library["library_type"]),
            )
        except Exception as exc:
            self._set_zotero_status(f"搜索失败：{exc}")
            return

        self.populate_zotero_results(results)
        self._set_zotero_status("搜索无结果。" if not results else f"找到 {len(results)} 个条目。")

    def auto_match_zotero_items(self) -> None:
        """按当前 arXiv ID 匹配 Zotero 存档 id 字段。"""
        arxiv_id = self._selected_arxiv_id()
        if not arxiv_id:
            self._set_zotero_status("自动匹配缺少 arXiv ID。")
            return
        library = self._selected_zotero_library()
        if library is None:
            self._set_zotero_status("未选择库。")
            return

        try:
            results = self._zotero_adapter().match_items_by_archive_id(
                arxiv_id,
                str(library["library_id"]),
                str(library["library_type"]),
            )
        except Exception as exc:
            self._set_zotero_status(f"自动匹配失败：{exc}")
            return

        self.populate_zotero_results(results)
        self._set_zotero_status("搜索无结果。" if not results else f"找到 {len(results)} 个条目。")

    def populate_zotero_results(self, results: list[dict[str, object]]) -> None:
        """把 Zotero 搜索结果写入固定列数据表，并清空选择。"""
        self.zotero_results = list(results)
        self.zotero_selected_keys = set()
        self._initialize_zotero_results_table()
        table = self.query_one("#zotero-results", DataTable)
        for item in self.zotero_results:
            table.add_row(
                "[]",
                Text(str(item.get("title") or ""), overflow="ellipsis", no_wrap=True),
                str(item.get("library_name") or item.get("library_id") or ""),
                ", ".join(str(value) for value in item.get("collection_names", []) or []),
            )
        table.call_after_refresh(self._fit_zotero_results_table_columns)

    def clear_zotero_results(self) -> None:
        """清空当前项目的 Zotero 搜索结果和选择状态。"""
        self.zotero_results = []
        self.zotero_selected_keys = set()
        self._initialize_zotero_results_table()

    def toggle_zotero_row_selection(self, row_index: int) -> None:
        """切换指定 Zotero 结果行的多选状态。"""
        if row_index < 0 or row_index >= len(self.zotero_results):
            return
        table = self.query_one("#zotero-results", DataTable)
        item = self.zotero_results[row_index]
        item_key = str(item.get("item_key") or "")
        if item_key in self.zotero_selected_keys:
            self.zotero_selected_keys.remove(item_key)
            table.update_cell_at((row_index, 0), "[]")
        else:
            self.zotero_selected_keys.add(item_key)
            table.update_cell_at((row_index, 0), "[√]")

    def import_selected_project_to_zotero(self) -> None:
        """把当前选中项目的译文 PDF 附加到所有选中 Zotero 条目。"""
        project = self._selected_project()
        if project is None:
            self._set_zotero_status("请选择一个项目。")
            return
        if not project.pdf_path:
            project.zotero_status = "失败：当前项目没有 PDF。"
            self._set_zotero_status(project.zotero_status)
            return

        selected_items = [
            item
            for item in self.zotero_results
            if str(item.get("item_key") or "") in self.zotero_selected_keys
        ]
        if not selected_items:
            project.zotero_status = "失败：未选择任何条目。"
            self._set_zotero_status(project.zotero_status)
            return

        api_key_env = self._zotero_config().get("web_api_key_env", "ZOTERO_API_KEY")
        api_key = os.environ.get(str(api_key_env), "").strip()
        if not api_key:
            project.zotero_status = f"失败：Web API key 环境变量未设置：{api_key_env}。"
            self._set_zotero_status(project.zotero_status)
            return

        adapter = self._zotero_adapter(api_key=api_key)
        success_count = 0
        failures: list[str] = []
        for item in selected_items:
            item_key = str(item.get("item_key") or "")
            library_id = str(item.get("library_id") or "")
            library_type = str(item.get("library_type") or "")
            try:
                adapter.attach_pdf(item_key, project.pdf_path, library_id, library_type)
                success_count += 1
            except Exception as exc:
                failures.append(f"{item_key}: {exc}")

        project.zotero_status = f"导入完成：成功 {success_count}，失败 {len(failures)}。"
        if failures:
            project.zotero_status = f"{project.zotero_status} {'; '.join(failures)}"
        self._set_zotero_status(project.zotero_status)

    def _set_zotero_status(self, message: str) -> None:
        """记录 Zotero 操作状态，并在可见 UI 中发出轻量提示。"""
        project = self._selected_project()
        if project is not None and message:
            project.zotero_status = message
        if message:
            self.notify(message)

    def _zotero_config(self) -> dict[str, object]:
        """返回当前 UI 配置中的 Zotero 配置段。"""
        config = self.current_config or load_ui_config(Path.cwd())
        zotero_config = config.get("zotero", {}) if isinstance(config, dict) else {}
        if not isinstance(zotero_config, dict):
            return {}
        return zotero_config

    def _zotero_adapter(self, api_key: str = "") -> ZoteroAdapter:
        """按当前配置创建 Zotero adapter。"""
        local_api_base = str(self._zotero_config().get("local_api_base", "http://127.0.0.1:23119/api"))
        try:
            return self.zotero_adapter_factory(api_key, local_api_base)
        except TypeError:
            return self.zotero_adapter_factory(api_key, "")

    def _zotero_library_value(self, library: dict[str, object]) -> str:
        """返回 Zotero 库下拉框内部值。"""
        return f"{library.get('library_type')}:{library.get('library_id')}"

    def _selected_zotero_library(self) -> dict[str, object] | None:
        """返回当前下拉框选中的 Zotero 库数据。"""
        select = self.query_one("#zotero-library-select", Select)
        if select.is_blank():
            return None
        value = str(select.value)
        return next((item for item in self.zotero_libraries if self._zotero_library_value(item) == value), None)

    def _selected_task_input_type(self) -> str:
        """返回当前选中项目所属任务的输入类型。"""
        if self.selected_project_name is None:
            return self.current_task.input_type if self.current_task is not None else ""
        for task, project in self._iter_project_states():
            if self.selected_task_id is not None and task.task_id != self.selected_task_id:
                continue
            if project.project_name == self.selected_project_name:
                return task.input_type
        return ""

    def _selected_arxiv_id(self) -> str:
        """从当前选中项目或任务输入中提取 arXiv ID。"""
        pattern = re.compile(r"\d{4}\.\d{4,5}(?:v\d+)?")
        candidates: list[str] = []
        if self.selected_project_name:
            candidates.append(self.selected_project_name)
        if self.current_task is not None:
            candidates.extend(self.current_task.inputs)
        for candidate in candidates:
            match = pattern.search(candidate)
            if match:
                return match.group(0)
        return ""

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
