"""Task history, runtime event, and notification behavior for the TUI app."""

from __future__ import annotations

from pathlib import Path

from src.tui.config import load_ui_config
from src.tui.history import load_output_history, write_project_metadata
from src.tui.state import ProjectStatus, ProjectViewState, TaskViewState


class TaskEventsMixin:
    """Merge task history, apply runtime events, and issue user notifications."""

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

    def handle_runtime_event(self, event: dict[str, object], task: TaskViewState | None = None) -> None:
        """应用 runtime 事件并刷新任务相关视图。"""
        target_task = task or self.current_task
        if target_task is None or target_task is not self.current_task:
            return

        event_payload = dict(event)
        target_task.apply_event(event_payload)
        if event_payload.get("type") == "project_log":
            self._refresh_selected_project_log(event_payload)
            return

        self._replace_history_project(target_task)
        self._persist_project_event(event_payload, target_task)
        self._notify_task_event(event_payload, target_task)
        self._refresh_selected_project_log(event_payload)
        self.refresh_project_list()
        self.refresh_task_table()

    def _refresh_selected_project_log(self, event: dict[str, object]) -> None:
        """如果日志事件属于当前详情项目，立即刷新日志控件。"""
        if event.get("type") != "project_log":
            return
        project = self._selected_project()
        if project is not None and project.project_name == str(event.get("project_name") or ""):
            self._refresh_project_log(project)
            self._refresh_terms_table(project)

    def _notify_task_event(self, event: dict[str, object], task: TaskViewState) -> None:
        """根据任务事件发送轻量通知，不依赖已删除的进度页。"""
        event_type = event.get("type")
        project_name = str(event.get("project_name") or "project")
        if event_type == "project_complete":
            if self._should_notify_project_event(task, project_name, "project_complete"):
                self.notify(f"项目完成：{project_name}，任务 id：{task.task_id}", title="LaTeXTransPlus")
        elif event_type == "project_error":
            if event.get("status") == "needs_term_review":
                if self._should_notify_project_event(task, project_name, "project_terms_ready"):
                    self.notify(f"术语表已生成：{project_name}，任务 id：{task.task_id}", title="LaTeXTransPlus")
            elif self._should_notify_project_event(task, project_name, "project_error"):
                error = str(event.get("error") or "未知异常")
                self.notify(
                    f"发生异常：{project_name}，任务 id：{task.task_id}，错误：{error}",
                    title="LaTeXTransPlus",
                    severity="error",
                )

        if self._task_is_finished(task) and not task.completion_notified:
            task.completion_notified = True
            self.notify(f"任务全部完成：{task.task_id}", title="LaTeXTransPlus")

    def _should_notify_project_event(self, task: TaskViewState, project_name: str, event_type: str) -> bool:
        """返回项目终态事件是否尚未发过通知，并记录本次通知键。"""
        notify_key = (event_type, project_name)
        if notify_key in task.notified_project_events:
            return False
        task.notified_project_events.add(notify_key)
        return True

    def _notify_empty_task_failure(self, task: TaskViewState, error: str) -> None:
        """在没有可映射项目的任务失败时发出任务级异常和终态通知。"""
        self.notify(
            f"发生异常：{task.task_id}，错误：{error}",
            title="LaTeXTransPlus",
            severity="error",
        )
        if not task.completion_notified:
            task.completion_notified = True
            self.notify(f"任务全部完成：{task.task_id}", title="LaTeXTransPlus")

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

    def _task_is_finished(self, task: TaskViewState) -> bool:
        """返回任务是否所有已知条目都已完成或失败。"""
        return task.total > 0 and self._stopped_project_count(task) >= task.total

    def _task_is_running(self, task: TaskViewState) -> bool:
        """返回任务是否仍有条目正在处理。"""
        if any(project.status == ProjectStatus.RUNNING for project in task.projects):
            return True
        return task.total > 0 and self._stopped_project_count(task) < task.total

    def _stopped_project_count(self, task: TaskViewState) -> int:
        """返回已离开后台处理状态的项目数量。"""
        stopped_statuses = {
            ProjectStatus.COMPLETED,
            ProjectStatus.FAILED,
            ProjectStatus.TERMS_READY,
        }
        return sum(1 for project in task.projects if project.status in stopped_statuses)

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
