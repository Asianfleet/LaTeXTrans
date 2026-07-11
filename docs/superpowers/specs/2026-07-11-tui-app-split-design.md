# TUI App 拆分设计

## 背景

当前 `src/tui/app.py` 是 Textual TUI 的主入口，已经承担了入口页、详情页、设置页、任务事件、历史加载、错误记录、术语表、Zotero 集成和后台任务启动等多类职责。文件长度约 1755 行，且 `LaTeXTransTuiApp` 内部方法大量通过共享状态和 `query_one("#...")` 访问控件。

这种实现短期可工作，但后续维护成本较高：

- 修改一个页面时需要理解整个 app 类。
- 业务逻辑、展示逻辑和 Textual 控件查询混在同一个文件。
- 测试集中依赖 `src.tui.app` 和 `LaTeXTransTuiApp` 的现有方法名。
- 错误记录、Zotero、配置页等功能边界已经明显，但没有模块边界承载。

本次拆分只调整 TUI 代码组织，不改变用户可见行为。

## 目标

- 在 `src/tui` 下新增一个子目录承载拆分后的 app 模块。
- 保留 `src/tui/app.py` 作为 TUI 入口和整合层。
- 按职责拆分当前 `app.py` 的控件、样式、布局和页面逻辑。
- 保留现有 `LaTeXTransTuiApp` 类、`run()` 函数和从 `src.tui.app` 导入常用对象的兼容性。
- 第一阶段尽量做机械迁移，降低行为回归风险。
- 拆分后每个模块都有清晰职责，便于后续继续重构和测试。

## 非目标

本次不实现以下内容：

- 不改变 TUI 页面布局、控件 id、CSS selector 或快捷键语义。
- 不重写 Textual 状态流。
- 不把所有 mixin 立即改造成完全独立的服务类。
- 不拆分 `tests/test_tui_app.py` 为多个测试文件，除非实现过程中必须更新导入。
- 不改变 Zotero API、运行时任务、历史加载、配置保存或错误报告格式。
- 不删除 `src.tui.app` 中现有外部可导入对象的兼容入口。

## 当前耦合判断

`app.py` 的耦合程度较高，主要是中心化 app 类耦合，而不是跨包循环依赖造成的耦合。

主要耦合点：

- `LaTeXTransTuiApp` 同时负责布局、事件分发、配置读写、任务运行、详情页刷新、错误报告解析、Zotero 操作和通知。
- 多个功能共享 `self.tasks`、`self.current_task`、`self.selected_project_name`、`self.selected_task_id`、`self.current_config` 等状态。
- 多数页面逻辑直接通过字符串控件 id 查询 Textual 控件。
- 错误报告和 Zotero 逻辑同时包含文件/API 读取、状态计算、表格渲染和状态提示。
- 测试大量从 `src.tui.app` 导入对象，并直接调用或 patch app 实例方法。

因此第一轮拆分采用“职责模块 + mixin 组合”的方式，先降低文件臃肿和认知负担，不在同一轮改变数据流。

## 总体方案

新增目录：

```text
src/tui/app_parts/
```

`src/tui/app.py` 继续作为入口文件，负责：

- 导入各拆分模块。
- 定义 `LaTeXTransTuiApp`。
- 组合 mixin。
- 初始化 app 级状态。
- 暴露 `run()`。
- re-export 现有测试和外部代码可能从 `src.tui.app` 导入的控件和函数。

拆分模块负责具体实现。第一阶段不追求完全解耦 app 状态，而是把原有方法搬到按职责命名的 mixin 中，保持方法名和调用路径稳定。

## 目录结构

目标结构为：

```text
src/tui/app.py
src/tui/app_parts/
  __init__.py
  constants.py
  styles.py
  widgets.py
  layout.py
  navigation.py
  config_page.py
  task_events.py
  project_views.py
  error_reports.py
  zotero_page.py
  runner.py
```

## 模块职责

### `constants.py`

