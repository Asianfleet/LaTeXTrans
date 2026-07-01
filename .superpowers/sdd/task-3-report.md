# Task 3 Report: 输入解析和校验

## 状态

已完成 SDD Task 3：新增 TUI 输入类型、批量文本解析和按输入类型校验逻辑。

## TDD 证据

### RED

先创建 `tests/test_tui_input_parser.py`，覆盖：

- 逗号和换行批量拆分
- arXiv ID 和 arXiv URL 接受
- arXiv 输入拒绝非 arXiv URL
- local 输入拒绝 HTTP/HTTPS URL
- remote 输入接受 HTTP/HTTPS URL
- remote 输入拒绝非 HTTP/HTTPS URL

运行命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_input_parser
```

结果：失败，符合预期。

关键错误：

```text
ModuleNotFoundError: No module named 'src.tui.input_parser'
FAILED (errors=1)
```

### GREEN

随后创建 `src/tui/input_parser.py`，实现：

- `InputType = Literal["arxiv", "local", "remote"]`
- `parse_input_items(input_type, text)`
- `validate_input_items(input_type, items)`

再次运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_input_parser
```

结果：

```text
Ran 6 tests in 0.000s
OK
```

## 变更文件

- `src/tui/input_parser.py`
- `tests/test_tui_input_parser.py`
- `.superpowers/sdd/task-3-report.md`

未修改 `.superpowers/sdd/progress.md`。

## 自审

- 新增函数均包含 docstring。
- 新增测试方法均包含 docstring。
- 仅实现 brief 指定接口，没有扩展 UI 或调用链。
- 校验错误文本与 brief 预期保持一致。
- 使用 `conda run -n latextrans python -m unittest tests.test_tui_input_parser` 完成 RED/GREEN 验证。

## 顾虑

- `local` 类型首版仅拒绝 HTTP/HTTPS URL，不检查路径是否实际存在；这与 brief 给出的实现范围一致。
- `remote` 类型仅校验 URL scheme，不校验归档扩展名；测试名称包含 archive，但 brief 的期望实现只要求 HTTP/HTTPS。
- arXiv URL 校验接受所有 `*.arxiv.org` 或 `arxiv.org` HTTP/HTTPS URL，不限制路径为 `/abs/`；这是按 brief 示例实现保持的宽松策略。
