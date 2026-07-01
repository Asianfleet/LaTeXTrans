# Task 7 报告：入口页提交与状态渲染

## 文档查询证据

- 已运行：`npx ctx7@latest docs /textualize/textual "Button Pressed Select value TextArea text current API testing Pilot click"`。
- 查询结果确认 Textual 官方文档中的 `App.run_test()`、`Pilot.click()`、`Button.Pressed` 事件处理示例。
- 已运行：`npx ctx7@latest docs /textualize/textual "Select value property TextArea text property Button.Pressed event Textual widgets"`。
- 查询结果确认 `TextArea.text` 是可读写属性，`Select.value` 保存当前选项值，`Button.Pressed` 可通过事件处理器接收。
- 已运行：`npx ctx7@latest docs /textualize/textual "Static widget update renderable content property render current API"`。
- 查询结果确认 `Static.update()` 用于更新内容区域。当前安装版本本地 API 暴露 `Static.content`，没有 brief 示例中的 `renderable` 属性，因此测试断言使用 `str(static.content)`。

## TDD RED 证据

- 新增入口页直接提交测试后运行：`conda run -n latextrans python -m unittest tests.test_tui_app.TuiEntryPageTests`。
- 结果：2 个 ERROR，均因 `LaTeXTransTuiApp` 缺少 `submit_entry_form`。
- 新增开始按钮点击测试后，临时移除按钮处理器并运行：`conda run -n latextrans python -m unittest tests.test_tui_app.TuiEntryPageTests.test_start_button_submits_entry_form`。
- 结果：1 个 FAIL，点击按钮后 `app.current_task` 仍为 `None`。

## TDD GREEN 证据

- 实现 `submit_entry_form()` 和 `on_button_pressed()` 后运行：`conda run -n latextrans python -m unittest tests.test_tui_app.TuiEntryPageTests`。
- 结果：3 个测试全部通过。
- 最终相关验证运行：`conda run -n latextrans python -m unittest tests.test_tui_app`。
- 结果：7 个测试全部通过。

## 变更文件

- `src/tui/app.py`
  - 引入 `parse_input_items()`、`validate_input_items()` 和 `TaskViewState`。
  - 新增 `current_task: TaskViewState | None`。
  - 新增 `submit_entry_form()`：读取 `Select.value` 和 `TextArea.text`，解析和校验输入，渲染错误文本，创建任务状态，更新进度摘要并切到 progress 页面。
  - 新增 `on_button_pressed()`：处理开始、任务管理、设置和新建任务按钮。
- `tests/test_tui_app.py`
  - 新增 `TuiEntryPageTests`，覆盖有效提交、开始按钮提交和校验错误渲染。

## 自审

- 未启动后台 worker。
- 未调用 runtime runner。
- 未修改 `.superpowers/sdd/progress.md`。
- 未读取 secrets。
- 新增测试方法均包含 docstring。
- 新增生产方法均包含 docstring。
- 最终 diff 仅包含 Task 7 相关代码文件和本报告。

## 顾虑

- Textual 当前版本的 `Static` 没有 `renderable` 属性，brief 示例断言不可用；已基于 Context7 和本地 API 改用 `Static.content`。
- `current_task` 是类属性标注，赋值后会成为实例属性；这符合当前测试和任务需求，但后续若并行运行多个 App 实例，可考虑在初始化生命周期中显式设置实例属性。

## 复审 Important 修复

- 问题：Textual `Select` 处于 blank state 时，`value` 是 `Select.NULL`；原代码直接 `str(value)`，导致未选择输入类型但已输入文本时显示 `unsupported input type: Select.NULL`。
- 文档证据：已运行 `npx ctx7@latest docs /textualize/textual "Select blank state NULL is_blank selection value current API"`，官方文档确认 blank state 的值为 `Select.NULL`，并推荐 `Select.is_blank()` 和 `Select.clear()` 处理该状态。
- 本地 API 证据：已运行 `conda run -n latextrans python -c "from textual.widgets import Select; print(hasattr(Select, 'NULL')); print(hasattr(Select, 'is_blank')); print(Select.NULL)"`，确认当前安装版本支持 `Select.NULL` 和 `Select.is_blank()`。
- RED：新增 `test_submit_entry_form_requires_input_type_when_select_is_blank` 后运行 `conda run -n latextrans python -m unittest tests.test_tui_app.TuiEntryPageTests.test_submit_entry_form_requires_input_type_when_select_is_blank`，结果失败，实际错误文本为 `unsupported input type: Select.NULL`。
- GREEN：改为通过 `input_type_select.is_blank()` 将 blank state 归一为空输入类型，并运行 `conda run -n latextrans python -m unittest tests.test_tui_app`。
- 测试结果：8 个测试全部通过。
- 补强：`test_submit_entry_form_shows_validation_errors` 现在断言校验失败时 `current_task is None`，且页面仍停留在 `PAGE_ENTRY`。
- 范围：本次修复仅修改 `src/tui/app.py`、`tests/test_tui_app.py` 和本报告；未实现 Task 8+。
