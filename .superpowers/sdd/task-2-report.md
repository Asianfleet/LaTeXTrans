# SDD Task 2 报告：UI 配置初始化与保存

## 实现内容

- 新增 `src/tui/config.py`，提供 TUI 专用配置管理接口。
- 定义 `UI_CONFIG_PATH = Path("config") / "ui.toml"`。
- 实现 `ensure_ui_config(project_root: Path) -> Path`：
  - 确保 `config/` 目录存在。
  - 若 `config/ui.toml` 已存在，直接返回。
  - 若不存在，优先从 `config/default.toml` 复制。
  - 当 `default.toml` 缺失时，从 `config/template.toml` 复制。
  - 两者都缺失时抛出 `FileNotFoundError`。
- 实现 `load_ui_config(project_root: Path) -> dict[str, Any]`，加载前自动确保 UI 配置存在。
- 实现 `save_ui_config(project_root: Path, config: dict[str, Any]) -> Path`，只写入 `config/ui.toml`，不回写 `config/default.toml`。
- 新增 `tests/test_tui_config.py`，覆盖默认配置复制、模板回退、保存读取 round trip。

## TDD RED 证据

先创建 `tests/test_tui_config.py`，未实现 `src.tui.config` 前运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_config
```

结果：

```text
ModuleNotFoundError: No module named 'src.tui.config'
FAILED (errors=1)
```

失败原因符合预期：测试引用的新模块尚不存在。

## TDD GREEN 证据

实现 `src/tui/config.py` 后再次运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_config
```

结果：

```text
Ran 3 tests in 0.034s
OK
```

## 变更文件

- `src/tui/config.py`
- `tests/test_tui_config.py`
- `.superpowers/sdd/task-2-report.md`

## 自审

- 新增函数和测试类/测试方法均包含 docstring。
- 文件读写显式使用 UTF-8。
- `save_ui_config` 只写入 `config/ui.toml`，不会修改 `config/default.toml`。
- 未读取 secrets。
- 未修改 `.superpowers/sdd/progress.md`。
- 未触及 brief 限定之外的源码或测试文件。

## 顾虑

- 目标测试已覆盖本任务 brief 中列出的行为；未运行完整测试套件，因为任务要求的验证命令聚焦 `tests.test_tui_config`。
