# Task 6 Report: Textual 主布局与页面切换

## 状态

已完成。

## Textual 文档查询证据

按 brief 要求先查询 Textual 最新官方文档，未凭记忆实现 API。

命令：

```powershell
npx ctx7@latest docs /textualize/textual "ContentSwitcher Button Footer ListView TextArea Select DataTable TabbedContent ProgressBar RichLog current API"
```

关键证据：
- Context7 返回 `ContentSwitcher` 官方文档片段，示例使用 `ContentSwitcher(initial="datatable")`，并通过 `self.query_one(ContentSwitcher).current = "datatable"` 切换页面。
- Context7 返回 `ContentSwitcher.current` reactive 属性说明：`current` 接收子组件 `id` 字符串，设置后切换可见内容；也可读取当前页面 id。
- Context7 返回 `ListView` 官方示例，确认 `ListView` 可作为列表控件直接组合到 `compose()`。

补充查询：

```powershell
npx ctx7@latest docs /textualize/textual "Footer BINDINGS Button.Pressed Select TextArea DataTable TabbedContent ProgressBar RichLog ListView official current API"
npx ctx7@latest docs /textualize/textual "TabbedContent initial parameter TabPane id TextArea read_only Select options current API"
```

关键证据：
- `Footer` 官方文档说明 `yield Footer()` 会自动显示当前可用 key bindings。
- `TabbedContent` 官方文档说明可用 `TabbedContent(initial="...")` 设置初始 tab，且 `TabPane` 需要 `id` 才能程序化切换。
- `Select` 官方文档说明选项为显示文本和值组成的 tuple 序列。

## TDD 证据

RED 先写测试：
- 修改 `tests/test_tui_app.py`，新增 `TuiLayoutTests`。
- 覆盖应用组合 `#project-list`、`#main-switcher`、`Footer`。
- 覆盖 `switch_page(page_id)` 更新 `ContentSwitcher.current`。

RED 命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiLayoutTests
```

RED 结果：

```text
ImportError: cannot import name 'PAGE_CONFIG' from 'src.tui.app'
FAILED (errors=1)
```

GREEN 实现后目标测试命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiLayoutTests
```

GREEN 结果：

```text
Ran 2 tests in 1.114s
OK
```

最终相关测试命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app
```

最终结果：

```text
Ran 4 tests in 1.146s
OK
```

## 变更文件

- `src/tui/app.py`
  - 新增页面常量：`PAGE_ENTRY`、`PAGE_PROGRESS`、`PAGE_DETAIL`、`PAGE_TASKS`、`PAGE_CONFIG`。
  - 新增 Textual 主布局：左侧按钮和项目列表、右侧 `ContentSwitcher`、底部 `Footer`。
  - 新增入口、进度、详情、任务管理、配置页面的首版占位组件。
  - 新增 `switch_page(page_id: str) -> None`。
  - 新增快捷键 action：新建任务、任务管理、设置。
- `tests/test_tui_app.py`
  - 新增 `TuiLayoutTests` 覆盖主布局和页面切换。

## 自审

- 未实现任务提交、后台运行、详情填充或配置保存。
- 未读取 secrets。
- 未修改 `.superpowers/sdd/progress.md`。
- 只暂存和提交 Task 6 相关文件。
- 所有新增类和函数/方法均有 docstring。
- `ContentSwitcher.current` 的用法与 Context7 官方文档一致。
- `Footer` 只通过 `yield Footer()` 组合，依赖官方说明自动显示绑定。

## 顾虑

- brief 的示例包含 `Switch` 组件；本任务实现保留了配置页开关占位。如果后续全局组件清单实际未包含 `Switch`，应在后续任务统一替换为清单内组件。
- 当前测试验证布局骨架和切页行为，不验证每个占位控件的业务语义；这是按 Task 6 范围刻意限制的。
