# Task 8 报告：后台 worker 运行与进度展示

## 状态

已完成。

## Textual 文档查询证据

- 执行：`npx ctx7@latest docs /textualize/textual "work decorator thread worker call_from_thread current API"`
- 结果要点：Textual 官方 workers 文档确认同步 API 应使用 `@work(thread=True)` 创建线程 worker；线程 worker 内应避免直接调用 UI 方法，使用 `App.call_from_thread()` 回到主线程更新 UI。
- 执行：`npx ctx7@latest docs /textualize/textual "import work decorator textual current import path"`
- 结果要点：Context7 返回的当前文档示例使用 `from textual.work import work`。本项目 conda 环境安装的 Textual 为 `8.2.8`，实际没有 `textual.work` 子模块，但顶层 `from textual import work` 可用。因此实现采用本环境可运行的顶层导入，并保持 `@work(thread=True)` 语义。

## TDD 证据

### RED

- 先添加 `TuiProgressTests.test_handle_runtime_event_updates_task_and_log`。
- 执行：`conda run -n latextrans python -m unittest tests.test_tui_app.TuiProgressTests`
- 失败证据：`AttributeError: 'LaTeXTransTuiApp' object has no attribute 'handle_runtime_event'`。

### RED 扩展

- 增加 `TuiProgressTests.test_start_current_task_runs_mocked_runner_in_worker`，使用 mock runner，避免真实下载或翻译。
- 执行：`conda run -n latextrans python -m unittest tests.test_tui_app.TuiProgressTests`
- 失败证据：缺少 `handle_runtime_event`，且 `src.tui.app` 尚无可 patch 的 `run_tui_task`。

### GREEN

- 实现 `handle_runtime_event()`、`start_current_task()` 和 `@work(thread=True)` 的 `run_current_task()`。
- 执行：`conda run -n latextrans python -m unittest tests.test_tui_app.TuiProgressTests`
- 通过证据：`Ran 2 tests ... OK`。

## 最终验证

- 执行：`conda run -n latextrans python -m unittest tests.test_tui_app`
- 结果：`Ran 10 tests ... OK`。输出包含 Textual 测试环境的 slow-task 诊断行。
- 执行：`conda run -n latextrans python -m unittest discover tests`
- 结果：`Ran 208 tests ... OK`。输出包含既有 `TerminologyAgent` 日志和 Textual slow-task 诊断行。

## 变更文件

- `src/tui/app.py`
  - 提交入口页后调用 `start_current_task()`。
  - 新增 `handle_runtime_event()`，通过 `TaskViewState.apply_event()` 更新任务状态，并刷新 `#progress-summary` 和 `#event-log`。
  - 新增 `start_current_task()` 和线程 worker `run_current_task()`。
  - worker 调用 `run_tui_task()`，并用 `call_from_thread()` 将 runtime 事件交回 UI 线程。
- `tests/test_tui_app.py`
  - 新增进度事件测试。
  - 新增 worker 启动测试，mock `run_tui_task()`，不执行真实下载或翻译。
  - 调整既有入口测试，对 `start_current_task()` 做 mock，避免入口行为测试触发真实 runner。
- `.superpowers/sdd/task-8-report.md`
  - 记录本任务实现、验证和顾虑。

## 自审

- 只修改了允许的实现/测试文件，并新增用户要求的报告文件。
- 未修改 `.superpowers/sdd/progress.md`。
- 未读取 secrets。
- 新增函数和测试方法均有 docstring。
- 最终 diff 仅包含任务相关代码、测试和报告。

## 顾虑

- Context7 当前文档示例给出 `from textual.work import work`，但本项目 conda 环境的 Textual 8.2.8 不存在该子模块；实现采用 `from textual import work` 以保证本环境测试可运行。
- Textual `run_test()` 在本环境会输出 slow-task 诊断行，但测试退出码为 0，未观察到功能性失败。
