"""Navigation, page switching, and top-level event handlers for the TUI app."""

from __future__ import annotations

from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Input,
    ListItem,
    ListView,
    Select,
    Static,
    Switch,
    TabbedContent,
    TextArea,
)

from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS


class NavigationMixin:
    """Handle main page navigation, shared widget events, and task table refresh."""

    def switch_page(self, page_id: str) -> None:
        """Switch the right-side content area to the given page."""
        self.query_one("#main-switcher", ContentSwitcher).current = page_id

    def refresh_project_list(self) -> None:
        """Refresh the left-side project list from all known task states."""
        list_view = self.query_one("#project-list", ListView)
        list_view.clear()

        for task, project in self._iter_project_states():
            label = Static(project.project_name)
            if self._task_is_running(task):
                label.add_class("running-task-project")
            list_view.append(ListItem(label))

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """切换 Zotero 结果行的选中状态。"""
        if event.data_table.id != "zotero-results":
            return
        row_index = event.cursor_row
        if row_index is not None:
            self.toggle_zotero_row_selection(row_index)

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
        elif event.button.id == "zotero-search-button":
            self.search_zotero_items()
        elif event.button.id == "zotero-auto-match-button":
            self.auto_match_zotero_items()
        elif event.button.id == "import-zotero-button":
            self.import_selected_project_to_zotero()

    def on_input_changed(self, event: Input.Changed) -> None:
        """配置输入框变化时立即保存并刷新预览。"""
        if self._is_config_widget(event.input.id):
            self.persist_config_form_change()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """搜索框回车时触发 Zotero 搜索。"""
        if event.input.id == "zotero-search-input":
            self.search_zotero_items()

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
        elif event.tabbed_content.id == "detail-tabs" and event.pane.id == "errors-tab":
            self.call_after_refresh(self._refresh_selected_errors_table)
        elif event.tabbed_content.id == "detail-tabs" and event.pane.id == "zotero-tab":
            self.load_zotero_libraries()

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