存放 app 页面 id、表格列宽、进度日志正则和标题常量。

包括：

- `PAGE_ENTRY`
- `PAGE_DETAIL`
- `PAGE_TASKS`
- `PAGE_CONFIG`
- Zotero 表格列宽常量
- 错误记录表格列宽常量
- `PROGRESS_LOG_LINE_RE`
- `APP_TITLE_PLAIN`
- `APP_TITLE_ART`
- `APP_TITLE_ART_COMPACT`
- `APP_TITLE_LINE_STYLES`

### `styles.py`

存放 `DEFAULT_CSS`。

`LaTeXTransTuiApp.DEFAULT_CSS` 从该模块导入并赋值，保持 Textual app 行为不变。

### `widgets.py`

存放独立 Textual 控件和纯展示函数。

包括：

- `app_title_art_width()`
- `build_art_title()`
- `build_app_title()`
- `build_app_title_for_width()`
- `ResponsiveAppTitle`
- `compact_progress_log_for_display()`
- `ErrorReportsTable`
- `ZoteroResultsTable`
- `EntryBatchTextArea`
- `ZoteroSearchInput`
- `ConfigTabbedContent`
- `DetailTabbedContent`

这些对象不应保存业务状态，只通过 Textual 事件调用 app 上已有方法。

### `layout.py`

存放 `LayoutMixin`。

职责：

- `compose()`
- `_compose_config_field()`

该模块只组合 Textual 控件，不处理任务运行、Zotero 搜索或配置保存。配置字段控件生成仍可依赖 `src.tui.config_schema`。

### `navigation.py`

存放 `NavigationMixin`。

职责：

- 主页面切换。
- 左侧项目列表刷新。
- 任务管理表刷新。
- Textual 基础事件分发。
- 快捷键 action。

包括：

- `switch_page()`
- `refresh_project_list()`
- `refresh_task_table()`
- `on_list_view_selected()`
- `on_data_table_row_selected()`
- `on_button_pressed()`
- `on_input_changed()`
- `on_input_submitted()`
- `on_select_changed()`
- `on_switch_changed()`
- `on_text_area_changed()`
- `on_tabbed_content_tab_activated()`
- `action_new_task()`
- `action_project_manager()`
- `action_task_manager()`
- `action_settings()`

### `config_page.py`

存放 `ConfigPageMixin`。

职责：

- 加载 UI 配置。
- 填充设置表单。
- 从表单收集配置。
- 持久化配置变更。
- 刷新 TOML 预览。

包括：

- `load_config_page()`
- `persist_config_form_change()`
- `_is_config_widget()`
- `_config_from_form()`
- `_populate_config_form()`
- `_collect_config_form_values()`
- `_update_config_preview()`

### `task_events.py`

存放 `TaskEventsMixin`。

职责：

- 加载历史输出。
- 合并历史任务与当前任务。
- 处理 runtime 事件。
- 持久化项目元数据。
- 发送项目和任务通知。
- 提供任务状态与项目选择的基础查询。

包括：

- `load_output_history()`
- `handle_runtime_event()`
- `_refresh_selected_project_log()`
- `_notify_task_event()`
- `_should_notify_project_event()`
- `_notify_empty_task_failure()`
- `_selected_project()`
- `_iter_project_states()`
- `_task_is_finished()`
- `_task_is_running()`
- `_stopped_project_count()`
- `_history_output_root()`
- `_merge_history_tasks()`
- `_replace_history_project()`
- `_persist_project_event()`
- `_input_item_for_project()`

### `project_views.py`

存放 `ProjectViewsMixin`。

职责：

- 选择项目。
- 刷新详情页整体内容。
- 展示 TeX 预览。
- 展示项目日志。
- 展示术语表。

包括：

- `select_project()`
- `refresh_detail_page()`
- `_refresh_tex_preview()`
- `_latex_syntax()`
- `_find_tex_preview_path()`
- `_refresh_project_log()`
- `_refresh_terms_table()`
- `_project_terms_path()`

