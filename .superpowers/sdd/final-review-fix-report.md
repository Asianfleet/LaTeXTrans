# Final Review Fix Report

## 范围

- Base commit before fixes: `a429b42`
- 修复最终审查提出的 4 个 Important。
- 未修改 `.superpowers/sdd/progress.md`。
- 代码变更仅触及允许文件：`src/tui/app.py`、`src/tui/runner.py`、`src/tui/state.py`、`tests/test_tui_app.py`、`tests/test_tui_runner.py`、`tests/test_tui_state.py`。

## Textual 文档核对

按全局约束在实现 Textual 组件、按钮消息和测试前使用 Context7 查询当前官方文档：

```powershell
npx ctx7@latest library textual "Textual App run_test Button Pressed Input value Select value DataTable add rows ProgressBar current API"
npx ctx7@latest docs /textualize/textual "Textual App run_test Button Pressed Input value Select value DataTable add rows ProgressBar current API"
```

核对结果：

- 官方库 ID 为 `/textualize/textual`。
- `App.run_test()` 是当前 headless 测试入口，返回 pilot，可用于 `press()` / `click()` / `pause()`。
- `Button.Pressed` 是按钮消息；当前 `Button.press()` 会发送 `Pressed` 消息。
- `Select.value`、`Input.value`、`DataTable.add_columns()` / `add_row()`、`ProgressBar.update()` 仍是当前可用 API。
- 本次新增 UI 只使用允许组件：`Input`、`Select`、`Button`、`Static`、`DataTable`，未引入清单外组件。

## Important 1：首次直接启动 TUI 缺少 `config/ui.toml`

### 修复

- `src/tui/runner.py` 在加载 runtime 配置前调用 `ensure_ui_config(Path.cwd())`。
- runtime 实际加载 `ensure_ui_config()` 返回路径，确保首次启动时 `config/ui.toml` 已创建。

### TDD 证据

RED：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_state tests.test_tui_runner tests.test_tui_app
```

关键失败：

```text
FAIL: test_run_tui_task_ensures_missing_ui_config_before_loading
AssertionError: False is not true
```

GREEN：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_state tests.test_tui_runner tests.test_tui_app
```

结果：

```text
Ran 29 tests in 17.284s
OK
```

## Important 2：prepare 阶段跳过部分输入导致 UI 进度卡住

### 修复

- `src/tui/runner.py` 在 `prepare_projects()` 后比较原始输入和 prepared project 列表。
- 对未产出 prepared project 的输入生成 UI 可见 `project_error` 事件。
- 成功项目仍继续进入 `runtime.run_projects()`。
- UI 原有 `TaskViewState` 会把该 `project_error` 计入 failed，因此 `completed + failed` 可达到原始 total。

### TDD 证据

RED：

```text
FAIL: test_run_tui_task_emits_errors_for_prepare_skipped_inputs
AssertionError: ['project_complete'] != ['project_error', 'project_complete']
```

GREEN：

```text
Ran 29 tests in 17.284s
OK
```

## Important 3：术语表详情页未实现实际查看

### 修复

- `ProjectViewState` 增加：
  - `project_terms_path`
  - `project_terms_decisions_path`
- `TaskViewState._copy_project_fields()` 复制 runtime 事件中的术语表路径字段。
- `LaTeXTransTuiApp.refresh_detail_page()` 调用 `_refresh_terms_table()`。
- `#terms-table` 展示：
  - 术语表 CSV 路径
  - 决策记录 JSON 路径
  - 可解析 CSV 术语行
- 该页保持只读查看，不提供编辑行为。

### TDD 证据

RED：

```text
AttributeError: 'ProjectViewState' object has no attribute 'project_terms_path'
TypeError: ProjectViewState.__init__() got an unexpected keyword argument 'project_terms_path'
```

GREEN：

```text
Ran 29 tests in 17.284s
OK
```

## Important 4：“导入 Zotero”按钮未接入 adapter

### 修复

- 详情页新增显式 Zotero 输入控件：
  - `#zotero-api-key-input`
  - `#zotero-script-path-input`
  - `#zotero-library-id-input`
  - `#zotero-library-type-select`
  - `#zotero-item-key-input`
  - `#zotero-status`
- `import-zotero-button` 接入 `import_selected_project_to_zotero()`。
- 只对当前 selected project 的 `pdf_path` 调用 `ZoteroAdapter.attach_pdf(item_key, pdf_path, library_id, library_type)`。
- 不自动匹配 Zotero 条目。
- 不新建顶层 item；adapter 只负责附加到现有 item。
- 不读取 secret 环境变量；API key 只能来自 UI 输入。
- 成功更新 `ProjectViewState.zotero_status` 和 `#zotero-status`。
- 失败更新可见错误，不改变项目翻译状态或 completed 计数。

### TDD 证据

RED：

```text
textual.css.query.NoMatches: No nodes match '#zotero-api-key-input'
```

