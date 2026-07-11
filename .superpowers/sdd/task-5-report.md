# Task 5 Report

## Summary

已完成 Task 5，将详情页/术语表逻辑与错误报告逻辑从 `src/tui/app.py` 拆分到两个独立 mixin：

- `src/tui/app_parts/project_views.py`
- `src/tui/app_parts/error_reports.py`

`LaTeXTransTuiApp` 已更新为组合这两个 mixin，方法名保持不变：

- `select_project()`
- `refresh_detail_page()`
- `_refresh_errors_table()`

两个新 mixin 均未导入 `src.tui.app`。

## Scope

按 brief 执行，未迁移 Zotero 页面或 runner 逻辑，未修改计划/spec 文件，未编辑 brief 之外的代码文件。

## Baseline Verification

在迁移前运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app -k "refresh_detail_page"
conda run -n latextrans python -m unittest tests.test_tui_app -k "errors_table"
conda run -n latextrans python -m unittest tests.test_tui_app -k "terms_table"
conda run -n latextrans python -m unittest tests.test_tui_app -k "compact_progress"
```

结果：全部 PASS。

## Implementation Notes

### Step 1

- 已完成：读取 brief、确认工作树干净、运行基线测试。

### Step 2

- 已完成：新建 `src/tui/app_parts/project_views.py`。
- 实现说明：原样迁入以下方法，保留原 docstring 与行为：
  - `select_project()`
  - `refresh_detail_page()`
  - `_refresh_tex_preview()`
  - `_latex_syntax()`
  - `_find_tex_preview_path()`
  - `_refresh_project_log()`
  - `_refresh_terms_table()`
  - `_project_terms_path()`

### Step 3

- 已完成：新建 `src/tui/app_parts/error_reports.py`。
- 实现说明：原样迁入以下方法，保留原 docstring 与行为：
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

### Step 4

- 已完成：在 `src/tui/app.py` 引入并组合 `ProjectViewsMixin`、`ErrorReportsMixin`。
- 实现说明：删除 `app.py` 中已迁移的方法实现，仅保留类组合。

### Step 5

- 已完成：运行迁移后验证命令。

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app -k "refresh_detail_page"
conda run -n latextrans python -m unittest tests.test_tui_app -k "errors_table"
conda run -n latextrans python -m unittest tests.test_tui_app -k "terms_table"
conda run -n latextrans python -m unittest tests.test_tui_app -k "compact_progress"
```

结果：全部 PASS。

## Issue Encountered

迁移后首次测试失败，原因是 `tests.test_tui_app` 仍从 `src.tui.app` 导入：

- `PAGE_DETAIL`
- `compact_progress_log_for_display`

这两个符号虽然已由 mixin 直接消费，但 `app.py` 仍需继续对外暴露以维持既有导入接口。已在 `src/tui/app.py` 补回相关导入，之后测试恢复通过。

## Files Changed

- `src/tui/app.py`
- `src/tui/app_parts/project_views.py`
- `src/tui/app_parts/error_reports.py`

## Diff Review

最终 diff 仅包含本任务相关拆分：

- `app.py` 删除详情页/术语表/错误报告方法实现，改为 mixin 组合。
- 新增 `project_views.py`。
- 新增 `error_reports.py`。

## Commit

已创建提交：

- `refactor(tui): extract project detail views`

## Concerns

无功能性遗留问题。唯一需要注意的是 `src.tui.app` 仍保留部分符号转发，以兼容现有测试和外部导入。

## AGENTS Lesson

本次未发现需要新增到 AGENTS.md 的新规则。
