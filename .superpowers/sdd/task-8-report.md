# Task 8 验证报告

## 总结

- 状态：DONE
- 结论：完成全量验证；发现并修复 1 个真实回归，随后目标测试与全量测试全部通过。

## 执行记录

### 1. 反向导入检查

原 brief 命令：

```powershell
rg -n "src\.tui\.app|from \.app|import app" src/tui/app_parts
```

输出：

```text
src/tui/app_parts\zotero_page.py:12:from src.tui.app_parts.constants import (
src/tui/app_parts\widgets.py:12:from src.tui.app_parts.constants import (
src/tui/app_parts\error_reports.py:13:from src.tui.app_parts.constants import (
src/tui/app_parts\runner.py:10:from src.tui.app_parts.constants import PAGE_ENTRY
src/tui/app_parts\project_views.py:11:from src.tui.app_parts.constants import PAGE_DETAIL
src/tui/app_parts\project_views.py:12:from src.tui.app_parts.widgets import compact_progress_log_for_display
src/tui/app_parts\navigation.py:19:from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS
src/tui/app_parts\layout.py:23:from src.tui.app_parts.constants import PAGE_CONFIG, PAGE_DETAIL, PAGE_ENTRY, PAGE_TASKS
src/tui/app_parts\layout.py:24:from src.tui.app_parts.widgets import (
```

判断：这些都是合法的 `src.tui.app_parts...` 导入，被原始正则里的 `src\.tui\.app` 子串误匹配，不是 `app_parts -> src.tui.app` 反向导入。

更精确检查：

```powershell
rg -n "from src\.tui\.app import|import src\.tui\.app\b|from \.app\b|import app\b" src/tui/app_parts
```

结果：无输出，退出码 1。

结论：`src/tui/app_parts` 中没有真实的 `src.tui.app`、`from .app` 或裸 `import app` 反向导入。

### 2. `app.py` 文件规模

命令：

```powershell
(Get-Content src/tui/app.py).Count
```

结果：`142`

结论：显著低于迁移前 `1755`，并满足理想目标 `< 250`。

### 3. `tests.test_tui_app`

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app
```

结果：`Ran 86 tests in 212.730s`，`OK`

### 4. 全量测试

首次执行：

```powershell
conda run -n latextrans python -m unittest discover tests
```

结果：失败。

失败用例：

- `tests.test_tui_app.TuiResultViewsTests.test_errors_table_recomputes_columns_after_terminal_resize`

失败现象：

- 错误记录表在终端从 `80x40` 放大到 `140x40` 后，`source` 列宽没有增长，断言 `6 not greater than 6`。

处理：

- 在 `src/tui/app.py` 增加应用级 `on_resize()`。
- 在 resize 后通过 `call_after_refresh()` 触发 `_refresh_tables_after_resize()`。
- 当详情页激活 `errors-tab` 时重绘错误表；当激活 `zotero-tab` 时重算 Zotero 结果表列宽。
- 保留 `PAGE_DETAIL` 等从 `src.tui.app` 暴露的常量导入，避免破坏现有测试和兼容 re-export。

修复后复验：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app.TuiResultViewsTests.test_errors_table_recomputes_columns_after_terminal_resize
conda run -n latextrans python -m unittest tests.test_tui_app
conda run -n latextrans python -m unittest discover tests
```

结果：

- 定点回归：`Ran 1 test in 2.249s`，`OK`
- `tests.test_tui_app`：`Ran 86 tests in 212.730s`，`OK`
- 全量测试：`Ran 310 tests in 214.739s`，`OK`

### 5. diff 范围检查

命令：

```powershell
git status --short
git diff --stat
```

结果（提交前）：

```text
 M src/tui/app.py
```

```text
 src/tui/app.py | 22 ++++++++++++++++++++++
 1 file changed, 22 insertions(+)
```

结论：最终代码变更仅落在允许修改的 `src/tui/app.py`。

## 代码变更摘要

- `src/tui/app.py`
  - 新增应用级 `on_resize()` 处理。
  - 新增 `_refresh_tables_after_resize()`，在终端尺寸变化后重算错误表和 Zotero 表的列宽相关布局。

## 提交建议

- 若需要提交，本任务使用：`test(tui): verify split app modules`

## AGENTS lessons

- 本次没有新增需要写入 AGENTS.md 的项目经验；现有规则已覆盖“验证前跑全量测试”“不要误判反向导入正则结果”“保留兼容 re-export”的约束。

## Task 8 Fixer 追加修复记录

### 6. 评审修复

背景：

- 基线提交：`5301448 test(tui): verify split app modules`
- 评审指出 `src/tui/app.py` 中 `_refresh_tables_after_resize()` 的详情页刷新条件过宽，会在非 `PAGE_TASKS` 且存在 `selected_project_name` 时进入详情页刷新分支。

修复：

- 将详情页刷新条件从：

```python
if main_switcher.current != PAGE_TASKS and self.selected_project_name is not None:
```

收敛为：

```python
if (
    main_switcher.current == PAGE_DETAIL
    and self.selected_project_name is not None
):
```

结果：

- 现在仅当主页面确实激活 `PAGE_DETAIL` 且已选择项目时，才刷新错误表和 Zotero 结果表。
- `PAGE_TASKS`、`PAGE_ENTRY`、`PAGE_CONFIG` 的 resize 行为未引入额外刷新。

### 7. 最终 `app.py` 行数

命令：

```powershell
(Get-Content src/tui/app.py).Count
```

结果：`167`

说明：此前报告中的 `142` 已过时；在 Task 8 后续加入 resize 刷新逻辑后，最终文件行数为 `167`。

### 8. 修复后验证

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app
conda run -n latextrans python -m unittest discover tests
(Get-Content src/tui/app.py).Count
```

结果：

- `tests.test_tui_app`：`Ran 86 tests in 211.577s`，`OK`
- 全量测试：`Ran 310 tests in 213.956s`，`OK`
- `app.py` 行数：`167`

### 9. 修复摘要

- `src/tui/app.py`
  - 将 `_refresh_tables_after_resize()` 的详情页刷新条件显式限定为 `PAGE_DETAIL` 激活时才执行。
- `.superpowers/sdd/task-8-report.md`
  - 追加本次修复说明。
  - 更新最终 `app.py` 行数。
  - 记录本次必跑测试命令与结果。
