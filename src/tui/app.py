"""Textual terminal UI entry point."""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

import toml
from rich.syntax import Syntax
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    ListItem,
    ListView,
    ProgressBar,
    RichLog,
    Rule,
    Select,
    Static,
    Switch,
    TabPane,
    TabbedContent,
    TextArea,
)

from src.tui.config import UI_CONFIG_PATH, load_ui_config, save_ui_config
from src.tui.config_schema import (
    CONFIG_FIELDS,
    ConfigField,
    bool_for_field,
    form_text_for_field,
    grouped_config_fields,
    normalized_config_from_form,
    parse_integer_value,
    parse_textarea_value,
    select_value_for_field,
)
from src.tui.history import load_output_history, write_project_metadata
from src.tui.input_parser import parse_input_items, validate_input_items
from src.tui.runner import run_tui_task
from src.tui.state import ProjectStatus, ProjectViewState, TaskViewState
from src.tui.zotero_adapter import ZoteroAdapter

PAGE_ENTRY = "entry"
PAGE_PROGRESS = "progress"
PAGE_DETAIL = "detail"
PAGE_TASKS = "tasks"
PAGE_CONFIG = "config"


class LaTeXTransTuiApp(App[None]):
    """Main Textual application for LaTeXTransPlus."""

    DEFAULT_CSS = """

    #sidebar {
        width: 1fr;
        padding: 0 1 0 1;
    }

    #sidebar Button {
        width: 100%;
        height: auto;
    }

    #project-list {
        background: transparent;
        padding: 0;
        scrollbar-size: 1 1;
    }

    #sidebar-rule {
        margin: 0;
        padding: 0;
    }

    #project-list ListItem:hover {
        background: $surface;
    }

    #main-switcher {
        width: 4fr;
    }

    #config,
    #tasks,
    #detail {
        padding-top: 1;
    }

    #tex-preview-scroll {
        height: 1fr;
    }

    #tex-preview {
        width: 100%;
    }

    #entry {
        align: center top;
        padding-top: 3;
    }

    #entry-form {
        width: 70%;
        min-width: 50;
        max-width: 90;
        height: auto;
        align-horizontal: center;
    }

    #app-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        text-align: center;
        margin: 0 0 2 0;
    }

    #batch-input {
        width: 100%;
        height: 8;
        margin: 0 0 1 0;
    }

    #entry-actions {
        width: 100%;
        height: 3;
    }

    #input-type-select {
        width: 24;
    }

    #start-task-button {
        dock: right;
        width: 10;
    }

    #entry-error {
        width: 100%;
        margin: 1 0 0 0;
    }

    #config-form {
        padding: 1 2;
    }

    .config-section-title {
        text-style: bold;
        margin: 1 0 0 0;
    }

    .config-field-row {
        height: auto;
        margin: 0 0 1 0;
    }

    .config-field-label {
        width: 24;
        padding: 1 1 0 0;
    }

    .config-field-row Input,
    .config-field-row Select {
        width: 1fr;
    }

    .config-field-row TextArea {
        width: 1fr;
        height: 5;
    }

    """

    current_task: TaskViewState | None = None
    tasks: list[TaskViewState]
    selected_project_name: str | None = None
    selected_task_id: str | None = None
    zotero_adapter_factory = staticmethod(
        lambda api_key, script_path: ZoteroAdapter(
            python_cmd=[sys.executable],
            script_path=script_path,
            api_key=api_key,
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
                        yield Static("LaTeXTransPlus", id="app-title")
                        yield TextArea(id="batch-input")
                        with Horizontal(id="entry-actions"):
                            yield Select(
                                [
                                    ("arXiv ID / URL", "arxiv"),
                                    ("本地项目/压缩包", "local"),
                                    ("远程压缩包 URL", "remote"),
                                ],
                                id="input-type-select",
                            )
                            yield Button("发送", id="start-task-button", flat=True)
                        yield Static("", id="entry-error")
                with Vertical(id=PAGE_PROGRESS):
                    yield Static("未开始", id="progress-summary")
                    yield ProgressBar(id="task-progress")
                    yield RichLog(id="event-log")
                with Vertical(id=PAGE_DETAIL):
                    with TabbedContent(initial="tex-tab", id="detail-tabs"):
                        with TabPane("TeX", id="tex-tab"):
                            with VerticalScroll(id="tex-preview-scroll"):
                                yield Static("", id="tex-preview")
                        with TabPane("术语表", id="terms-tab"):
                            yield DataTable(id="terms-table")
                        with TabPane("错误记录", id="errors-tab"):
                            yield DataTable(id="errors-table")
                        with TabPane("日志", id="log-tab"):
                            yield Static("", id="project-log-summary")
                            yield RichLog(id="project-log")
                        with TabPane("Zotero", id="zotero-tab"):
                            yield Input(id="zotero-api-key-input", password=True)
                            yield Input(id="zotero-script-path-input")
                            yield Input(id="zotero-library-id-input")
                            yield Select([("用户库", "user"), ("群组库", "group")], id="zotero-library-type-select")
                            yield Input(id="zotero-item-key-input")
                            yield Static("", id="zotero-status")
                            yield Button("导入 Zotero", id="import-zotero-button")
                with Vertical(id=PAGE_TASKS):
                    yield DataTable(id="task-table")
                with Vertical(id=PAGE_CONFIG):
                    with TabbedContent(initial="config-form-tab", id="config-tabs"):
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

    def on_mount(self) -> None:
        """Load existing output projects into the sidebar when the app starts."""
        if not self.load_history_on_mount:
            return
        self.theme = "nord"
        self.load_output_history()

    def switch_page(self, page_id: str) -> None:
        """Switch the right-side content area to the given page."""
        self.query_one("#main-switcher", ContentSwitcher).current = page_id

    def load_output_history(self) -> None:
        """Load output directory history into task state and refresh project views."""
        history_tasks = load_output_history(self._history_output_root())
        if not history_tasks:
            self.refresh_project_list()
            self.refresh_task_table()
            return

        current_tasks = [task for task in self.tasks if task is self.current_task]
        self.tasks = self._merge_history_tasks(history_tasks, current_tasks)
        self.refresh_project_list()
        self.refresh_task_table()

    def select_project(self, project_name: str, task_id: str | None = None) -> None:
        """Select a project and open its read-only detail page."""
        if task_id is None:
            project_identity = next(
                (
                    (task.task_id, project.project_name)
                    for task, project in self._iter_project_states()
                    if project.project_name == project_name
                ),
                (None, project_name),
            )
            task_id = project_identity[0]
        self.selected_project_name = project_name
        self.selected_task_id = task_id
        self.refresh_detail_page()
        self.switch_page(PAGE_DETAIL)

    def refresh_project_list(self) -> None:
        """Refresh the left-side project list from all known task states."""
        list_view = self.query_one("#project-list", ListView)
        list_view.clear()

        for task, project in self._iter_project_states():
            list_view.append(ListItem(Static(project.project_name)))

    def refresh_detail_page(self) -> None:
        """Refresh read-only detail widgets for the selected project."""
        project = self._selected_project()
        if project is None:
            return

        self._refresh_tex_preview(project)
        self._refresh_project_log(project)
        self._refresh_errors_table(project)
        self._refresh_terms_table(project)
        self.query_one("#zotero-status", Static).update(project.zotero_status)

    def refresh_task_table(self) -> None:
        """Refresh the project management table from all known task states."""
        table = self.query_one("#task-table", DataTable)
        table.clear(columns=True)
        table.add_columns("项目", "状态", "任务 id")

        for task, project in self._iter_project_states():
            table.add_row(
                project.project_name,
                project.status.value,
                task.task_id,
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle sidebar project selection from the project list."""
        if event.list_view.id != "project-list":
            return
        project_states = list(self._iter_project_states())
        if 0 <= event.index < len(project_states):
            task, project = project_states[event.index]
            self.select_project(project.project_name, task.task_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理主导航和任务入口按钮。"""
        if event.button.id == "start-task-button":
            self.submit_entry_form()
        elif event.button.id == "new-task-button":
            self.switch_page(PAGE_ENTRY)
        elif event.button.id in {"project-manager-button", "task-manager-button"}:
            self.switch_page(PAGE_TASKS)
        elif event.button.id == "settings-button":
            self.switch_page(PAGE_CONFIG)
            self.load_config_page()
        elif event.button.id == "import-zotero-button":
            self.import_selected_project_to_zotero()

    def on_input_changed(self, event: Input.Changed) -> None:
        """配置输入框变化时立即保存并刷新预览。"""
        if self._is_config_widget(event.input.id):
            self.persist_config_form_change()

    def on_select_changed(self, event: Select.Changed) -> None:
        """配置下拉框变化时立即保存并刷新预览。"""
        if self._is_config_widget(event.select.id):
            self.persist_config_form_change()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """配置开关变化时立即保存并刷新预览。"""
        if self._is_config_widget(event.switch.id):
            self.persist_config_form_change()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """配置多行文本变化时立即保存并刷新预览。"""
        if self._is_config_widget(event.text_area.id):
            self.persist_config_form_change()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """切到配置预览页时刷新未保存表单对应的 TOML。"""
        if event.tabbed_content.id == "config-tabs" and event.pane.id == "config-preview-tab":
            self.persist_config_form_change()

    def load_config_page(self) -> None:
        """将 UI 配置加载到结构化表单和 TOML 预览区。"""
        config = load_ui_config(Path.cwd())
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
        except ValueError as exc:
            self.query_one("#config-error", Static).update(str(exc))
            return
        save_ui_config(Path.cwd(), config)
        self.current_config = dict(config)
        self._update_config_preview(config)
        self.query_one("#config-error", Static).update("")

    def _is_config_widget(self, widget_id: str | None) -> bool:
        """判断事件来源是否为设置页配置控件。"""
        return bool(widget_id and widget_id.startswith("config-") and widget_id != "config-preview")

    def _config_from_form(self) -> dict[str, object]:
        """将当前表单转换为完整配置对象。"""
        values = self._collect_config_form_values()
        return normalized_config_from_form(dict(self.current_config), values)

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
        self.query_one("#event-log", RichLog).clear()
        self.query_one("#progress-summary", Static).update(f"已创建任务：{len(items)} 个条目")
        self.switch_page(PAGE_PROGRESS)
        self.start_current_task()

    def handle_runtime_event(self, event: dict[str, object], task: TaskViewState | None = None) -> None:
        """应用 runtime 事件并刷新进度页控件。"""
        target_task = task or self.current_task
        if target_task is None or target_task is not self.current_task:
            return

        target_task.apply_event(dict(event))
        self._replace_history_project(target_task)
        self._persist_project_event(dict(event), target_task)
        self._refresh_progress_widgets(target_task)
        self.query_one("#event-log", RichLog).write(str(event))
        self.refresh_project_list()
        self.refresh_task_table()

    def _refresh_progress_widgets(self, task: TaskViewState) -> None:
        """根据任务状态刷新摘要和进度条。"""
        finished = task.completed + task.failed
        summary = (
            f"总数 {task.total}，"
            f"完成 {task.completed}，"
            f"失败 {task.failed}"
        )
        last_error = next((event.get("error") for event in reversed(task.events) if event.get("error")), None)
        if last_error:
            summary = f"{summary}，错误 {last_error}"
        self.query_one("#progress-summary", Static).update(summary)
        self.query_one("#task-progress", ProgressBar).update(total=task.total, progress=finished)

    def _selected_project(self) -> ProjectViewState | None:
        """Return the currently selected project state."""
        if self.selected_project_name is None:
            return None
        for task, project in self._iter_project_states():
            if self.selected_task_id is not None and task.task_id != self.selected_task_id:
                continue
            if project.project_name == self.selected_project_name:
                return project
        return None

    def _iter_project_states(self) -> list[tuple[TaskViewState, ProjectViewState]]:
        """Return project states flattened across known task history."""
        tasks = self.tasks
        if not tasks and self.current_task is not None:
            tasks = [self.current_task]
        return [(task, project) for task in tasks for project in task.projects]

    def _next_task_id(self) -> str:
        """Return the next stable task identifier for a submitted UI task."""
        return datetime.now().strftime("%Y%m%dT%H%M%S.%f")[:-3]

    def _history_output_root(self) -> Path:
        """Return the output root used for loading historical projects."""
        config = load_ui_config(Path.cwd())
        configured_output = config.get("output_dir", "outputs")
        return Path(str(configured_output))

    def _merge_history_tasks(
        self,
        history_tasks: list[TaskViewState],
        current_tasks: list[TaskViewState],
    ) -> list[TaskViewState]:
        """Merge historical tasks with current in-memory tasks by output directory."""
        merged = list(history_tasks)
        for task in current_tasks:
            for project in task.projects:
                if project.output_dir:
                    merged = [
                        history_task
                        for history_task in merged
                        if not any(
                            history_project.output_dir == project.output_dir
                            for history_project in history_task.projects
                        )
                    ]
            if task not in merged:
                merged.append(task)
        return merged

    def _replace_history_project(self, task: TaskViewState) -> None:
        """Remove stale historical rows whose output directory is now owned by this task."""
        output_dirs = {
            project.output_dir
            for project in task.projects
            if project.output_dir
        }
        if not output_dirs:
            return
        retained_tasks: list[TaskViewState] = []
        for existing_task in self.tasks:
            if existing_task is task:
                retained_tasks.append(existing_task)
                continue
            existing_task.projects = [
                project
                for project in existing_task.projects
                if project.output_dir not in output_dirs
            ]
            if existing_task.projects:
                retained_tasks.append(existing_task)
        if task not in retained_tasks:
            retained_tasks.append(task)
        self.tasks = retained_tasks

    def _persist_project_event(self, event: dict[str, object], task: TaskViewState) -> None:
        """Persist metadata for project events with an output directory."""
        event_type = event.get("type")
        if event_type not in {"project_start", "project_complete", "project_error"}:
            return
        output_dir = event.get("output_dir")
        project_name = str(event.get("project_name") or "")
        if not output_dir or not project_name:
            return
        project = next(
            (item for item in task.projects if item.project_name == project_name),
            None,
        )
        status = project.status if project is not None else ProjectStatus.PENDING
        input_item = self._input_item_for_project(task, project_name)
        write_project_metadata(
            project_dir=Path(str(output_dir)),
            task_id=task.task_id,
            input_type=task.input_type,
            input_item=input_item,
            project_name=project_name,
            status=status,
        )

    def _input_item_for_project(self, task: TaskViewState, project_name: str) -> str:
        """Return the submitted input item that most likely produced the project."""
        for item in task.inputs:
            if Path(item).name == project_name or item == project_name:
                return item
        return task.inputs[0] if task.inputs else project_name

    def _refresh_tex_preview(self, project: ProjectViewState) -> None:
        """Load the first TeX source as a read-only preview."""
        tex_preview = self.query_one("#tex-preview", Static)
        tex_path = self._find_tex_preview_path(project)
        if tex_path is None:
            tex_preview.update("")
            return

        try:
            tex_preview.update(self._latex_syntax(tex_path.read_text(encoding="utf-8")))
        except OSError as exc:
            tex_preview.update(f"无法读取 TeX 文件：{exc}")

    def _latex_syntax(self, source: str) -> Syntax:
        """把 TeX 源码转换为离线 Rich LaTeX 高亮对象。"""
        return Syntax(
            source,
            "latex",
            theme="ansi_dark",
            line_numbers=True,
            word_wrap=True,
        )

    def _find_tex_preview_path(self, project: ProjectViewState) -> Path | None:
        """Find a representative TeX file for the project preview."""
        if project.project_dir is None:
            return None

        project_dir = Path(project.project_dir)
        if not project_dir.exists():
            return None

        if project_dir.is_file() and project_dir.suffix.lower() == ".tex":
            return project_dir

        main_tex = project_dir / "main.tex"
        if main_tex.is_file():
            return main_tex

        try:
            return next(path for path in sorted(project_dir.glob("*.tex")) if path.is_file())
        except StopIteration:
            return None

    def _refresh_project_log(self, project: ProjectViewState) -> None:
        """Load the selected project's log file into the log panel."""
        log_widget = self.query_one("#project-log", RichLog)
        log_summary = self.query_one("#project-log-summary", Static)
        log_widget.clear()
        if project.log_path is None:
            log_summary.update("")
            return

        try:
            log_text = Path(project.log_path).read_text(encoding="utf-8")
        except OSError as exc:
            log_text = f"无法读取日志文件：{exc}"
        log_summary.update(log_text)
        log_widget.write(log_text)

    def _refresh_errors_table(self, project: ProjectViewState) -> None:
        """Refresh the selected project's error report table."""
        table = self.query_one("#errors-table", DataTable)
        table.clear(columns=True)
        table.add_columns("错误报告", "错误信息")
        if project.errors_report_path is None and project.error is None:
            return
        table.add_row(project.errors_report_path or "", project.error or "")

    def _refresh_terms_table(self, project: ProjectViewState) -> None:
        """Refresh the selected project's read-only terminology table."""
        table = self.query_one("#terms-table", DataTable)
        table.clear(columns=True)
        table.add_columns("术语", "译文")
        if not project.project_terms_path:
            return

        terms_path = Path(project.project_terms_path)
        try:
            with terms_path.open("r", encoding="utf-8", newline="") as terms_file:
                rows = list(csv.reader(terms_file))
        except OSError as exc:
            table.add_row("术语表读取错误", str(exc))
            return

        for row in rows[1:]:
            if len(row) >= 2:
                table.add_row(row[0], row[1])

    def import_selected_project_to_zotero(self) -> None:
        """把当前选中项目的译文 PDF 附加到显式指定的 Zotero 条目。"""
        project = self._selected_project()
        status_widget = self.query_one("#zotero-status", Static)
        if project is None:
            status_widget.update("请选择一个项目。")
            return
        if not project.pdf_path:
            project.zotero_status = "失败：当前项目没有 PDF。"
            status_widget.update(project.zotero_status)
            return

        api_key = self.query_one("#zotero-api-key-input", Input).value.strip()
        script_path = self.query_one("#zotero-script-path-input", Input).value.strip()
        library_id = self.query_one("#zotero-library-id-input", Input).value.strip()
        library_type_select = self.query_one("#zotero-library-type-select", Select)
        library_type = "" if library_type_select.is_blank() else str(library_type_select.value)
        item_key = self.query_one("#zotero-item-key-input", Input).value.strip()
        missing_fields = [
            field_name
            for field_name, field_value in (
                ("API key", api_key),
                ("adapter script", script_path),
                ("library_id", library_id),
                ("library_type", library_type),
                ("item_key", item_key),
            )
            if not field_value
        ]
        if missing_fields:
            project.zotero_status = f"失败：缺少 {', '.join(missing_fields)}。"
            status_widget.update(project.zotero_status)
            return

        try:
            adapter = self.zotero_adapter_factory(api_key, script_path)
            result = adapter.attach_pdf(item_key, project.pdf_path, library_id, library_type)
        except Exception as exc:
            project.zotero_status = f"失败：{exc}"
            status_widget.update(project.zotero_status)
            return

        attachment_key = result.get("attachment_key", "")
        upload_status = result.get("status", "uploaded")
        project.zotero_status = f"{upload_status}: {attachment_key}".strip()
        status_widget.update(project.zotero_status)

    def start_current_task(self) -> None:
        """通过 Textual worker 启动当前任务。"""
        if self.current_task is None:
            return
        task = self.current_task
        task.total = len(task.inputs)
        self._refresh_progress_widgets(task)
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
                return
            project_name = task.running_project or (task.inputs[0] if task.inputs else "task")
            self.call_from_thread(
                self.handle_runtime_event,
                {"type": "project_error", "project_name": project_name, "error": str(exc)},
                task,
            )

    def action_new_task(self) -> None:
        """Open the entry page."""
        self.switch_page(PAGE_ENTRY)

    def action_project_manager(self) -> None:
        """Open the project management page."""
        self.switch_page(PAGE_TASKS)

    def action_task_manager(self) -> None:
        """Open the project management page through the legacy binding name."""
        self.action_project_manager()

    def action_settings(self) -> None:
        """Open the configuration page."""
        self.switch_page(PAGE_CONFIG)
        self.load_config_page()


def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
