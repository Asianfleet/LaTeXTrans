# TUI App Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将臃肿的 `src/tui/app.py` 拆分到 `src/tui/app_parts/` 下的职责模块，同时保留现有 TUI 行为、公共导入路径和测试接口。

**Architecture:** 采用“入口整合层 + app_parts mixin 模块”的低风险迁移。`src/tui/app.py` 继续定义 `LaTeXTransTuiApp` 和 `run()`，并 re-export 现有公共对象；布局、配置页、导航、任务事件、详情页、错误报告、Zotero 和 runner 逻辑按职责移入 mixin，最终由 `LaTeXTransTuiApp` 多继承组合。

**Tech Stack:** Python 3.10+、Textual、Rich、TOML、`pathlib`、`unittest`、`unittest.mock`

## Global Constraints

- 在 `src/tui` 下新增一个子目录承载拆分后的 app 模块。
- 保留 `src/tui/app.py` 作为 TUI 入口和整合层。
- 第一阶段尽量做机械迁移，降低行为回归风险。
- 不改变 TUI 页面布局、控件 id、CSS selector 或快捷键语义。
- 不重写 Textual 状态流。
- 不把所有 mixin 立即改造成完全独立的服务类。
- 不改变 Zotero API、运行时任务、历史加载、配置保存或错误报告格式。
- 不删除 `src.tui.app` 中现有外部可导入对象的兼容入口。
- `app_parts` 模块不得导入 `src.tui.app`，避免形成循环依赖。
- 页面 id 和控件 id 不变。
- `LaTeXTransTuiApp.DEFAULT_CSS` 内容不变。
- `LaTeXTransTuiApp.BINDINGS` 语义不变。
- 现有测试中直接调用的 app 方法名不变。
- `load_history_on_mount=False` 的测试用法不变。
- `zotero_adapter_factory` 的测试替换方式不变。
- 项目运行和测试必须使用本项目 `latextrans` conda 环境。
- 新增类和函数必须带文档字符串。
- 涉及配置页的测试必须继续保护真实 `config/ui.toml`，不能因为拆分改变 mock 覆盖范围。

---

## 文件结构

- Create: `src/tui/app_parts/__init__.py`
  - `app_parts` 包标识，不导入 `src.tui.app`。
- Create: `src/tui/app_parts/constants.py`
  - 页面 id、列宽、标题和日志压缩正则等常量。
- Create: `src/tui/app_parts/styles.py`
  - `DEFAULT_CSS`。
- Create: `src/tui/app_parts/widgets.py`
  - 自定义 Textual 控件和标题/日志展示纯函数。
- Create: `src/tui/app_parts/layout.py`
  - `LayoutMixin`，承载 `compose()` 和 `_compose_config_field()`。
- Create: `src/tui/app_parts/config_page.py`
  - `ConfigPageMixin`，承载设置页加载、表单收集、即时保存和预览。
- Create: `src/tui/app_parts/navigation.py`
  - `NavigationMixin`，承载页面切换、事件分发、项目列表、任务表和快捷键 action。
- Create: `src/tui/app_parts/task_events.py`
  - `TaskEventsMixin`，承载历史加载、runtime 事件处理、通知和任务状态 helper。
- Create: `src/tui/app_parts/project_views.py`
  - `ProjectViewsMixin`，承载项目选择、详情页刷新、TeX 预览、日志和术语表。
- Create: `src/tui/app_parts/error_reports.py`
  - `ErrorReportsMixin`，承载错误报告读取、状态合并、列宽和表格刷新。
- Create: `src/tui/app_parts/zotero_page.py`
  - `ZoteroPageMixin`，承载 Zotero tab 表格、库加载、搜索、多选和附件导入。
- Create: `src/tui/app_parts/runner.py`
  - `RunnerMixin`，承载入口提交、任务 id、后台 worker 和 runner 调用。
- Modify: `src/tui/app.py`
  - 精简为入口整合层，组合 mixin 并 re-export 兼容对象。
- Test: `tests/test_tui_app.py`
  - 优先不改测试；只有在导入断裂时做最小兼容更新。

## Task 1: App Parts 基础模块