实现控件后，按钮点击测试继续暴露测试路径问题：隐藏页坐标点击未触发按钮。按 Textual 当前文档和本地源码核对，改用 `Button.press()` 发送 `Button.Pressed` 消息后验证按钮接线。

GREEN：

```text
Ran 29 tests in 17.284s
OK
```

## 测试结果

聚焦测试：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_state tests.test_tui_runner tests.test_tui_app
```

结果：

```text
Ran 29 tests in 17.284s
OK
```

全量测试：

```powershell
conda run -n latextrans python -m unittest discover tests
```

结果：

```text
Ran 227 tests in 17.135s
OK
```

备注：全量测试输出包含既有 TerminologyAgent 日志和 Textual 慢 message pump 提示，但退出码为 0，测试通过。

## 变更文件

- `src/tui/app.py`
  - 渲染术语表路径、决策路径和 CSV 术语行。
  - 新增 Zotero 显式输入控件和状态消息。
  - 接入导入按钮到 `ZoteroAdapter.attach_pdf()`。
- `src/tui/runner.py`
  - 首次运行前确保 UI 配置存在。
  - 为 prepare 阶段跳过项生成 `project_error`。
- `src/tui/state.py`
  - 保存项目术语表路径字段。
- `tests/test_tui_app.py`
  - 覆盖术语表详情页渲染。
  - 覆盖 Zotero 导入成功和失败。
- `tests/test_tui_runner.py`
  - 覆盖缺失 UI 配置时自动初始化。
  - 覆盖 prepare 跳过项生成失败事件且成功项目继续。
- `tests/test_tui_state.py`
  - 覆盖术语表路径字段事件归并。

## 自审

- 新增生产函数和测试方法均有 docstring。
- 未读取 `auth.json` 或任何 `_API_KEY` / `_KEY` 环境变量。
- 未修改 `.superpowers/sdd/progress.md`。
- 未回退他人改动。
- Zotero 导入只使用用户显式输入的 existing item 信息。
- UI 新增组件均在允许清单内。
- 最终 diff 仅包含任务相关代码、测试和本报告。

## 顾虑

- prepare skipped 输入的匹配是 runner 层基于 prepared project 路径名的保守推断；它覆盖本地目录、常见归档名和 URL 文件名场景，但 runtime 当前没有返回精确 skip 列表，因此无法做到完全来源级追踪。
- Zotero UI 的 API key 输入是最小实现，未持久化到配置文件，也未做异步 worker 化；真实网络请求可能阻塞 UI，后续可独立改为后台 worker。

## Re-review 修复：prepare 全部跳过与 remote skip 稳定性

### 问题 1：all-skipped prepare 抛 `ValueError` 时 undercount

re-review 指出：当 `runtime.prepare_projects()` 因全部输入被跳过而抛出 `ValueError` 时，runner 之前不会运行 `_emit_prepare_skip_events()`，外层 app 只能把异常转成一个 `project_error`，多输入 batch 的进度仍可能卡住。

修复：

- `run_tui_task()` 捕获 `runtime.prepare_projects()` 抛出的 `ValueError`。
- 捕获后先为所有 submitted items 发出 `project_error`。
- 随后重抛原始 `ValueError`，保持 UI 仍能展示总体 prepare 错误。
- 不调用 `runtime.run_projects()`，因为没有 prepared project。

TDD RED：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_runner tests.test_tui_app
```

关键失败：

```text
FAIL: test_run_tui_task_emits_all_prepare_errors_when_prepare_raises
AssertionError: [] != ['project_error', 'project_error']
```

GREEN：

```text
Ran 28 tests in 19.989s
OK
```

### 问题 2：remote skip 用 URL 名称匹配 prepared path 不稳定

re-review 指出：remote archive 下载后可能重命名，之前用 URL 文件名匹配 prepared project path 会把有效 remote 误报 skipped。

修复：

- `_prepare_skipped_items()` 增加 `input_type` 参数。
- `input_type == "remote"` 时不再按 URL 字符串匹配 project path。
- remote 只按数量保守判断：若 `len(projects) < len(items)`，标记末尾超出数量的输入为 skipped。
- 数量相等时不发 skipped 事件，避免误伤已 prepared 的 remote project。

TDD RED：

```text
FAIL: test_run_tui_task_remote_skip_uses_counts_not_url_names
AssertionError: ['project_error', 'project_error', 'project_complete'] != ['project_error', 'project_complete']
```

GREEN：

```text
Ran 28 tests in 19.989s
OK
```

### 问题 3：Zotero 按钮测试依赖 `Button.press()` 异步消息导致全量脆弱

本地全量测试暴露：`Button.press()` post 的 `Button.Pressed` 消息可能延迟到 app teardown 后才处理，导致 `#zotero-status` 查询 NoMatches。

修复：

- Zotero 成功/失败行为测试改为直接调用 `app.import_selected_project_to_zotero()`，验证同步业务逻辑。
- 新增 `test_import_zotero_button_branch_calls_import_method`，直接构造带 `button.id` 的简单事件对象调用 `on_button_pressed()`，只验证按钮 ID 分支调用导入方法。
- 不再用 `Button.press()` 验证同步导入行为，避免 DOM teardown race。

