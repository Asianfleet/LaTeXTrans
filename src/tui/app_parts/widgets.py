"""Standalone widgets and display helpers for the Textual TUI app."""

from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Static, TabbedContent, TextArea

from src.tui.app_parts.constants import (
    APP_TITLE_ART,
    APP_TITLE_ART_COMPACT,
    APP_TITLE_LINE_STYLES,
    APP_TITLE_PLAIN,
    PROGRESS_LOG_LINE_RE,
)


def app_title_art_width(art: str) -> int:
    """计算艺术字标题的最大终端显示宽度。"""
    return max(cell_len(line) for line in art.splitlines())


def build_art_title(art: str) -> Text:
    """用入口页标题样式构建指定艺术字文本。"""
    title = Text()
    for index, line in enumerate(art.splitlines()):
        if index:
            title.append("\n")
        title.append(line, style=APP_TITLE_LINE_STYLES[index])
    return title


def build_app_title() -> Text:
    """构建入口页宽屏蓝白色多行艺术字标题。"""
    return build_art_title(APP_TITLE_ART)


def build_app_title_for_width(width: int) -> Text:
    """根据可用宽度构建入口页标题，避免艺术字被终端换行错位。"""
    if width >= app_title_art_width(APP_TITLE_ART):
        return build_art_title(APP_TITLE_ART)
    if width >= app_title_art_width(APP_TITLE_ART_COMPACT):
        return build_art_title(APP_TITLE_ART_COMPACT)
    return Text(APP_TITLE_PLAIN, style=APP_TITLE_LINE_STYLES[2])


class ResponsiveAppTitle(Static):
    """入口页标题控件，根据自身宽度切换宽版、窄版和普通标题。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """初始化时先使用普通标题，等待布局完成后再按实际宽度刷新。"""
        super().__init__(build_app_title_for_width(0), *args, **kwargs)

    def on_mount(self) -> None:
        """控件挂载后按当前宽度刷新标题。"""
        self._refresh_for_width(self.size.width)

    def on_resize(self, event: events.Resize) -> None:
        """控件尺寸变化时按新的可绘制宽度刷新标题。"""
        self._refresh_for_width(event.size.width)

    def _refresh_for_width(self, width: int) -> None:
        """按给定宽度更新标题内容。"""
        next_title = build_app_title_for_width(width)
        if isinstance(self.content, Text) and self.content.plain == next_title.plain:
            return
        self.update(next_title, layout=False)


def compact_progress_log_for_display(log_text: str) -> str:
    """压缩连续进度日志块，展示时只保留首行、中间行和末行。"""
    displayed_lines: list[str] = []
    progress_block: list[str] = []

    def flush_progress_block() -> None:
        """将当前连续进度块按展示规则写入输出行。"""
        if not progress_block:
            return
        if len(progress_block) <= 3:
            displayed_lines.extend(progress_block)
        else:
            middle_index = len(progress_block) // 2
            displayed_lines.extend(
                [
                    progress_block[0],
                    progress_block[middle_index],
                    progress_block[-1],
                ]
            )
        progress_block.clear()

    for line in log_text.splitlines():
        stripped_line = line.rstrip()
        if PROGRESS_LOG_LINE_RE.match(stripped_line):
            progress_block.append(stripped_line)
            continue
        flush_progress_block()
        displayed_lines.append(stripped_line)

    flush_progress_block()
    return "\n".join(displayed_lines)


class ErrorReportsTable(DataTable):
    """错误记录表，尺寸变化时按新的可视宽度重新生成列。"""

    def on_resize(self, event: events.Resize) -> None:
        """表格尺寸变化时重新分配错误记录列宽。"""
        if self.columns:
            app = self.app
            if hasattr(app, "_refresh_selected_errors_table"):
                app.call_after_refresh(app._refresh_selected_errors_table)


class ZoteroResultsTable(DataTable):
    """Zotero 搜索结果表，单击数据行即可切换选中状态。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """初始化 Zotero 表格的鼠标点击防抖状态。"""
        super().__init__(*args, **kwargs)
        self._ignore_next_click = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """在鼠标按下时立即切换数据行，保证单击即可选中。"""
        if self._toggle_clicked_row(event):
            self._ignore_next_click = True
            event.stop()

    def on_resize(self, event: events.Resize) -> None:
        """表格尺寸变化时重新收紧列宽，避免出现水平滚动。"""
        if self.columns:
            app = self.app
            if hasattr(app, "_fit_zotero_results_table_columns"):
                app._fit_zotero_results_table_columns()

    def on_click(self, event: events.Click) -> None:
        """把数据行单击解释为 Zotero 条目选择，并保留非数据区默认行为。"""
        if self._ignore_next_click:
            self._ignore_next_click = False
            event.stop()
            return
        if self._toggle_clicked_row(event):
            event.stop()

    async def _on_click(self, event: events.Click) -> None:
        """在默认 DataTable 处理前拦截 Zotero 数据行点击。"""
        if self._toggle_clicked_row(event):
            event.stop()
            return
        await super()._on_click(event)

    def _toggle_clicked_row(self, event: events.MouseEvent) -> bool:
        """根据点击事件切换对应 Zotero 数据行，返回是否已处理。"""
        meta = event.style.meta
        has_cell_meta = "row" in meta and "column" in meta
        row_index = int(meta["row"]) if has_cell_meta else self._row_index_from_click(event)
        column_index = int(meta["column"]) if has_cell_meta else 0
        if not meta.get("out_of_bounds", False):
            if 0 <= row_index < self.row_count and column_index >= 0:
                self.cursor_coordinate = Coordinate(row_index, column_index)
                app = self.app
                if hasattr(app, "toggle_zotero_row_selection"):
                    app.toggle_zotero_row_selection(row_index)
                self._scroll_cursor_into_view(animate=True)
                return True
        return False

    def _row_index_from_click(self, event: events.MouseEvent) -> int:
        """从 Textual 鼠标事件坐标推导数据行索引。"""
        row_index = int(event.y) - self.header_height
        if 0 <= row_index < self.row_count or event.screen_y is None:
            return row_index
        return int(event.screen_y - self.region.y) - self.header_height