**Files:**
- Create: `src/tui/app_parts/__init__.py`
- Create: `src/tui/app_parts/constants.py`
- Create: `src/tui/app_parts/styles.py`
- Create: `src/tui/app_parts/widgets.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: 当前 `src/tui/app.py` 中的常量、`DEFAULT_CSS`、标题函数、日志压缩函数和自定义控件。
- Produces: `src.tui.app_parts.constants.PAGE_ENTRY: str`
- Produces: `src.tui.app_parts.styles.DEFAULT_CSS: str`
- Produces: `src.tui.app_parts.widgets.build_app_title() -> rich.text.Text`
- Produces: `src.tui.app_parts.widgets.compact_progress_log_for_display(log_text: str) -> str`
- Produces: `src.tui.app` 继续导出 `build_app_title`、`build_app_title_for_width`、`app_title_art_width`、`compact_progress_log_for_display`、`ResponsiveAppTitle`、`ErrorReportsTable`、`ZoteroResultsTable`、`EntryBatchTextArea`、`ZoteroSearchInput`、`ConfigTabbedContent`、`DetailTabbedContent`

- [ ] **Step 1: 运行基础导入测试，确认迁移前基线**

Run:

```powershell
python -m unittest tests.test_tui_app -k "app_title"
```

Expected: PASS，确认标题相关测试在拆分前可作为行为基线。

- [ ] **Step 2: 创建 `app_parts` 包和基础模块**

新增 `src/tui/app_parts/__init__.py`：

```python
"""Composable implementation modules for the Textual TUI app."""
```

新增 `src/tui/app_parts/constants.py`，从 `src/tui/app.py` 迁入以下常量，保持值完全一致：

```python
"""Constants shared by the Textual TUI app modules."""

from __future__ import annotations

import re

PAGE_ENTRY = "entry"
PAGE_DETAIL = "detail"
PAGE_TASKS = "tasks"
PAGE_CONFIG = "config"
ZOTERO_SELECTION_COLUMN_WIDTH = 4
ZOTERO_MIN_TITLE_COLUMN_WIDTH = 20
ZOTERO_MIN_LIBRARY_COLUMN_WIDTH = 10
ZOTERO_MAX_LIBRARY_COLUMN_WIDTH = 18
ZOTERO_MIN_COLLECTION_COLUMN_WIDTH = 12
ZOTERO_MAX_COLLECTION_COLUMN_WIDTH = 24
ERROR_POSITION_COLUMN_WIDTH = 10
ERROR_TYPE_COLUMN_WIDTH = 5
ERROR_PROBLEM_COLUMN_WIDTH = 24
ERROR_STATUS_COLUMN_WIDTH = 8
ERROR_MIN_CONTENT_COLUMN_WIDTH = 6
PROGRESS_LOG_LINE_RE = re.compile(r"^\[[#-]+\]\s+\d{1,3}(?:\.\d+)?%")
APP_TITLE_PLAIN = "LaTeXTransPlus"
APP_TITLE_ART = "\n".join(
    (
        "  ██╗      █████╗ ████████╗███████╗██╗  ██╗████████╗██████╗  █████╗ ███╗   ██╗███████╗      ██╗",
        "  ██║     ██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝██╔══██╗██╔══██╗████╗  ██║██╔════╝    ██████╗",
        "  ██║     ███████║   ██║   █████╗   ╚███╔╝    ██║   ██████╔╝███████║██╔██╗ ██║███████╗    ╚═██╔═╝",
        "  ██║     ██╔══██║   ██║   ██╔══╝   ██╔██╗    ██║   ██╔══██╗██╔══██║██║╚██╗██║╚════██║      ╚═╝",
        "  ███████╗██║  ██║   ██║   ███████╗██╔╝ ██╗   ██║   ██║  ██║██║  ██║██║ ╚████║███████║",
        "  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝",
    )
)
APP_TITLE_ART_COMPACT = "\n".join(
    (
        "  ██╗      █████╗ ████████╗███████╗██╗  ██╗████████╗      ██╗",
        "  ██║     ██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝    ██████╗",
        "  ██║     ███████║   ██║   █████╗   ╚███╔╝    ██║       ╚═██╔═╝",
        "  ██║     ██╔══██║   ██║   ██╔══╝   ██╔██╗    ██║         ╚═╝",
        "  ███████╗██║  ██║   ██║   ███████╗██╔╝ ██╗   ██║",
        "  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═╝",
    )
)
APP_TITLE_LINE_STYLES = (
    "bold bright_white",
    "bold #dbeafe",
    "bold #93c5fd",
    "bold #60a5fa",
    "bold #3b82f6",
    "bold #1d4ed8",
)
```

新增 `src/tui/app_parts/styles.py`，迁入当前 `LaTeXTransTuiApp.DEFAULT_CSS` 字符串：

```python
"""CSS used by the Textual TUI app."""