### Re-review 测试结果

聚焦测试：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_runner tests.test_tui_app
```

结果：

```text
Ran 28 tests in 19.989s
OK
```

全量测试：

```powershell
conda run -n latextrans python -m unittest discover tests
```

结果：

```text
Ran 230 tests in 17.612s
OK
```

备注：输出仍包含既有 TerminologyAgent 日志和 Textual 慢 message pump 提示，但退出码为 0。

### Re-review 变更文件

- `src/tui/runner.py`
  - 捕获 prepare `ValueError` 并为全部 submitted items 发出 `project_error`。
  - remote skip 推断改为数量匹配。
- `tests/test_tui_runner.py`
  - 覆盖 all-skipped prepare `ValueError`。
  - 覆盖 remote prepared project 重命名时不误报成功输入 skipped。
- `tests/test_tui_app.py`
  - 稳定 Zotero 导入测试，避免异步 button message race。
  - 增加按钮分支同步单元测试。

## Final re-review 修复：remote skip 不绑定具体 URL

### 问题

上一轮 remote skip 改为按数量取 `items[len(projects):]` 后仍存在歧义：如果第一个 remote URL 失败、第二个 URL 成功，runner 会误把第二个 URL 标成 skipped。runtime 当前不返回精确 remote skip 列表，因此 runner 不能可靠地把 skipped 绑定到具体 URL。

### 修复

- `input_type == "remote"` 且 prepare 成功时，不再生成任何 per-URL `project_error`。
- 改为发送 `{"type": "run_start", "total": len(projects)}`，把 UI total 重置为真实 prepared project 数。
- `input_type == "remote"` 且 prepare 全部失败抛 `ValueError` 时，发送 `{"type": "run_start", "total": 0}` 后重抛，避免误标具体 URL。
- local 输入仍保留 path/name 匹配，并继续为 skipped item 生成 per-item `project_error`。

### TDD RED

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_runner tests.test_tui_app
```

关键失败：

```text
FAIL: test_run_tui_task_remote_skip_resets_total_without_url_errors
AssertionError: ['project_error', 'project_complete'] != ['run_start', 'project_complete']

FAIL: test_run_tui_task_remote_prepare_error_resets_total_without_url_errors
AssertionError: [{'type': 'project_error', ...}] != [{'type': 'run_start', 'total': 0}]
```

### GREEN 与验证

聚焦测试：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_runner tests.test_tui_app
```

结果：

```text
Ran 29 tests in 15.439s
OK
```

全量测试：

```powershell
conda run -n latextrans python -m unittest discover tests
```

结果：

```text
Ran 231 tests in 17.573s
OK
```

备注：输出包含既有 TerminologyAgent 日志和 Textual 慢 message pump 提示，退出码为 0。

## Final re-review 修复：app 不再把 remote prepare 全失败重映射到首个 URL

### 问题

- `src/tui/runner.py` 在 remote prepare 全失败时会先发送 `{"type": "run_start", "total": 0}`，然后重抛异常。
- `src/tui/app.py` 的 `run_current_task()` 通用异常处理随后仍会补发一个 `project_error`，`project_name` 取 `task.inputs[0]`。
- 结果 UI 状态会变成 `total=0, failed=1`，并错误地把失败绑定到第一个 remote URL，违背“remote skip 不绑定具体 URL”的修复意图。

### 修复

- 在 `LaTeXTransTuiApp.run_current_task()` 的异常分支中增加特例判断：
  - 当 `task.input_type == "remote"` 且 `task.total == 0` 时，直接返回。
- 这样当 runner 已明确把 remote prepare 结果表达为 `run_start total=0` 时，app 不再额外构造 per-input `project_error`。
- 非 remote 路径或 remote 但 `total > 0` 的异常路径保持原有可见错误行为。

### TDD RED

新增测试：

- `tests.test_tui_app.TuiProgressTests.test_remote_prepare_failure_does_not_remap_error_to_input_url`

RED 命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiProgressTests.test_remote_prepare_failure_does_not_remap_error_to_input_url
```

结果：

```text
FAIL: test_remote_prepare_failure_does_not_remap_error_to_input_url
AssertionError: 1 != 0
```

### GREEN 与验证

目标测试：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiProgressTests.test_remote_prepare_failure_does_not_remap_error_to_input_url
```

结果：

```text
Ran 1 test in 0.939s
OK
```

联测：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app tests.test_tui_runner
```

结果：

```text
Ran 30 tests in 16.230s
OK
```

### 本次变更文件

- `src/tui/app.py`
  - remote `total == 0` 的异常整合路径不再补发 `project_error`。
- `tests/test_tui_app.py`
  - 增加 remote prepare 全失败回归测试。
- `.superpowers/sdd/final-review-fix-report.md`
  - 追加本次 final re-review fix 记录与 RED/GREEN 证据。