### `error_reports.py`

存放 `ErrorReportsMixin`。

职责：

- 刷新错误记录表。
- 按可用宽度计算错误记录列宽。
- 读取最终和初始错误报告。
- 合并已解决和未解决状态。
- 反查错误位置对应的原文和译文。

包括：

- `_refresh_errors_table()`
- `_refresh_selected_errors_table()`
- `_errors_column_widths()`
- `_errors_table_available_width()`
- `_error_reports_with_status()`
- `_read_error_report()`
- `_initial_error_report_path()`
- `_project_errors_report_path()`
- `_error_report_key()`
- `_error_report_position()`
- `_error_report_type()`
- `_error_report_problem()`
- `_error_status_text()`
- `_error_report_content()`
- `_error_content_root()`
- `_find_error_part_record()`
- `_read_json_list()`
- `_truncated_plain_text()`

### `zotero_page.py`

存放 `ZoteroPageMixin`。

职责：

- 初始化 Zotero 结果表。
- 计算和刷新 Zotero 表格列宽。
- 加载 Zotero 库。
- 普通搜索和自动匹配。
- 维护结果选择状态。
- 导入当前项目 PDF 到选中 Zotero 条目。
- 创建 Zotero adapter。

包括：

- `_initialize_zotero_results_table()`
- `_zotero_column_widths()`
- `_fit_zotero_results_table_columns()`
- `_refresh_zotero_controls()`
- `load_zotero_libraries()`
- `search_zotero_items()`
- `auto_match_zotero_items()`
- `populate_zotero_results()`
- `clear_zotero_results()`
- `toggle_zotero_row_selection()`
- `import_selected_project_to_zotero()`
- `_set_zotero_status()`
- `_zotero_config()`
- `_zotero_adapter()`
- `_zotero_library_value()`
- `_selected_zotero_library()`

### `runner.py`

存放 `RunnerMixin`。

职责：

- 读取入口页输入。
- 创建任务状态。
- 启动 Textual worker。
- 调用 `run_tui_task()`。
- 处理 worker 异常。
- 提供任务输入相关 helper。

包括：

- `submit_entry_form()`
- `_next_task_id()`
- `_selected_task_input_type()`
- `_selected_arxiv_id()`
- `start_current_task()`
- `run_current_task()`

## `app.py` 整合方式

`app.py` 中的类定义改为多 mixin 继承：

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

`app.py` 保留：

- `LaTeXTransTuiApp`
- `run()`
- `BINDINGS`
- `DEFAULT_CSS` 赋值
- `zotero_adapter_factory`
- `__init__()`
- `on_mount()`

`app.py` 也继续从拆分模块导入并暴露以下对象：

- `build_app_title`
- `build_app_title_for_width`
- `app_title_art_width`
- `compact_progress_log_for_display`
- `ResponsiveAppTitle`
- `ErrorReportsTable`
- `ZoteroResultsTable`
- `EntryBatchTextArea`
- `ZoteroSearchInput`
- `ConfigTabbedContent`
- `DetailTabbedContent`

这样现有测试和潜在外部导入路径不需要立即调整。

## 依赖方向

依赖方向保持单向：

```text
app.py
  -> app_parts mixin / widgets / styles / constants
app_parts.*
  -> src.tui.config / config_schema / history / input_parser / runner / state / zotero_adapter
```

`app_parts` 模块不得导入 `src.tui.app`，避免形成循环依赖。

mixin 之间可以通过 `self` 调用现有 app 方法。第一阶段接受这种调用，因为目标是机械拆分；后续如果继续解耦，再把共享逻辑抽成纯函数或小服务。

## 行为兼容性

拆分后必须保持以下兼容性：

- `from src.tui.app import LaTeXTransTuiApp, run` 可用。
- `from src.tui.app import build_app_title, compact_progress_log_for_display` 可用。
- 页面 id 和控件 id 不变。
- `LaTeXTransTuiApp.DEFAULT_CSS` 内容不变。
- `LaTeXTransTuiApp.BINDINGS` 语义不变。
- 现有测试中直接调用的 app 方法名不变。
- `load_history_on_mount=False` 的测试用法不变。
- `zotero_adapter_factory` 的测试替换方式不变。