class EntryBatchTextArea(TextArea):
    """入口页批量输入框，负责把 Enter 解释为提交任务。"""

    BINDINGS = [
        *TextArea.BINDINGS,
        Binding("enter", "submit_entry", "发送", priority=True),
    ]

    def action_submit_entry(self) -> None:
        """提交入口页表单，不在输入框中插入换行。"""
        app = self.app
        if hasattr(app, "submit_entry_form"):
            app.submit_entry_form()


class ZoteroSearchInput(Input):
    """Zotero 搜索输入框，负责把 Enter 解释为搜索。"""

    BINDINGS = [
        *Input.BINDINGS,
        Binding("enter", "submit_search", "搜索", priority=True),
    ]

    def action_submit_search(self) -> None:
        """提交当前 Zotero 搜索词。"""
        app = self.app
        if hasattr(app, "search_zotero_items"):
            app.search_zotero_items()


class ConfigTabbedContent(TabbedContent):
    """设置页 tab 容器，提供只在设置上下文显示的 tab 快捷键。"""

    BINDINGS = [
        Binding("c", "show_tab('config-form-tab')", "配置"),
        Binding("p", "show_tab('config-preview-tab')", "预览"),
    ]

    def action_show_tab(self, tab_id: str) -> None:
        """切换到指定设置 tab。"""
        self.active = tab_id


class DetailTabbedContent(TabbedContent):
    """项目详情 tab 容器，提供只在详情上下文显示的 tab 快捷键。"""

    BINDINGS = [
        Binding("t", "show_tab('tex-tab')", "TeX"),
        Binding("r", "show_tab('terms-tab')", "术语"),
        Binding("e", "show_tab('errors-tab')", "错误"),
        Binding("l", "show_tab('log-tab')", "日志"),
        Binding("z", "show_tab('zotero-tab')", "Zotero"),
    ]

    def action_show_tab(self, tab_id: str) -> None:
        """切换到指定项目详情 tab。"""
        self.active = tab_id
