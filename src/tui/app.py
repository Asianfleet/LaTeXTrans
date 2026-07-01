"""Textual terminal UI entry point."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
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
    Select,
    Static,
    Switch,
    TabPane,
    TabbedContent,
    TextArea,
)

from src.tui.config import UI_CONFIG_PATH
from src.tui.input_parser import parse_input_items, validate_input_items
from src.tui.runner import run_tui_task
from src.tui.state import ProjectViewState, TaskViewState

PAGE_ENTRY = "entry"
PAGE_PROGRESS = "progress"
PAGE_DETAIL = "detail"
PAGE_TASKS = "tasks"
PAGE_CONFIG = "config"


class LaTeXTransTuiApp(App[None]):
    """Main Textual application for LaTeXTransPlus."""

    current_task: TaskViewState | None = None
    selected_project_name: str | None = None

    BINDINGS = [
        ("q", "quit", "退出"),
        ("n", "new_task", "新建任务"),
        ("m", "task_manager", "任务管理"),
        ("s", "settings", "设置"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the persistent sidebar, content switcher, and footer."""
        with Horizontal(id="app-body"):
            with Vertical(id="sidebar"):
                yield Button("新建任务", id="new-task-button")
                yield Button("任务管理", id="task-manager-button")
                yield ListView(id="project-list")
                yield Button("设置", id="settings-button")
            with ContentSwitcher(initial=PAGE_ENTRY, id="main-switcher"):
                with Vertical(id=PAGE_ENTRY):
                    yield Static("LaTeXTransPlus", id="app-title")
                    yield Select(
                        [
                            ("arXiv ID / URL", "arxiv"),
                            ("本地项目/压缩包", "local"),
                            ("远程压缩包 URL", "remote"),
                        ],
                        id="input-type-select",
                    )
                    yield TextArea(id="batch-input")
                    yield Button("开始", id="start-task-button")
                    yield Static("", id="entry-error")
                with Vertical(id=PAGE_PROGRESS):
                    yield Static("未开始", id="progress-summary")
                    yield ProgressBar(id="task-progress")
                    yield RichLog(id="event-log")
                with Vertical(id=PAGE_DETAIL):
                    with TabbedContent(initial="tex-tab", id="detail-tabs"):
                        with TabPane("TeX", id="tex-tab"):
                            tex_preview = TextArea(id="tex-preview")
                            tex_preview.read_only = True
                            yield tex_preview
                        with TabPane("术语表", id="terms-tab"):
                            yield DataTable(id="terms-table")
                        with TabPane("错误记录", id="errors-tab"):
                            yield DataTable(id="errors-table")
                        with TabPane("日志", id="log-tab"):
                            yield Static("", id="project-log-summary")
                            yield RichLog(id="project-log")
                    yield Static("", id="detail-paths")
                    yield Button("打开输出目录", id="open-output-button")
                    yield Button("导入 Zotero", id="import-zotero-button")
                with Vertical(id=PAGE_TASKS):
                    yield DataTable(id="task-table")
                with Vertical(id=PAGE_CONFIG):
                    yield Input(id="config-path-input")
                    yield Select([("浅色", "light"), ("深色", "dark")], id="theme-select")
                    yield Switch(id="config-switch")
                    yield TextArea(id="config-preview")
                    yield Button("保存", id="save-config-button")
                    yield Button("重载", id="reload-config-button")
        yield Footer()

    def switch_page(self, page_id: str) -> None:
        """Switch the right-side content area to the given page."""
        self.query_one("#main-switcher", ContentSwitcher).current = page_id

    def select_project(self, project_name: str) -> None:
        """Select a project and open its read-only detail page."""
        self.selected_project_name = project_name
        self.refresh_detail_page()
        self.switch_page(PAGE_DETAIL)

    def refresh_project_list(self) -> None:
        """Refresh the left-side project list from current task state."""
        list_view = self.query_one("#project-list", ListView)
        list_view.clear()
        if self.current_task is None:
            return

        for project in self.current_task.projects:
            list_view.append(ListItem(Static(f"{project.project_name} [{project.status.value}]")))

    def refresh_detail_page(self) -> None:
        """Refresh read-only detail widgets for the selected project."""
        project = self._selected_project()
        if project is None:
            return

        self._refresh_tex_preview(project)
        self._refresh_project_log(project)
        self._refresh_errors_table(project)
        self.query_one("#detail-paths", Static).update(self._project_detail_summary(project))

    def refresh_task_table(self) -> None:
        """Refresh the task management table from current project states."""
        table = self.query_one("#task-table", DataTable)
        table.clear(columns=True)
        table.add_columns("项目", "状态", "PDF", "输出目录")
        if self.current_task is None:
            return

        for project in self.current_task.projects:
            table.add_row(
                project.project_name,
                project.status.value,
                project.pdf_path or "",
                project.output_dir or "",
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle sidebar project selection from the project list."""
        if event.list_view.id != "project-list" or self.current_task is None:
            return
        if 0 <= event.index < len(self.current_task.projects):
            self.select_project(self.current_task.projects[event.index].project_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理主导航和任务入口按钮。"""
        if event.button.id == "start-task-button":
            self.submit_entry_form()
        elif event.button.id == "new-task-button":
            self.switch_page(PAGE_ENTRY)
        elif event.button.id == "task-manager-button":
            self.switch_page(PAGE_TASKS)
        elif event.button.id == "settings-button":
            self.switch_page(PAGE_CONFIG)

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
        self.current_task = TaskViewState(input_type=input_type, inputs=items)
        self.query_one("#progress-summary", Static).update(f"已创建任务：{len(items)} 个条目")
        self.switch_page(PAGE_PROGRESS)
        self.start_current_task()

    def handle_runtime_event(self, event: dict[str, object], task: TaskViewState | None = None) -> None:
        """应用 runtime 事件并刷新进度页控件。"""
        target_task = task or self.current_task
        if target_task is None or target_task is not self.current_task:
            return

        target_task.apply_event(dict(event))
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
        if self.current_task is None or self.selected_project_name is None:
            return None
        for project in self.current_task.projects:
            if project.project_name == self.selected_project_name:
                return project
        return None

    def _project_detail_summary(self, project: ProjectViewState) -> str:
        """Build the visible detail summary for project artifacts."""
        lines = [
            f"项目: {project.project_name}",
            f"状态: {project.status.value}",
            f"PDF: {project.pdf_path or '-'}",
            f"Output: {project.output_dir or '-'}",
            f"Log: {project.log_path or '-'}",
            f"错误报告: {project.errors_report_path or '-'}",
        ]
        if project.error:
            lines.append(f"错误: {project.error}")
        return "\n".join(lines)

    def _refresh_tex_preview(self, project: ProjectViewState) -> None:
        """Load the first TeX source as a read-only preview."""
        tex_preview = self.query_one("#tex-preview", TextArea)
        tex_preview.read_only = True
        tex_path = self._find_tex_preview_path(project)
        if tex_path is None:
            tex_preview.text = ""
            return

        try:
            tex_preview.text = tex_path.read_text(encoding="utf-8")
        except OSError as exc:
            tex_preview.text = f"无法读取 TeX 文件：{exc}"

    def _find_tex_preview_path(self, project: ProjectViewState) -> Path | None:
        """Find a representative TeX file for the project preview."""
        if project.project_dir is None:
            return None

        project_dir = Path(project.project_dir)
        if not project_dir.exists():
            return None

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
            project_name = task.running_project or (task.inputs[0] if task.inputs else "task")
            self.call_from_thread(
                self.handle_runtime_event,
                {"type": "project_error", "project_name": project_name, "error": str(exc)},
                task,
            )

    def action_new_task(self) -> None:
        """Open the entry page."""
        self.switch_page(PAGE_ENTRY)

    def action_task_manager(self) -> None:
        """Open the task management page."""
        self.switch_page(PAGE_TASKS)

    def action_settings(self) -> None:
        """Open the configuration page."""
        self.switch_page(PAGE_CONFIG)


def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
