# Task 4 报告：状态模型和事件归并

## 状态

已完成。

## TDD 证据

### RED

先创建 `tests/test_tui_state.py`，覆盖以下行为：

- `run_start` 设置 `TaskViewState.total`
- `project_start` 创建项目并标记为 `RUNNING`
- `project_complete` 更新项目路径、状态和完成/失败计数
- `project_error` 创建或更新项目并统计失败数

运行命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_state
```

结果：失败，符合预期。

关键错误：

```text
ModuleNotFoundError: No module named 'src.tui.state'
FAILED (errors=1)
```

### GREEN

实现 `src/tui/state.py` 后再次运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_state
```

结果：

```text
Ran 3 tests in 0.000s
OK
```

### 扩展验证

运行相关 TUI 测试集合：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_state tests.test_tui_input_parser tests.test_tui_config tests.test_tui_app
```

结果：

```text
Ran 14 tests in 0.261s
OK
```

## 变更文件

- `src/tui/state.py`
- `tests/test_tui_state.py`
- `.superpowers/sdd/task-4-report.md`

## 实现说明

- 新增 `ProjectStatus` 枚举：`PENDING`、`RUNNING`、`COMPLETED`、`FAILED`。
- 新增 `ProjectViewState`，保存单个项目的展示状态、路径、验证摘要、错误信息和 Zotero 导入状态。
- 新增 `TaskViewState`，保存输入类型、输入列表、总数、完成数、失败数、当前运行项目、事件列表和项目列表。
- `TaskViewState.apply_event()` 会保留原始事件，并根据 `run_start`、`project_start`、`project_complete`、`project_error` 归并状态。
- `project_complete` 和 `project_error` 后会从项目列表重新统计 `completed` 与 `failed`，避免重复事件导致计数漂移。

## 自审

- 新增类、函数和测试方法均包含 docstring。
- 只实现状态模型，没有实现 runner 或 Textual UI。
- 字段名按 brief 使用。
- 未修改 `.superpowers/sdd/progress.md`。
- 未读取 secrets。

## 顾虑

- `running_project` 在项目完成或失败后当前仍保留最后启动的项目名；brief 未要求完成时清空，因此没有额外改变该语义。
- 未知事件目前只会记录到 `events`，不改变派生状态；这与当前状态模型的最小归并需求一致。