from __future__ import annotations

DEFAULT_CSS = """
<paste the exact current LaTeXTransTuiApp.DEFAULT_CSS string here>
"""
```

新增 `src/tui/app_parts/widgets.py`，迁入当前控件和纯函数，导入只来自 Textual/Rich 和 `app_parts.constants`：

```python
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

<move the current widget and helper definitions here without changing their bodies>
```

- [ ] **Step 3: 更新 `app.py` 的基础导入和 re-export**

在 `src/tui/app.py` 删除被搬走的常量、CSS、控件和纯函数定义，改为导入：

```python
from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS
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
    compact_progress_log_for_display,
)
```

将类内 CSS 改为：

```python
class LaTeXTransTuiApp(App[None]):
    """Main Textual application for LaTeXTransPlus."""

    DEFAULT_CSS = DEFAULT_CSS
```

- [ ] **Step 4: 运行标题、控件和导入相关测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "app_title"
python -m unittest tests.test_tui_app -k "zotero_results_table"
python -c "from src.tui.app import LaTeXTransTuiApp, build_app_title, compact_progress_log_for_display; print(LaTeXTransTuiApp.__name__, bool(build_app_title()), compact_progress_log_for_display('[#] 1%'))"
```

Expected: 两组 unittest PASS；Python one-liner 输出包含 `LaTeXTransTuiApp True [#] 1%`。

- [ ] **Step 5: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/__init__.py src/tui/app_parts/constants.py src/tui/app_parts/styles.py src/tui/app_parts/widgets.py
git commit -m "refactor(tui): extract app widgets and constants"
```

Expected: commit 成功，`git status --short` 不显示本任务文件的未暂存修改。

## Task 2: Layout 与配置页拆分

**Files:**
- Create: `src/tui/app_parts/layout.py`
- Create: `src/tui/app_parts/config_page.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `LayoutMixin` 依赖 Task 1 的 `PAGE_*` 和自定义控件。
- Produces: `LayoutMixin.compose(self) -> ComposeResult`
- Produces: `LayoutMixin._compose_config_field(self, field: ConfigField) -> ComposeResult`
- Produces: `ConfigPageMixin.load_config_page(self) -> None`
- Produces: `ConfigPageMixin.persist_config_form_change(self) -> None`

