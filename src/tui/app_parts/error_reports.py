"""Error report table behavior for the Textual TUI app."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.text import Text
from textual.css.query import NoMatches
from textual.widgets import DataTable

from src.tui.app_parts.constants import (
    ERROR_MIN_CONTENT_COLUMN_WIDTH,
    ERROR_POSITION_COLUMN_WIDTH,
    ERROR_PROBLEM_COLUMN_WIDTH,
    ERROR_STATUS_COLUMN_WIDTH,
    ERROR_TYPE_COLUMN_WIDTH,
)
from src.tui.state import ProjectViewState


class ErrorReportsMixin:
    """Read, merge, and render validation error reports for the selected project."""

    def _refresh_errors_table(self, project: ProjectViewState) -> None:
        """刷新选中项目的错误记录表，展示错误内容和解决状态。"""
        table = self.query_one("#errors-table", DataTable)
        table.clear(columns=True)
        widths = self._errors_column_widths(table)
        for label, width in zip(("位置", "类型", "问题", "状态", "原文", "译文"), widths):
            table.add_column(label, width=width)

        for report, status in self._error_reports_with_status(project):
            source, translation = self._error_report_content(report, project)
            table.add_row(
                self._error_report_position(report),
                self._error_report_type(report),
                self._truncated_plain_text(self._error_report_problem(report), widths[2]),
                self._error_status_text(status),
                self._truncated_plain_text(source, widths[4]),
                self._truncated_plain_text(translation, widths[5]),
                height=1,
            )

    def _refresh_selected_errors_table(self) -> None:
        """在错误 tab 可见后按真实表格宽度重绘错误表。"""
        project = self._selected_project()
        if project is not None:
            self._refresh_errors_table(project)

    def _errors_column_widths(self, table: DataTable) -> tuple[int, int, int, int, int, int]:
        """按错误表可视宽度分配固定列宽，避免长内容撑出横向滚动。"""
        visible_width = self._errors_table_available_width(table)
        padding_budget = 2 * table.cell_padding * 6
        content_budget = max(
            visible_width - padding_budget,
            (
                ERROR_POSITION_COLUMN_WIDTH
                + ERROR_TYPE_COLUMN_WIDTH
                + ERROR_PROBLEM_COLUMN_WIDTH
                + ERROR_STATUS_COLUMN_WIDTH
                + ERROR_MIN_CONTENT_COLUMN_WIDTH * 2
            ),
        )
        fixed_width = (
            ERROR_POSITION_COLUMN_WIDTH
            + ERROR_TYPE_COLUMN_WIDTH
            + ERROR_PROBLEM_COLUMN_WIDTH
            + ERROR_STATUS_COLUMN_WIDTH
        )
        content_width = max(content_budget - fixed_width, ERROR_MIN_CONTENT_COLUMN_WIDTH * 2)
        source_width = max(ERROR_MIN_CONTENT_COLUMN_WIDTH, content_width // 2)
        translation_width = max(ERROR_MIN_CONTENT_COLUMN_WIDTH, content_width - source_width)
        return (
            ERROR_POSITION_COLUMN_WIDTH,
            ERROR_TYPE_COLUMN_WIDTH,
            ERROR_PROBLEM_COLUMN_WIDTH,
            ERROR_STATUS_COLUMN_WIDTH,
            source_width,
            translation_width,
        )

    def _errors_table_available_width(self, table: DataTable) -> int:
        """返回错误表可用于分配列宽的当前宽度。"""
        if table.size.width:
            return table.size.width
        for selector in ("#detail-tabs", "#main-switcher"):
            try:
                width = self.query_one(selector).size.width
            except NoMatches:
                width = 0
            if width:
                return width
        screen_width = self.screen.size.width if self.screen else 0
        return max((screen_width * 4) // 5, 80)

    def _error_reports_with_status(self, project: ProjectViewState) -> list[tuple[dict[str, object], str]]:
        """读取最终和初始错误报告，合并为带解决状态的展示行。"""
        report_path = self._project_errors_report_path(project)
        final_reports = self._read_error_report(str(report_path) if report_path else None)
        initial_path = self._initial_error_report_path(str(report_path) if report_path else None)
        initial_reports = self._read_error_report(str(initial_path) if initial_path else None)
        if not final_reports and not initial_reports:
            if project.error:
                return [({"part": "project", "num_or_ph": "-", "error": project.error}, "unresolved")]
            return []

        final_by_key = {self._error_report_key(report): report for report in final_reports}
        initial_by_key = {self._error_report_key(report): report for report in initial_reports}
        rows: list[tuple[dict[str, object], str]] = []
        for key, report in final_by_key.items():
            rows.append((report, "unresolved"))
            initial_by_key.pop(key, None)
        for report in initial_by_key.values():
            rows.append((report, "resolved"))
        return rows

    def _read_error_report(self, report_path: str | None) -> list[dict[str, object]]:
        """从 JSON 错误报告读取列表格式记录。"""
        if not report_path:
            return []
        path = Path(report_path)
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _initial_error_report_path(self, report_path: str | None) -> Path | None:
        """返回最终错误报告同目录下的初始错误报告路径。"""
        if not report_path:
            return None
        return Path(report_path).parent / "initial_errors_report.json"

    def _project_errors_report_path(self, project: ProjectViewState) -> Path | None:
        """返回项目错误报告路径，必要时从输出目录发现并回填。"""
        if project.errors_report_path:
            report_path = Path(project.errors_report_path)
            if report_path.is_file():
                return report_path
        if project.output_dir:
            fallback_path = Path(project.output_dir) / "errors_report.json"
            if fallback_path.is_file():
                project.errors_report_path = str(fallback_path)
                return fallback_path
        return None

    def _error_report_key(self, report: dict[str, object]) -> tuple[str, str]:
        """返回用于判断同一错误位置是否仍未解决的稳定键。"""
        return (str(report.get("part") or ""), str(report.get("num_or_ph") or ""))

    def _error_report_position(self, report: dict[str, object]) -> str:
        """把错误记录的位置字段转换为表格显示文本。"""
        part = str(report.get("part") or "")
        identifier = str(report.get("num_or_ph") or "-")
        part_labels = {"sec": "章节", "cap": "图题", "env": "环境", "project": "项目"}
        label = part_labels.get(part, part or "项目")
        return f"{label} {identifier}".strip()

    def _error_report_type(self, report: dict[str, object]) -> str:
        """从 issue 类型和旧字段推断错误类型显示文本。"""
        issue_labels = {
            "command_mismatch": "命令",
            "placeholder_mismatch": "占位符",
            "bracket_mismatch": "括号",
        }
        labels: list[str] = []
        issues = report.get("issues")
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict):
                    issue_type = str(issue.get("type") or "")
                    label = issue_labels.get(issue_type, issue_type)
                    if label and label not in labels:
                        labels.append(label)
        legacy_fields = [
            ("command_error", "命令"),
            ("ph_error", "占位符"),
            ("bracket_error", "括号"),
        ]
        for field, label in legacy_fields:
            if report.get(field) and label not in labels:
                labels.append(label)
        return "、".join(labels) if labels else "项目"

    def _error_report_problem(self, report: dict[str, object]) -> str:
        """从新旧错误报告字段拼接问题说明。"""
        messages: list[str] = []
        issues = report.get("issues")
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict) and issue.get("message"):
                    messages.append(str(issue["message"]))
        for field in ("command_error", "ph_error", "bracket_error", "error"):
            value = report.get(field)
            if value:
                messages.append(str(value))
        return "\n".join(messages)

    def _error_status_text(self, status: str) -> Text:
        """返回仅状态单元格使用的彩色 Rich 文本。"""
        if status == "resolved":
            return Text("已解决", style="green")
        return Text("未解决", style="yellow")

    def _error_report_content(self, report: dict[str, object], project: ProjectViewState) -> tuple[str, str]:
        """反查错误位置对应的原文和译文内容。"""
        content_root = self._error_content_root(project)
        if content_root is None:
            return "", ""
        part = str(report.get("part") or "")
        identifier = str(report.get("num_or_ph") or "")
        part_record = self._find_error_part_record(content_root, part, identifier)
        if part_record is None:
            return "", ""
        return str(part_record.get("content") or ""), str(part_record.get("trans_content") or "")

    def _error_content_root(self, project: ProjectViewState) -> Path | None:
        """确定错误报告关联的输出目录，用于读取 map JSON。"""
        if project.errors_report_path:
            return Path(project.errors_report_path).parent
        if project.output_dir:
            return Path(project.output_dir)
        return None

    def _find_error_part_record(
        self,
        content_root: Path,
        part: str,
        identifier: str,
    ) -> dict[str, object] | None:
        """在 sections/captions/envs map 中查找错误位置对应的内容记录。"""
        map_specs = {
            "sec": ("sections_map.json", "section"),
            "cap": ("captions_map.json", "placeholder"),
            "env": ("envs_map.json", "placeholder"),
        }
        spec = map_specs.get(part)
        if spec is None:
            return None
        filename, key = spec
        for record in self._read_json_list(content_root / filename):
            if str(record.get(key) or "") == identifier:
                return record
        return None

    def _read_json_list(self, path: Path) -> list[dict[str, object]]:
        """读取 JSON 列表文件，并过滤非对象元素。"""
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _truncated_plain_text(self, value: str, width: int) -> Text:
        """按列宽截断普通文本，不对内容本身做额外高亮。"""
        collapsed = re.sub(r"\s+", " ", value).strip()
        limit = max(width, 3)
        if len(collapsed) > limit:
            collapsed = collapsed[: max(limit - 3, 0)] + "..."
        return Text(collapsed, overflow="ellipsis", no_wrap=True)
