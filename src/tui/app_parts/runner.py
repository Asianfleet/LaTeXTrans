"""Entry submission and background task execution for the Textual TUI app."""

from __future__ import annotations

from datetime import datetime

from textual import work
from textual.widgets import Select, Static, TextArea

from src.tui.app_parts.constants import PAGE_ENTRY
from src.tui.config import UI_CONFIG_PATH
from src.tui.input_parser import parse_input_items, validate_input_items
from src.tui.runner import run_tui_task
from src.tui.state import TaskViewState


class RunnerMixin:
    """Create TUI tasks from entry input and run them in a Textual worker."""

    task_timestamp_factory = staticmethod(
        lambda: datetime.now().strftime("%Y%m%dT%H%M%S.%f")[:-3]
    )
    task_runner = staticmethod(run_tui_task)

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
        self.query_one("#batch-input", TextArea).load_text("")
        self.switch_page(PAGE_ENTRY)
        self.notify(
            f"任务已开始：{self.current_task.task_id}（{len(items)} 个条目）",
            title="LaTeXTransPlus",
        )
        self.start_current_task()

    def _next_task_id(self) -> str:
        """Return the next stable task identifier for a submitted UI task."""
        return self.task_timestamp_factory()

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
            self.task_runner(
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
