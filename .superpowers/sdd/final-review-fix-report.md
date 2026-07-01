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