## 实施顺序

1. 新建 `src/tui/app_parts/__init__.py`。
2. 搬迁常量到 `constants.py`。
3. 搬迁 CSS 到 `styles.py`。
4. 搬迁纯函数和自定义控件到 `widgets.py`。
5. 搬迁 `compose()` 和 `_compose_config_field()` 到 `layout.py`。
6. 搬迁配置页逻辑到 `config_page.py`。
7. 搬迁 Zotero 逻辑到 `zotero_page.py`。
8. 搬迁错误报告逻辑到 `error_reports.py`。
9. 搬迁详情页、日志和术语表逻辑到 `project_views.py`。
10. 搬迁任务事件和历史逻辑到 `task_events.py`。
11. 搬迁入口提交和后台 worker 逻辑到 `runner.py`。
12. 精简 `app.py` 为入口和整合层。
13. 运行 TUI app 测试和完整测试套件。

每一步应保持补丁较小，并在可行时运行至少 `python -m unittest tests.test_tui_app`。

## 测试计划

优先运行：

```text
python -m unittest tests.test_tui_app
```

最终运行：

```text
python -m unittest discover tests
```

重点确认：

- TUI app 可导入。
- 主布局、详情页、配置页和 Zotero tab 结构不变。
- 标题响应式逻辑不变。
- 配置表单即时保存行为不变。
- 项目选择、任务表、历史输出加载行为不变。
- 错误记录表列宽和 resize 行为不变。
- Zotero 搜索、自动匹配、多选和导入行为不变。
- 后台任务事件处理和通知行为不变。

## 风险与缓解

### Mixin 方法互相调用仍有隐式耦合

第一阶段允许 mixin 通过 `self` 调用其他 mixin 方法，因为这是从现有单类结构迁移的最低风险方式。缓解方式是保持方法名不变，并通过现有测试覆盖行为。

### 循环导入风险

所有拆分模块只能从 `app_parts.constants`、`app_parts.widgets` 等基础模块导入，不得导入 `src.tui.app`。`app.py` 作为最终组合层，位于依赖方向顶层。

### 测试导入路径风险

`app.py` 继续 re-export 原有导入对象，避免一次性修改大量测试。后续如果要更新测试导入路径，应作为单独清理任务处理。

### Textual worker 装饰器迁移风险

`run_current_task()` 搬到 `RunnerMixin` 后仍需保留 `@work(thread=True, exclusive=True)`。验证重点是后台任务仍可启动，异常仍通过 `call_from_thread()` 回到 UI 线程。

### UI 配置测试污染风险

涉及配置页的测试必须继续保护真实 `config/ui.toml`，不能因为拆分改变 mock 覆盖范围。实现时应特别确认 `save_ui_config(Path.cwd(), ...)` 的 patch 仍覆盖完整交互生命周期。

## 后续可选重构

本次拆分完成后，可以再单独评估以下改进：

- 将错误报告解析逻辑抽为不依赖 Textual 的纯函数。
- 将 Zotero 搜索和导入状态管理抽为页面模型。
- 将 `query_one("#...")` 集中封装为小型 view accessor，减少字符串 id 分散。
- 将 `tests/test_tui_app.py` 按配置页、错误表、Zotero、任务事件拆分为多个测试文件。
- 为 mixin 间调用建立更明确的协议或轻量基类。

## 决策总结

本次采用 `src/tui/app_parts/` 子目录承载拆分模块，`src/tui/app.py` 保留入口与整合职责。拆分方式优先选择 mixin 组合，保持现有状态模型、方法名、控件 id、CSS 和导入兼容性不变。该方案能显著降低 `app.py` 文件臃肿度，同时避免在同一轮引入大规模行为重构风险。
