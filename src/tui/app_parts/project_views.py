"""Selected project detail views for the Textual TUI app."""

from __future__ import annotations

import csv
from pathlib import Path

from rich.syntax import Syntax
from textual.widgets import DataTable, RichLog, Static

from src.tui.app_parts.constants import PAGE_DETAIL
from src.tui.app_parts.widgets import compact_progress_log_for_display
from src.tui.state import ProjectViewState


class ProjectViewsMixin:
    """Select projects and refresh TeX, log, and terminology detail widgets."""

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
        self.clear_zotero_results()
        self.refresh_detail_page()
        self.switch_page(PAGE_DETAIL)

    def refresh_detail_page(self) -> None:
        """Refresh read-only detail widgets for the selected project."""
        project = self._selected_project()
        if project is None:
            return

        self._refresh_tex_preview(project)
        self._refresh_project_log(project)
        self._refresh_errors_table(project)
        self._refresh_terms_table(project)
        self._refresh_zotero_controls()

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
        log_widget.clear()
        if project.log_path is None:
            for line in project.log_lines:
                log_widget.write(line)
            return

        try:
            log_text = Path(project.log_path).read_text(encoding="utf-8")
            log_text = compact_progress_log_for_display(log_text)
        except OSError as exc:
            log_text = "\n".join(project.log_lines) if project.log_lines else f"无法读取日志文件：{exc}"
        log_widget.write(log_text)

    def _refresh_terms_table(self, project: ProjectViewState) -> None:
        """Refresh the selected project's read-only terminology table."""
        table = self.query_one("#terms-table", DataTable)
        table.clear(columns=True)
        table.add_columns("术语", "译文")
        terms_path = self._project_terms_path(project)
        if terms_path is None:
            return

        try:
            with terms_path.open("r", encoding="utf-8", newline="") as terms_file:
                rows = list(csv.reader(terms_file))
        except OSError as exc:
            table.add_row("术语表读取错误", str(exc))
            return

        for row in rows[1:]:
            if len(row) >= 2:
                table.add_row(row[0], row[1])

    def _project_terms_path(self, project: ProjectViewState) -> Path | None:
        """Return the terminology CSV path for a project, including output-dir fallback."""
        if project.project_terms_path:
            terms_path = Path(project.project_terms_path)
            if terms_path.is_file():
                return terms_path
        if project.output_dir:
            fallback_path = Path(project.output_dir) / "project_terms.csv"
            if fallback_path.is_file():
                project.project_terms_path = str(fallback_path)
                return fallback_path
        return None
