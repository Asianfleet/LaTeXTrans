"""Textual terminal UI entry point."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
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

PAGE_ENTRY = "entry"
PAGE_PROGRESS = "progress"
PAGE_DETAIL = "detail"
PAGE_TASKS = "tasks"
PAGE_CONFIG = "config"


class LaTeXTransTuiApp(App[None]):
    """Main Textual application for LaTeXTransPlus."""

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