- [ ] **Step 1: 运行布局和配置页基线测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "composes_sidebar"
python -m unittest tests.test_tui_app -k "config"
```

Expected: PASS。

- [ ] **Step 2: 创建 `layout.py` 并迁入布局方法**

新增 `src/tui/app_parts/layout.py`：

```python
"""Layout composition for the Textual TUI app."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    RichLog,
    Rule,
    Select,
    Static,
    TabPane,
    TextArea,
)

from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS
from src.tui.app_parts.widgets import (
    ConfigTabbedContent,
    DetailTabbedContent,
    EntryBatchTextArea,
    ErrorReportsTable,
    ResponsiveAppTitle,
    ZoteroResultsTable,
    ZoteroSearchInput,
)
from src.tui.config_schema import ConfigField, grouped_config_fields


class LayoutMixin:
    """Compose the persistent TUI layout and setting field rows."""

    <move compose() and _compose_config_field() here without changing their bodies>
```

- [ ] **Step 3: 创建 `config_page.py` 并迁入配置页方法**

新增 `src/tui/app_parts/config_page.py`：

```python
"""Configuration page behavior for the Textual TUI app."""

from __future__ import annotations

from pathlib import Path

import toml
from textual.css.query import NoMatches
from textual.widgets import Input, Select, Static, Switch, TextArea

from src.tui.config import load_ui_config, save_ui_config
from src.tui.config_schema import (
    CONFIG_FIELDS,
    bool_for_field,
    form_text_for_field,
    normalized_config_from_form,
    parse_integer_value,
    parse_textarea_value,
    select_value_for_field,
)


class ConfigPageMixin:
    """Load, collect, persist, and preview UI configuration form values."""

    <move load_config_page(), persist_config_form_change(), _is_config_widget(),
    _config_from_form(), _populate_config_form(), _collect_config_form_values(),
    and _update_config_preview() here without changing their bodies>
```

- [ ] **Step 4: 让 `LaTeXTransTuiApp` 继承 layout 和配置 mixin**

在 `src/tui/app.py` 添加：

```python
from src.tui.app_parts.config_page import ConfigPageMixin
from src.tui.app_parts.layout import LayoutMixin
```

更新类定义：

```python
class LaTeXTransTuiApp(LayoutMixin, ConfigPageMixin, App[None]):
    """Main Textual application for LaTeXTransPlus."""
```

从 `app.py` 删除已迁移的方法定义，保留 `__init__()` 和 `on_mount()`。

- [ ] **Step 5: 运行布局和配置页测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "composes_sidebar"
python -m unittest tests.test_tui_app -k "config"
python -c "from src.tui.app import LaTeXTransTuiApp; print(LaTeXTransTuiApp.__mro__[1].__name__, LaTeXTransTuiApp.__mro__[2].__name__)"
```

Expected: unittest PASS；one-liner 输出 `LayoutMixin ConfigPageMixin`。

- [ ] **Step 6: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/layout.py src/tui/app_parts/config_page.py
git commit -m "refactor(tui): extract layout and config page"
```

Expected: commit 成功。

## Task 3: 导航、页面切换和任务表拆分

**Files:**
- Create: `src/tui/app_parts/navigation.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `PAGE_ENTRY`、`PAGE_DETAIL`、`PAGE_TASKS`、`PAGE_CONFIG`
- Consumes: app 上已有 `submit_entry_form()`、`search_zotero_items()`、`auto_match_zotero_items()`、`import_selected_project_to_zotero()`、`load_config_page()`、`load_zotero_libraries()` 等方法。
- Produces: `NavigationMixin.switch_page(self, page_id: str) -> None`
- Produces: `NavigationMixin.refresh_project_list(self) -> None`
- Produces: `NavigationMixin.refresh_task_table(self) -> None`
- Produces: Textual event handler 和 action 方法原名不变。

- [ ] **Step 1: 运行导航基线测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "switch_page"
python -m unittest tests.test_tui_app -k "button"
python -m unittest tests.test_tui_app -k "shortcut"
python -m unittest tests.test_tui_app -k "refresh_task_table"
```

Expected: PASS。

- [ ] **Step 2: 创建 `navigation.py` 并迁入导航方法**

新增 `src/tui/app_parts/navigation.py`：

```python
"""Navigation, page switching, and top-level event handlers for the TUI app."""

from __future__ import annotations

from textual.widgets import Button, ContentSwitcher, DataTable, Input, ListItem, ListView, Select, Static, Switch, TabbedContent, TextArea

from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS


class NavigationMixin:
    """Handle main page navigation, shared widget events, and task table refresh."""

    <move switch_page(), refresh_project_list(), refresh_task_table(),
    on_list_view_selected(), on_data_table_row_selected(), on_button_pressed(),
    on_input_changed(), on_input_submitted(), on_select_changed(),
    on_switch_changed(), on_text_area_changed(), on_tabbed_content_tab_activated(),
    action_new_task(), action_project_manager(), action_task_manager(),
    and action_settings() here without changing their bodies>
```

- [ ] **Step 3: 让 app 继承 `NavigationMixin`**

在 `src/tui/app.py` 添加：

```python
from src.tui.app_parts.navigation import NavigationMixin
```

更新类定义：

```python
class LaTeXTransTuiApp(LayoutMixin, NavigationMixin, ConfigPageMixin, App[None]):
    """Main Textual application for LaTeXTransPlus."""
```

删除 `app.py` 中已迁移的导航方法。

- [ ] **Step 4: 运行导航测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "switch_page"
python -m unittest tests.test_tui_app -k "button"
python -m unittest tests.test_tui_app -k "shortcut"
python -m unittest tests.test_tui_app -k "refresh_task_table"
```

Expected: PASS。

- [ ] **Step 5: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/navigation.py
git commit -m "refactor(tui): extract navigation handlers"
```

Expected: commit 成功。

## Task 4: 任务事件、历史和通知拆分

**Files:**
- Create: `src/tui/app_parts/task_events.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `src.tui.history.load_output_history()`、`write_project_metadata()`
- Consumes: `src.tui.state.ProjectStatus`、`ProjectViewState`、`TaskViewState`
- Produces: `TaskEventsMixin.load_output_history(self) -> None`
- Produces: `TaskEventsMixin.handle_runtime_event(self, event: dict[str, object], task: TaskViewState | None = None) -> None`
- Produces: `_selected_project()`、`_iter_project_states()`、`_task_is_finished()` 等 helper 原名不变。

- [ ] **Step 1: 运行任务事件基线测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "handle_runtime_event"
python -m unittest tests.test_tui_app -k "history"
python -m unittest tests.test_tui_app -k "notify"
python -m unittest tests.test_tui_app -k "worker_exception"
```

Expected: PASS。

- [ ] **Step 2: 创建 `task_events.py` 并迁入任务事件方法**

新增 `src/tui/app_parts/task_events.py`：

```python
"""Task history, runtime event, and notification behavior for the TUI app."""

from __future__ import annotations

from pathlib import Path

from src.tui.config import load_ui_config
from src.tui.history import load_output_history, write_project_metadata
from src.tui.state import ProjectStatus, ProjectViewState, TaskViewState


class TaskEventsMixin:
    """Merge task history, apply runtime events, and issue user notifications."""

    <move load_output_history(), handle_runtime_event(), _refresh_selected_project_log(),
    _notify_task_event(), _should_notify_project_event(), _notify_empty_task_failure(),
    _selected_project(), _iter_project_states(), _task_is_finished(),
    _task_is_running(), _stopped_project_count(), _history_output_root(),
    _merge_history_tasks(), _replace_history_project(), _persist_project_event(),
    and _input_item_for_project() here without changing their bodies>
```

- [ ] **Step 3: 让 app 继承 `TaskEventsMixin`**

在 `src/tui/app.py` 添加：

```python
from src.tui.app_parts.task_events import TaskEventsMixin
```

更新类定义：

```python
class LaTeXTransTuiApp(
    LayoutMixin,
    NavigationMixin,
    ConfigPageMixin,
    TaskEventsMixin,
    App[None],
):
    """Main Textual application for LaTeXTransPlus."""
```

删除 `app.py` 中已迁移的任务事件方法。

- [ ] **Step 4: 运行任务事件测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "handle_runtime_event"
python -m unittest tests.test_tui_app -k "history"
python -m unittest tests.test_tui_app -k "notify"
python -m unittest tests.test_tui_app -k "worker_exception"
```

Expected: PASS。

- [ ] **Step 5: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/task_events.py
git commit -m "refactor(tui): extract task event handling"
```

Expected: commit 成功。

## Task 5: 详情页、错误记录和术语表拆分

**Files:**
- Create: `src/tui/app_parts/project_views.py`
- Create: `src/tui/app_parts/error_reports.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `TaskEventsMixin._selected_project()`
- Consumes: `widgets.compact_progress_log_for_display()`
- Produces: `ProjectViewsMixin.select_project(self, project_name: str, task_id: str | None = None) -> None`
- Produces: `ProjectViewsMixin.refresh_detail_page(self) -> None`
- Produces: `ErrorReportsMixin._refresh_errors_table(self, project: ProjectViewState) -> None`
- Produces: 错误报告 helper 和术语表 helper 原名不变。

- [ ] **Step 1: 运行详情页和错误表基线测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "refresh_detail_page"
python -m unittest tests.test_tui_app -k "errors_table"
python -m unittest tests.test_tui_app -k "terms_table"
python -m unittest tests.test_tui_app -k "compact_progress"
```

Expected: PASS。

- [ ] **Step 2: 创建 `project_views.py` 并迁入详情页通用方法**

新增 `src/tui/app_parts/project_views.py`：

```python
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

    <move select_project(), refresh_detail_page(), _refresh_tex_preview(),
    _latex_syntax(), _find_tex_preview_path(), _refresh_project_log(),
    _refresh_terms_table(), and _project_terms_path() here without changing their bodies>
```

- [ ] **Step 3: 创建 `error_reports.py` 并迁入错误报告方法**

新增 `src/tui/app_parts/error_reports.py`：

```python
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

    <move _refresh_errors_table(), _refresh_selected_errors_table(),
    _errors_column_widths(), _errors_table_available_width(),
    _error_reports_with_status(), _read_error_report(),
    _initial_error_report_path(), _project_errors_report_path(),
    _error_report_key(), _error_report_position(), _error_report_type(),
    _error_report_problem(), _error_status_text(), _error_report_content(),
    _error_content_root(), _find_error_part_record(), _read_json_list(),
    and _truncated_plain_text() here without changing their bodies>
```

- [ ] **Step 4: 让 app 继承详情页和错误报告 mixin**

在 `src/tui/app.py` 添加：

```python
from src.tui.app_parts.error_reports import ErrorReportsMixin
from src.tui.app_parts.project_views import ProjectViewsMixin
```

更新类定义：

```python
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
```

删除 `app.py` 中已迁移的详情页和错误报告方法。

- [ ] **Step 5: 运行详情页和错误表测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "refresh_detail_page"
python -m unittest tests.test_tui_app -k "errors_table"
python -m unittest tests.test_tui_app -k "terms_table"
python -m unittest tests.test_tui_app -k "compact_progress"
```

Expected: PASS。

- [ ] **Step 6: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/project_views.py src/tui/app_parts/error_reports.py
git commit -m "refactor(tui): extract project detail views"
```

Expected: commit 成功。

## Task 6: Zotero 页面拆分

**Files:**
- Create: `src/tui/app_parts/zotero_page.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `TaskEventsMixin._selected_project()`、`ConfigPageMixin.current_config`、`ProjectViewsMixin` 的选中项目状态。
- Consumes: `src.tui.zotero_adapter.ZoteroAdapter`
- Produces: `ZoteroPageMixin.load_zotero_libraries(self) -> None`
- Produces: `ZoteroPageMixin.search_zotero_items(self) -> None`
- Produces: `ZoteroPageMixin.auto_match_zotero_items(self) -> None`
- Produces: `ZoteroPageMixin.populate_zotero_results(self, results: list[dict[str, object]]) -> None`
- Produces: `ZoteroPageMixin.import_selected_project_to_zotero(self) -> None`

- [ ] **Step 1: 运行 Zotero 基线测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "zotero"
```

Expected: PASS。

- [ ] **Step 2: 创建 `zotero_page.py` 并迁入 Zotero 方法**

新增 `src/tui/app_parts/zotero_page.py`：

```python
"""Zotero tab behavior for the Textual TUI app."""

from __future__ import annotations

import os
import re
from pathlib import Path

from rich.text import Text
from textual.widgets import Button, DataTable, Input, Rule, Select

from src.tui.app_parts.constants import (
    ZOTERO_MAX_COLLECTION_COLUMN_WIDTH,
    ZOTERO_MAX_LIBRARY_COLUMN_WIDTH,
    ZOTERO_MIN_COLLECTION_COLUMN_WIDTH,
    ZOTERO_MIN_LIBRARY_COLUMN_WIDTH,
    ZOTERO_MIN_TITLE_COLUMN_WIDTH,
    ZOTERO_SELECTION_COLUMN_WIDTH,
)
from src.tui.config import load_ui_config
from src.tui.zotero_adapter import ZoteroAdapter


class ZoteroPageMixin:
    """Load Zotero libraries, search items, manage row selection, and attach PDFs."""

    <move _initialize_zotero_results_table(), _zotero_column_widths(),
    _fit_zotero_results_table_columns(), _refresh_zotero_controls(),
    load_zotero_libraries(), search_zotero_items(), auto_match_zotero_items(),
    populate_zotero_results(), clear_zotero_results(), toggle_zotero_row_selection(),
    import_selected_project_to_zotero(), _set_zotero_status(), _zotero_config(),
    _zotero_adapter(), _zotero_library_value(), _selected_zotero_library(),
    _selected_task_input_type(), and _selected_arxiv_id() here without changing their bodies>
```

- [ ] **Step 3: 让 app 继承 `ZoteroPageMixin`**

在 `src/tui/app.py` 添加：

```python
from src.tui.app_parts.zotero_page import ZoteroPageMixin
```

更新类定义：

```python
class LaTeXTransTuiApp(
    LayoutMixin,
    NavigationMixin,
    ConfigPageMixin,
    TaskEventsMixin,
    ProjectViewsMixin,
    ErrorReportsMixin,
    ZoteroPageMixin,
    App[None],
):
    """Main Textual application for LaTeXTransPlus."""
```

删除 `app.py` 中已迁移的 Zotero 方法。

- [ ] **Step 4: 运行 Zotero 测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "zotero"
```

Expected: PASS。

- [ ] **Step 5: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/zotero_page.py
git commit -m "refactor(tui): extract zotero page behavior"
```

Expected: commit 成功。

## Task 7: Runner 与 app 入口最终精简

**Files:**
- Create: `src/tui/app_parts/runner.py`
- Modify: `src/tui/app.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `parse_input_items(input_type: str, input_text: str) -> list[str]`
- Consumes: `validate_input_items(input_type: str, items: list[str]) -> list[str]`
- Consumes: `run_tui_task(config_path: str, input_type: str, items: list[str], overrides: dict[str, object], event_callback: Callable[[dict[str, object]], None])`
- Produces: `RunnerMixin.submit_entry_form(self) -> None`
- Produces: `RunnerMixin.start_current_task(self) -> None`
- Produces: `RunnerMixin.run_current_task(self, task: TaskViewState) -> None`
- Produces: `src.tui.app.LaTeXTransTuiApp` 只保留入口整合职责。

- [ ] **Step 1: 运行入口提交和 worker 基线测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "submit_entry_form"
python -m unittest tests.test_tui_app -k "start_current_task"
python -m unittest tests.test_tui_app -k "worker"
```

Expected: PASS。

- [ ] **Step 2: 创建 `runner.py` 并迁入入口提交和 worker 方法**

新增 `src/tui/app_parts/runner.py`：

```python
"""Entry submission and background task execution for the Textual TUI app."""

from __future__ import annotations

from datetime import datetime

from textual import work
from textual.widgets import Select, Static, TextArea

from src.tui.config import UI_CONFIG_PATH
from src.tui.input_parser import parse_input_items, validate_input_items
from src.tui.runner import run_tui_task
from src.tui.state import TaskViewState


class RunnerMixin:
    """Create TUI tasks from entry input and run them in a Textual worker."""

    <move submit_entry_form(), _next_task_id(), start_current_task(),
    and run_current_task() here without changing their bodies>
```

`_selected_task_input_type()` 和 `_selected_arxiv_id()` 已在 Task 6 迁入 `ZoteroPageMixin`，不要在本文件重复定义。

- [ ] **Step 3: 让 app 继承 `RunnerMixin` 并精简入口文件**

在 `src/tui/app.py` 添加：

```python
from src.tui.app_parts.runner import RunnerMixin
```

最终类定义应为：

```python
class LaTeXTransTuiApp(
    LayoutMixin,
    NavigationMixin,
    ConfigPageMixin,
    TaskEventsMixin,
    ProjectViewsMixin,
    ErrorReportsMixin,
    ZoteroPageMixin,
    RunnerMixin,
    App[None],
):
    """Main Textual application for LaTeXTransPlus."""
```

`src/tui/app.py` 最终只保留这些实现内容：

```python
class LaTeXTransTuiApp(...):
    """Main Textual application for LaTeXTransPlus."""

    DEFAULT_CSS = DEFAULT_CSS
    current_task: TaskViewState | None = None
    tasks: list[TaskViewState]
    selected_project_name: str | None = None
    selected_task_id: str | None = None
    zotero_adapter_factory = staticmethod(
        lambda api_key, local_api_base: ZoteroAdapter(
            api_key=api_key,
            local_api_base=local_api_base,
        )
    )
    BINDINGS = [...]

    def __init__(self, load_history_on_mount: bool = True) -> None:
        """Initialize in-memory task history for the terminal UI."""
        ...

    def on_mount(self) -> None:
        """Load existing output projects into the sidebar when the app starts."""
        ...


def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
```

- [ ] **Step 4: 运行入口提交和 worker 测试**

Run:

```powershell
python -m unittest tests.test_tui_app -k "submit_entry_form"
python -m unittest tests.test_tui_app -k "start_current_task"
python -m unittest tests.test_tui_app -k "worker"
python -c "from src.tui.app import LaTeXTransTuiApp, run; print(LaTeXTransTuiApp.__name__, callable(run))"
```

Expected: unittest PASS；one-liner 输出 `LaTeXTransTuiApp True`。

- [ ] **Step 5: 提交本任务**

Run:

```powershell
git add src/tui/app.py src/tui/app_parts/runner.py
git commit -m "refactor(tui): extract task runner behavior"
```

Expected: commit 成功。

## Task 8: 全量验证、循环导入检查和文档收尾

**Files:**
- Modify: `src/tui/app.py`
- Modify: `src/tui/app_parts/*.py`
- Test: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: 所有前序任务产出的 mixin 和 re-export。
- Produces: 通过完整 TUI app 测试和完整 unittest 套件的拆分结果。

- [ ] **Step 1: 检查 `app_parts` 没有反向导入 `src.tui.app`**

Run:

```powershell
rg -n "src\.tui\.app|from \.app|import app" src/tui/app_parts
```

Expected: 无输出，命令退出码可以是 1。

- [ ] **Step 2: 检查 `app.py` 文件规模已明显下降**

Run:

```powershell
(Get-Content src/tui/app.py).Count
```

Expected: 输出显著低于迁移前的 `1755`，理想值小于 `250`。

- [ ] **Step 3: 运行 TUI app 测试**

Run:

```powershell
python -m unittest tests.test_tui_app
```

Expected: PASS。

- [ ] **Step 4: 运行完整测试套件**

Run:

```powershell
python -m unittest discover tests
```

Expected: PASS。

- [ ] **Step 5: 检查最终 diff 范围**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 只包含 `src/tui/app.py` 和 `src/tui/app_parts/` 下的拆分相关变更；如果计划和 spec 未单独提交，也会包含 `docs/superpowers/specs/2026-07-11-tui-app-split-design.md` 和 `docs/superpowers/plans/2026-07-11-tui-app-split.md`。

- [ ] **Step 6: 提交最终验证或清理**

如果 Task 1-7 已逐步提交且本任务没有代码变更，只记录验证结果即可。若有导入清理或小修复：

```powershell
git add src/tui/app.py src/tui/app_parts
git commit -m "test(tui): verify split app modules"
```

Expected: commit 成功，或没有需要提交的代码变更。

## Self-Review Notes

- Spec 覆盖：计划覆盖了 `app_parts` 新目录、`app.py` 整合层、所有目标模块、兼容 re-export、循环导入约束、测试策略和配置污染风险。
- 占位扫描：计划没有留待后续补全的空白项；机械迁移步骤要求从当前 `src/tui/app.py` 原样搬迁对应代码。
- 类型一致性：所有 mixin 方法名与 spec 和当前 `app.py` 方法名保持一致；`RunnerMixin` 不重复定义 Task 6 已迁移的 Zotero 输入 helper。
- 风险提示：执行时每个新类和新函数必须有 docstring；如果原方法已有 docstring，迁移时原样保留。
