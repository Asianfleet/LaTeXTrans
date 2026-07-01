# Task 9 报告：详情页和任务管理页数据填充

## 状态

完成。

## Textual 文档查询证据

按 brief 要求运行：

```powershell
npx ctx7@latest docs /textualize/textual "ListView ListItem Selected DataTable add_columns add_row clear current API"
```

查询结果确认：

- `ListView.Selected` 会在列表项被选择时发布，可由父组件的 `on_list_view_selected` 处理，事件包含 `list_view`、`item` 和 `index`。
- `ListItem` 是 `ListView` 的可聚焦子项，可包含 `Label` 等子组件。
- `DataTable` 使用 `add_columns` 添加列，使用 `add_row` 添加单行，使用 `clear(columns=True)` 清空列和行后重建表格。

另用本项目 `latextrans` conda 环境只读确认已安装 Textual API 签名：

```powershell
conda run -n latextrans python -c "import inspect; from textual.widgets import ListView, DataTable; print('ListView.append', inspect.signature(ListView.append)); print('ListView.clear', inspect.signature(ListView.clear)); print('DataTable.clear', inspect.signature(DataTable.clear)); print('DataTable.add_columns', inspect.signature(DataTable.add_columns)); print('DataTable.add_row', inspect.signature(DataTable.add_row))"
```

确认 `ListView.append` / `clear`、`DataTable.clear(columns=False)`、`add_columns`、`add_row` 可用。

## TDD 证据

RED 1：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiResultViewsTests
```

结果：4 个测试报错，原因分别为 `select_project`、`refresh_project_list`、`refresh_detail_page`、`refresh_task_table` 尚不存在。

GREEN 1：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiResultViewsTests
```

结果：`Ran 4 tests ... OK`。

RED 2：

新增错误报告表格断言后运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiResultViewsTests
```

结果：`errors_table.row_count` 为 0，期望为 1。

GREEN 2：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiResultViewsTests
```

结果：`Ran 4 tests ... OK`。

完整相关验证：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app
```

结果：`Ran 16 tests in 10.744s`，`OK`。运行中 Textual 输出了若干 message pump 超过 0.1 秒的调试提示，但测试退出码为 0。

## 变更文件

- `src/tui/app.py`
  - 新增 `selected_project_name`。
  - 新增 `select_project()`、`refresh_project_list()`、`refresh_detail_page()`、`refresh_task_table()`。
  - 新增 `on_list_view_selected()`，支持从侧栏项目列表进入详情页。
  - runtime 事件归并后刷新项目列表和任务表。
  - 详情页展示 PDF、输出目录、日志路径、错误报告路径和错误信息。
  - TeX 预览只读，优先读取 `project_dir/main.tex`，否则读取项目目录下第一个 `.tex`。
  - 日志内容写入 `RichLog`，同时放入 `project-log-summary` 方便稳定显示和测试。
  - 错误记录页用 `DataTable` 展示错误报告路径和错误信息。
- `tests/test_tui_app.py`
  - 新增 `TuiResultViewsTests` 覆盖项目选择、任务表、项目列表、详情页 artifacts、只读 TeX 预览、日志和错误报告。

## 自审

- 未实现完整编辑器；`#tex-preview` 保持 `read_only=True`，只加载预览文本。
- 未实现配置页保存。
- 未实现 Zotero 导入。
- 未修改 `.superpowers/sdd/progress.md`。
- 未读取 secrets。
- 新增类/函数/测试方法均带 docstring。
- 写入范围限定为用户允许的 `src/tui/app.py`、`tests/test_tui_app.py` 和本报告文件。

## 顾虑

- `RichLog.write()` 在 Textual 中可能延迟到控件尺寸已知后渲染，因此增加了 `project-log-summary` 作为同一日志内容的稳定可见摘要；这会让日志 tab 同时有摘要和滚动日志。
- 当前 TeX 预览只做简单文件选择：优先 `main.tex`，否则项目目录顶层第一个 `.tex`，不递归查找子目录。

## 复审修复：允许组件清单

复审指出 `ListItem` 本身在允许清单内，但 Task 9 初始实现新增并使用了清单外组件 `Label`。修复方式：

- 从 `src/tui/app.py` 移除 `Label` 导入。
- 项目列表项从 `ListItem(Label(...))` 改为 `ListItem(Static(...))`。
- 从 `tests/test_tui_app.py` 移除 `Label` 导入和查询，改为查询 `Static` 内容。
- 未实现 Task 10+，未扩大功能范围。

TDD 修复证据：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiResultViewsTests
```

RED：新增断言确认列表项不应包含 `Label` 子组件，当前实现失败，失败信息为 `Exception not raised`。

GREEN：替换为 `Static` 后同一命令通过，`Ran 4 tests ... OK`。

复审后验证：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app
```

结果：`Ran 16 tests in 11.089s`，`OK`。

```powershell
conda run -n latextrans python -m unittest discover tests
```

结果：`Ran 214 tests in 11.987s`，`OK`。运行期间存在既有 agent 日志和 Textual message pump 调试提示，但命令退出码为 0。
