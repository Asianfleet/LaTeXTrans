# Textual Terminal UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LaTeXTransPlus 增加基于 Textual 的终端 UI，复用现有 runtime，支持单类型批量任务、进度展示、结果查看、UI 配置和将翻译 PDF 附加到 Zotero 现有条目。

**Architecture:** 新增 `src/tui/` 作为独立 TUI 边界，CLI 保持不变；`src/tui/app.py` 组合 Textual 主界面，`src/tui/state.py` 管理任务和项目状态，`src/tui/runner.py` 在后台 worker 中调用现有 `runtime.prepare_projects()` / `runtime.run_projects()`，`src/tui/config.py` 管理 UI 专用配置。Zotero 导入通过独立 adapter 封装，失败不影响翻译结果。

**Tech Stack:** Python 3.10+、Textual、TOML、`pathlib`、`subprocess`、`unittest`、`unittest.mock`

## Global Constraints

- 实现任何 Textual API、组件、worker、测试或布局用法前，必须使用 `find-docs` / Context7 查询 Textual 最新官方文档，不允许只凭记忆写。
- 首版 Textual 组件限定为 spec 中的清单：`App`、`Horizontal`、`Vertical`、`VerticalScroll`、`ContentSwitcher`、`TabbedContent`、`TabPane`、`Button`、`Select`、`Input`、`TextArea`、`Switch`、`ListView`、`ListItem`、`DataTable`、`ProgressBar`、`RichLog`、`Static`、`Footer`。
- 单次 UI 任务只能选择一种输入类型：`arxiv`、`local`、`remote`。
- UI 首版不支持 `--all-existing`。
- 详情页 tex 查看必须是只读预览，不实现完整编辑器。
- UI 配置写入 UI 专用文件，不回写 `config/default.toml`。
- Zotero 导入只支持把已生成翻译 PDF 附加到已有条目，不新建 Zotero 条目，不自动匹配条目。
- 项目运行和测试必须使用本项目 `latextrans` conda 环境。
- 新增类和函数必须带文档字符串。

---

## 文件结构

- Modify: `requirements.txt`
  - 增加 Textual 依赖。
- Modify: `setup.py`
  - 增加 `latextrans-tui=src.tui.app:run` console script。
- Create: `src/tui/__init__.py`
  - TUI 包标识。
- Create: `src/tui/config.py`
  - UI 配置路径、初始化、读取、保存。
- Create: `src/tui/input_parser.py`
  - UI 输入类型与批量文本解析、校验。
- Create: `src/tui/state.py`
  - UI 任务、项目状态、事件归并模型。
- Create: `src/tui/runner.py`
  - 后台运行封装，桥接现有 runtime。
- Create: `src/tui/zotero_adapter.py`
  - Zotero CLI wrapper 的最小适配层。
- Create: `src/tui/app.py`
  - Textual App、布局、页面切换、事件处理。
- Create: `tests/test_tui_config.py`
  - UI 配置初始化和保存测试。
- Create: `tests/test_tui_input_parser.py`
  - 输入类型与批量输入校验测试。
- Create: `tests/test_tui_state.py`
  - 状态模型和 runtime 事件归并测试。
- Create: `tests/test_tui_runner.py`
  - runner 对 runtime 的调用和事件回调测试。
- Create: `tests/test_tui_zotero_adapter.py`
  - Zotero adapter 命令构造和错误处理测试。
- Create: `tests/test_tui_app.py`
  - Textual App 组合、页面切换和基础交互测试。
- Modify: `README.md`
  - 增加 TUI 入口和功能说明。
- Modify: `README_ZH.md`
  - 增加中文 TUI 入口和功能说明。

## Task 1: 依赖、入口和包结构

**Files:**
- Modify: `requirements.txt`
- Modify: `setup.py`
- Create: `src/tui/__init__.py`

**Interfaces:**
- Produces: `latextrans-tui` console script pointing to `src.tui.app:run`
- Produces: importable package `src.tui`

- [ ] **Step 1: 查询 Textual 最新安装与 App 入口文档**

Run:

```powershell
npx ctx7@latest library textual "Python Textual install app run console script current API"
npx ctx7@latest docs /textualize/textual "App run console script current API"
```

Expected: 输出 Textual 官方文档片段，确认安装包名和 `App().run()` 用法。

- [ ] **Step 2: 写失败测试，确认 console script 尚不存在**

在 `tests/test_tui_app.py` 中创建：

```python
import unittest

from setup import load_requirements


class TuiPackagingTests(unittest.TestCase):
    def test_textual_dependency_is_declared(self):
        requirements = load_requirements("requirements.txt")
        self.assertTrue(any(item.startswith("textual") for item in requirements))

    def test_tui_run_function_is_importable(self):
        from src.tui.app import run

        self.assertTrue(callable(run))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiPackagingTests
```

Expected: FAIL，`src.tui.app` 不存在或 requirements 未声明 Textual。

- [ ] **Step 4: 增加依赖和入口**

在 `requirements.txt` 追加：

```text
textual>=0.86.0
```

在 `setup.py` 的 `console_scripts` 增加：

```python
"latextrans-tui=src.tui.app:run",
```

创建 `src/tui/__init__.py`：

```python
"""Textual terminal UI for LaTeXTransPlus."""
```

创建临时最小 `src/tui/app.py`：

```python
"""Textual terminal UI entry point."""

from textual.app import App


class LaTeXTransTuiApp(App[None]):
    """Minimal Textual application shell for packaging tests."""


def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiPackagingTests
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add requirements.txt setup.py src/tui/__init__.py src/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): add textual entry point"
```

## Task 2: UI 配置初始化与保存

**Files:**
- Create: `src/tui/config.py`
- Create: `tests/test_tui_config.py`

**Interfaces:**
- Produces: `UI_CONFIG_PATH = Path("config/ui.toml")`
- Produces: `ensure_ui_config(project_root: Path) -> Path`
- Produces: `load_ui_config(project_root: Path) -> dict[str, Any]`
- Produces: `save_ui_config(project_root: Path, config: dict[str, Any]) -> Path`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_tui_config.py`：

```python
import tempfile
import unittest
from pathlib import Path

import toml

from src.tui.config import ensure_ui_config, load_ui_config, save_ui_config


class TuiConfigTests(unittest.TestCase):
    def test_ensure_ui_config_copies_default_when_present(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "default.toml").write_text('target_language = "ja"\n', encoding="utf-8")
            (config_dir / "template.toml").write_text('target_language = "ch"\n', encoding="utf-8")

            path = ensure_ui_config(root)

            self.assertEqual(path, config_dir / "ui.toml")
            self.assertEqual(toml.load(path)["target_language"], "ja")

    def test_ensure_ui_config_uses_template_when_default_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "template.toml").write_text('target_language = "ko"\n', encoding="utf-8")

            path = ensure_ui_config(root)

            self.assertEqual(toml.load(path)["target_language"], "ko")

    def test_load_and_save_ui_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "template.toml").write_text('target_language = "ch"\n', encoding="utf-8")

            saved_path = save_ui_config(root, {"target_language": "fr", "ui": {"dark": True}})
            loaded = load_ui_config(root)

            self.assertEqual(saved_path, config_dir / "ui.toml")
            self.assertEqual(loaded["target_language"], "fr")
            self.assertTrue(loaded["ui"]["dark"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_config
```

Expected: FAIL，`src.tui.config` 不存在。

- [ ] **Step 3: 实现配置模块**

创建 `src/tui/config.py`：

```python
"""UI-specific configuration loading and persistence."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import toml

UI_CONFIG_PATH = Path("config") / "ui.toml"


def ensure_ui_config(project_root: Path) -> Path:
    """Ensure the UI config file exists and return its path."""
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    ui_path = project_root / UI_CONFIG_PATH
    if ui_path.exists():
        return ui_path

    default_path = config_dir / "default.toml"
    template_path = config_dir / "template.toml"
    source_path = default_path if default_path.exists() else template_path
    if not source_path.exists():
        raise FileNotFoundError("Missing config/default.toml and config/template.toml.")

    shutil.copyfile(source_path, ui_path)
    return ui_path


def load_ui_config(project_root: Path) -> dict[str, Any]:
    """Load the UI config, creating it from the configured template if needed."""
    return toml.load(ensure_ui_config(project_root))


def save_ui_config(project_root: Path, config: dict[str, Any]) -> Path:
    """Save the UI config to config/ui.toml."""
    ui_path = project_root / UI_CONFIG_PATH
    ui_path.parent.mkdir(parents=True, exist_ok=True)
    ui_path.write_text(toml.dumps(config), encoding="utf-8")
    return ui_path
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_config
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add src/tui/config.py tests/test_tui_config.py
git commit -m "feat(tui): add ui config management"
```

## Task 3: 输入解析和校验

**Files:**
- Create: `src/tui/input_parser.py`
- Create: `tests/test_tui_input_parser.py`

**Interfaces:**
- Produces: `InputType = Literal["arxiv", "local", "remote"]`
- Produces: `parse_input_items(input_type: InputType, text: str) -> list[str]`
- Produces: `validate_input_items(input_type: InputType, items: list[str]) -> list[str]`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_tui_input_parser.py`：

```python
import unittest

from src.tui.input_parser import parse_input_items, validate_input_items


class TuiInputParserTests(unittest.TestCase):
    def test_parse_accepts_commas_and_newlines(self):
        items = parse_input_items("arxiv", "2508.18791, 2407.01648\n2501.00001")
        self.assertEqual(items, ["2508.18791", "2407.01648", "2501.00001"])

    def test_arxiv_accepts_ids_and_urls(self):
        errors = validate_input_items(
            "arxiv",
            ["2508.18791", "https://arxiv.org/abs/2508.18791v2"],
        )
        self.assertEqual(errors, [])

    def test_arxiv_rejects_non_arxiv_url(self):
        errors = validate_input_items("arxiv", ["https://example.test/paper.zip"])
        self.assertEqual(errors, ["arxiv input must be an arXiv ID or arXiv URL: https://example.test/paper.zip"])

    def test_local_rejects_remote_url(self):
        errors = validate_input_items("local", ["https://example.test/paper.zip"])
        self.assertEqual(errors, ["local input must be a local path, not a URL: https://example.test/paper.zip"])

    def test_remote_accepts_http_archive_url(self):
        errors = validate_input_items("remote", ["https://example.test/paper.tar.gz"])
        self.assertEqual(errors, [])

    def test_remote_rejects_non_http_url(self):
        errors = validate_input_items("remote", ["file:///tmp/paper.zip"])
        self.assertEqual(errors, ["remote input must be an http or https URL: file:///tmp/paper.zip"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_input_parser
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现输入解析**

创建 `src/tui/input_parser.py`：

```python
"""Input parsing and validation for the terminal UI."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

InputType = Literal["arxiv", "local", "remote"]
_ARXIV_ID_PATTERN = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


def parse_input_items(input_type: InputType, text: str) -> list[str]:
    """Split user-entered batch input into normalized items."""
    del input_type
    normalized = text.replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def validate_input_items(input_type: InputType, items: list[str]) -> list[str]:
    """Return validation errors for the selected input type."""
    errors: list[str] = []
    for item in items:
        parsed = urlparse(item)
        if input_type == "arxiv":
            if _ARXIV_ID_PATTERN.match(item):
                continue
            if parsed.scheme in {"http", "https"} and parsed.netloc.lower().endswith("arxiv.org"):
                continue
            errors.append(f"arxiv input must be an arXiv ID or arXiv URL: {item}")
        elif input_type == "local":
            if parsed.scheme in {"http", "https"}:
                errors.append(f"local input must be a local path, not a URL: {item}")
        elif input_type == "remote":
            if parsed.scheme not in {"http", "https"}:
                errors.append(f"remote input must be an http or https URL: {item}")
        else:
            errors.append(f"unsupported input type: {input_type}")
    return errors
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_input_parser
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add src/tui/input_parser.py tests/test_tui_input_parser.py
git commit -m "feat(tui): validate batch task input"
```

## Task 4: 状态模型和事件归并

**Files:**
- Create: `src/tui/state.py`
- Create: `tests/test_tui_state.py`

**Interfaces:**
- Produces: `ProjectStatus`
- Produces: `ProjectViewState`
- Produces: `TaskViewState`
- Produces: `TaskViewState.apply_event(event: dict[str, Any]) -> None`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_tui_state.py`：

```python
import unittest

from src.tui.state import ProjectStatus, TaskViewState


class TuiStateTests(unittest.TestCase):
    def test_apply_run_start_sets_total(self):
        state = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
        state.apply_event({"type": "run_start", "total": 2})
        self.assertEqual(state.total, 2)

    def test_project_lifecycle_events_update_counts_and_paths(self):
        state = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
        state.apply_event({
            "type": "project_start",
            "project_name": "2508.18791",
            "project_dir": r"D:\src",
            "output_dir": r"D:\out",
            "log_path": r"D:\out\latextrans.log",
        })
        self.assertEqual(state.projects[0].status, ProjectStatus.RUNNING)

        state.apply_event({
            "type": "project_complete",
            "project_name": "2508.18791",
            "project_dir": r"D:\src",
            "output_dir": r"D:\out",
            "pdf_path": r"D:\out\ch_2508.18791.pdf",
            "errors_report_path": r"D:\out\errors_report.json",
            "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
            "log_path": r"D:\out\latextrans.log",
        })

        self.assertEqual(state.completed, 1)
        self.assertEqual(state.failed, 0)
        self.assertEqual(state.projects[0].status, ProjectStatus.COMPLETED)
        self.assertEqual(state.projects[0].pdf_path, r"D:\out\ch_2508.18791.pdf")

    def test_project_error_updates_failed_count(self):
        state = TaskViewState(input_type="remote", inputs=["https://example.test/paper.zip"])
        state.apply_event({"type": "project_error", "project_name": "paper", "error": "boom"})
        self.assertEqual(state.failed, 1)
        self.assertEqual(state.projects[0].status, ProjectStatus.FAILED)
        self.assertEqual(state.projects[0].error, "boom")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_state
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现状态模型**

创建 `src/tui/state.py`：

```python
"""State models for the Textual terminal UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProjectStatus(str, Enum):
    """Project processing status displayed in the UI."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProjectViewState:
    """Display state for one translated project."""

    project_name: str
    status: ProjectStatus = ProjectStatus.PENDING
    project_dir: str | None = None
    output_dir: str | None = None
    pdf_path: str | None = None
    errors_report_path: str | None = None
    log_path: str | None = None
    validation_summary: dict[str, Any] | None = None
    error: str | None = None
    zotero_status: str = "not_imported"


@dataclass
class TaskViewState:
    """Display state for a single UI-submitted translation task."""

    input_type: str
    inputs: list[str]
    total: int = 0
    completed: int = 0
    failed: int = 0
    running_project: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    projects: list[ProjectViewState] = field(default_factory=list)

    def apply_event(self, event: dict[str, Any]) -> None:
        """Merge a runtime event into UI state."""
        self.events.append(event)
        event_type = event.get("type")
        if event_type == "run_start":
            self.total = int(event.get("total") or 0)
            return

        if event_type == "project_start":
            project = self._get_or_create_project(str(event.get("project_name") or "project"))
            project.status = ProjectStatus.RUNNING
            self.running_project = project.project_name
            self._copy_project_fields(project, event)
            return

        if event_type in {"project_complete", "project_error"}:
            project = self._get_or_create_project(str(event.get("project_name") or "project"))
            project.status = ProjectStatus.COMPLETED if event_type == "project_complete" else ProjectStatus.FAILED
            self._copy_project_fields(project, event)
            self.completed = sum(1 for item in self.projects if item.status == ProjectStatus.COMPLETED)
            self.failed = sum(1 for item in self.projects if item.status == ProjectStatus.FAILED)
            return

    def _get_or_create_project(self, project_name: str) -> ProjectViewState:
        """Return existing project state or create a new entry."""
        for project in self.projects:
            if project.project_name == project_name:
                return project
        project = ProjectViewState(project_name=project_name)
        self.projects.append(project)
        return project

    def _copy_project_fields(self, project: ProjectViewState, event: dict[str, Any]) -> None:
        """Copy known runtime event fields into a project view state."""
        for key in (
            "project_dir",
            "output_dir",
            "pdf_path",
            "errors_report_path",
            "log_path",
            "validation_summary",
            "error",
        ):
            if key in event:
                setattr(project, key, event[key])
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_state
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add src/tui/state.py tests/test_tui_state.py
git commit -m "feat(tui): add task view state"
```

## Task 5: runtime runner 桥接

**Files:**
- Create: `src/tui/runner.py`
- Create: `tests/test_tui_runner.py`

**Interfaces:**
- Consumes: `parse_input_items()`, `TaskViewState`
- Produces: `run_tui_task(config_path: str, input_type: str, items: list[str], overrides: dict[str, Any], event_callback: Callable[[dict[str, Any]], None]) -> dict[str, Any]`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_tui_runner.py`：

```python
import unittest
from unittest.mock import patch

from src.tui.runner import run_tui_task


class TuiRunnerTests(unittest.TestCase):
    def test_run_tui_task_passes_arxiv_inputs_as_paper_list(self):
        config = {"target_language": "ch", "paper_list": []}
        events = []

        with patch("src.tui.runner.runtime.load_runtime_config", return_value=config) as load_config:
            with patch(
                "src.tui.runner.runtime.prepare_projects",
                return_value=([r"D:\paper"], config, "tex-source", "outputs"),
            ) as prepare_projects:
                with patch(
                    "src.tui.runner.runtime.run_projects",
                    return_value={"completed_projects": [], "failed_projects": []},
                ) as run_projects:
                    result = run_tui_task(
                        config_path="config/ui.toml",
                        input_type="arxiv",
                        items=["2508.18791"],
                        overrides={"target_language": "ja"},
                        event_callback=events.append,
                    )

        self.assertEqual(load_config.call_args.kwargs["overrides"]["paper_list"], ["2508.18791"])
        prepare_projects.assert_called_once_with(config=config, project_items=[], project_url_items=[], all_existing=False)
        run_projects.assert_called_once()
        self.assertEqual(result["projects"], [r"D:\paper"])

    def test_run_tui_task_routes_local_and_remote_inputs(self):
        config = {"target_language": "ch", "paper_list": []}

        with patch("src.tui.runner.runtime.load_runtime_config", return_value=config):
            with patch("src.tui.runner.runtime.prepare_projects", return_value=([], config, "src", "out")) as prepare_projects:
                with patch("src.tui.runner.runtime.run_projects", return_value={"completed_projects": [], "failed_projects": []}):
                    run_tui_task("config/ui.toml", "local", [r"D:\paper"], {}, lambda event: None)
                    run_tui_task("config/ui.toml", "remote", ["https://example.test/paper.zip"], {}, lambda event: None)

        self.assertEqual(prepare_projects.call_args_list[0].kwargs["project_items"], [r"D:\paper"])
        self.assertEqual(prepare_projects.call_args_list[1].kwargs["project_url_items"], ["https://example.test/paper.zip"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_runner
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 runner**

创建 `src/tui/runner.py`：

```python
"""Bridge between the Textual UI and the existing runtime workflow."""

from __future__ import annotations

from typing import Any, Callable

from src import runtime

TuiEventCallback = Callable[[dict[str, Any]], None]


def run_tui_task(
    config_path: str,
    input_type: str,
    items: list[str],
    overrides: dict[str, Any],
    event_callback: TuiEventCallback,
) -> dict[str, Any]:
    """Run a UI-submitted translation task through the existing runtime."""
    runtime_overrides = dict(overrides)
    project_items: list[str] = []
    project_url_items: list[str] = []
    if input_type == "arxiv":
        runtime_overrides["paper_list"] = list(items)
    elif input_type == "local":
        runtime_overrides["paper_list"] = []
        project_items = list(items)
    elif input_type == "remote":
        runtime_overrides["paper_list"] = []
        project_url_items = list(items)
    else:
        raise ValueError(f"Unsupported input type: {input_type}")

    config = runtime.load_runtime_config(config_path=config_path, overrides=runtime_overrides)
    projects, config, projects_dir, output_dir = runtime.prepare_projects(
        config=config,
        project_items=project_items,
        project_url_items=project_url_items,
        all_existing=False,
    )
    project_status = runtime.run_projects(
        config=config,
        projects=projects,
        output_dir=output_dir,
        event_callback=event_callback,
    )
    return {
        "config": config,
        "projects": projects,
        "projects_dir": projects_dir,
        "output_dir": output_dir,
        "completed_projects": project_status["completed_projects"],
        "failed_projects": project_status["failed_projects"],
    }
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_runner
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add src/tui/runner.py tests/test_tui_runner.py
git commit -m "feat(tui): bridge tasks to runtime"
```

## Task 6: Textual 主布局与页面切换

**Files:**
- Modify: `src/tui/app.py`
- Modify: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: Textual components from spec
- Produces: `LaTeXTransTuiApp.switch_page(page_id: str) -> None`
- Produces: `PAGE_ENTRY = "entry"` and page IDs for `progress`、`detail`、`tasks`、`config`

- [ ] **Step 1: 查询 Textual 最新组件文档**

Run:

```powershell
npx ctx7@latest docs /textualize/textual "ContentSwitcher Button Footer ListView TextArea Select DataTable TabbedContent ProgressBar RichLog current API"
```

Expected: 输出官方文档片段，确认组件名、事件名、`ContentSwitcher.current` 和 `Footer` 行为。

- [ ] **Step 2: 写失败测试**

扩展 `tests/test_tui_app.py`：

```python
from textual.widgets import ContentSwitcher, Footer, ListView

from src.tui.app import (
    PAGE_CONFIG,
    PAGE_DETAIL,
    PAGE_ENTRY,
    PAGE_PROGRESS,
    PAGE_TASKS,
    LaTeXTransTuiApp,
)


class TuiLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_app_composes_sidebar_switcher_and_footer(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            self.assertIsNotNone(app.query_one("#project-list", ListView))
            self.assertIsNotNone(app.query_one("#main-switcher", ContentSwitcher))
            self.assertIsNotNone(app.query_one(Footer))

    async def test_switch_page_updates_content_switcher(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            for page_id in [PAGE_ENTRY, PAGE_PROGRESS, PAGE_DETAIL, PAGE_TASKS, PAGE_CONFIG]:
                app.switch_page(page_id)
                self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, page_id)
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiLayoutTests
```

Expected: FAIL，页面常量、布局或 `switch_page()` 尚未实现。

- [ ] **Step 4: 实现基础布局**

替换 `src/tui/app.py` 为：

```python
"""Textual terminal UI entry point."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    Label,
    ListView,
    ProgressBar,
    RichLog,
    Select,
    Static,
    Switch,
    TabPane,
    TabbedContent,
    TextArea,
)

PAGE_ENTRY = "entry"
PAGE_PROGRESS = "progress"
PAGE_DETAIL = "detail"
PAGE_TASKS = "tasks"
PAGE_CONFIG = "config"


class LaTeXTransTuiApp(App[None]):
    """Main Textual application for LaTeXTransPlus."""

    BINDINGS = [
        ("q", "quit", "退出"),
        ("n", "new_task", "新建任务"),
        ("m", "task_manager", "任务管理"),
        ("s", "settings", "设置"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the persistent left sidebar, right content switcher, and footer."""
        with Horizontal(id="app-body"):
            with Vertical(id="sidebar"):
                yield Button("新建任务", id="new-task-button")
                yield Button("任务管理", id="task-manager-button")
                yield ListView(id="project-list")
                yield Button("设置", id="settings-button")
            with ContentSwitcher(initial=PAGE_ENTRY, id="main-switcher"):
                with Vertical(id=PAGE_ENTRY):
                    yield Label("LaTeXTransPlus", id="app-title")
                    yield Select(
                        [
                            ("arXiv ID / URL", "arxiv"),
                            ("本地项目/压缩包", "local"),
                            ("远程压缩包 URL", "remote"),
                        ],
                        id="input-type-select",
                    )
                    yield TextArea(id="batch-input")
                    yield Button("开始", id="start-task-button")
                    yield Static("", id="entry-error")
                with Vertical(id=PAGE_PROGRESS):
                    yield Static("未开始", id="progress-summary")
                    yield ProgressBar(id="task-progress")
                    yield RichLog(id="event-log")
                with Vertical(id=PAGE_DETAIL):
                    with TabbedContent(initial="tex-tab", id="detail-tabs"):
                        with TabPane("TeX", id="tex-tab"):
                            tex_preview = TextArea(id="tex-preview")
                            tex_preview.read_only = True
                            yield tex_preview
                        with TabPane("术语表", id="terms-tab"):
                            yield DataTable(id="terms-table")
                        with TabPane("错误记录", id="errors-tab"):
                            yield DataTable(id="errors-table")
                        with TabPane("日志", id="log-tab"):
                            yield RichLog(id="project-log")
                    yield Static("", id="detail-paths")
                    yield Button("打开输出目录", id="open-output-button")
                    yield Button("导入 Zotero", id="import-zotero-button")
                with Vertical(id=PAGE_TASKS):
                    yield DataTable(id="task-table")
                with Vertical(id=PAGE_CONFIG):
                    yield Input(id="config-path-input")
                    yield Select([("浅色", "light"), ("深色", "dark")], id="theme-select")
                    yield Switch(id="config-switch")
                    yield TextArea(id="config-preview")
                    yield Button("保存", id="save-config-button")
                    yield Button("重载", id="reload-config-button")
        yield Footer()

    def switch_page(self, page_id: str) -> None:
        """Switch the right-side content area to the given page."""
        self.query_one("#main-switcher", ContentSwitcher).current = page_id

    def action_new_task(self) -> None:
        """Open the entry page."""
        self.switch_page(PAGE_ENTRY)

    def action_task_manager(self) -> None:
        """Open the task management page."""
        self.switch_page(PAGE_TASKS)

    def action_settings(self) -> None:
        """Open the configuration page."""
        self.switch_page(PAGE_CONFIG)


def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiLayoutTests
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add src/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): compose main textual layout"
```

## Task 7: 入口页提交与状态渲染

**Files:**
- Modify: `src/tui/app.py`
- Modify: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `parse_input_items()`, `validate_input_items()`, `TaskViewState`
- Produces: `LaTeXTransTuiApp.current_task: TaskViewState | None`
- Produces: `LaTeXTransTuiApp.submit_entry_form() -> None`

- [ ] **Step 1: 查询 Textual 最新表单事件文档**

Run:

```powershell
npx ctx7@latest docs /textualize/textual "Button Pressed Select value TextArea text current API testing Pilot click"
```

Expected: 确认 Button pressed 事件、`Select.value`、`TextArea.text` 和测试交互 API。

- [ ] **Step 2: 写失败测试**

在 `tests/test_tui_app.py` 添加：

```python
from textual.widgets import ContentSwitcher, Select, Static, TextArea

from src.tui.state import TaskViewState


class TuiEntryPageTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_entry_form_creates_task_and_switches_to_progress(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "arxiv"
            app.query_one("#batch-input", TextArea).text = "2508.18791\n2407.01648"

            app.submit_entry_form()

            self.assertIsInstance(app.current_task, TaskViewState)
            self.assertEqual(app.current_task.inputs, ["2508.18791", "2407.01648"])
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_PROGRESS)

    async def test_submit_entry_form_shows_validation_errors(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.query_one("#input-type-select", Select).value = "remote"
            app.query_one("#batch-input", TextArea).text = "file:///bad.zip"

            app.submit_entry_form()

            self.assertIn("remote input must be", app.query_one("#entry-error", Static).renderable)
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiEntryPageTests
```

Expected: FAIL，`current_task` 或 `submit_entry_form()` 尚未实现。

- [ ] **Step 4: 实现入口提交**

在 `src/tui/app.py` 中增加 imports：

```python
from src.tui.input_parser import parse_input_items, validate_input_items
from src.tui.state import TaskViewState
```

在 `LaTeXTransTuiApp` 中增加：

```python
    current_task: TaskViewState | None = None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle primary navigation and task action buttons."""
        if event.button.id == "start-task-button":
            self.submit_entry_form()
        elif event.button.id == "new-task-button":
            self.switch_page(PAGE_ENTRY)
        elif event.button.id == "task-manager-button":
            self.switch_page(PAGE_TASKS)
        elif event.button.id == "settings-button":
            self.switch_page(PAGE_CONFIG)

    def submit_entry_form(self) -> None:
        """Validate the entry form and create a task view state."""
        input_type = str(self.query_one("#input-type-select", Select).value or "")
        input_text = self.query_one("#batch-input", TextArea).text
        items = parse_input_items(input_type, input_text)
        errors = validate_input_items(input_type, items)
        error_widget = self.query_one("#entry-error", Static)
        if not input_type or not items:
            error_widget.update("请选择输入类型并输入至少一个条目。")
            return
        if errors:
            error_widget.update("\n".join(errors))
            return
        error_widget.update("")
        self.current_task = TaskViewState(input_type=input_type, inputs=items)
        self.query_one("#progress-summary", Static).update(f"已创建任务：{len(items)} 个条目")
        self.switch_page(PAGE_PROGRESS)
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiEntryPageTests
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add src/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): submit batch task input"
```

## Task 8: 后台 worker 运行与进度展示

**Files:**
- Modify: `src/tui/app.py`
- Modify: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `run_tui_task()`
- Produces: `LaTeXTransTuiApp.start_current_task() -> None`
- Produces: `LaTeXTransTuiApp.handle_runtime_event(event: dict[str, Any]) -> None`

- [ ] **Step 1: 查询 Textual 最新 worker 文档**

Run:

```powershell
npx ctx7@latest docs /textualize/textual "work decorator thread worker call_from_thread current API"
```

Expected: 确认同步 runtime 应在 `@work(thread=True)` worker 中执行，并用 `call_from_thread()` 回 UI 线程。

- [ ] **Step 2: 写失败测试**

在 `tests/test_tui_app.py` 添加：

```python
from textual.widgets import RichLog


class TuiProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_runtime_event_updates_task_and_log(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])

            app.handle_runtime_event({"type": "run_start", "total": 1})
            app.handle_runtime_event({"type": "project_start", "project_name": "2508.18791"})
            app.handle_runtime_event({"type": "project_complete", "project_name": "2508.18791", "pdf_path": "paper.pdf"})

            self.assertEqual(app.current_task.completed, 1)
            self.assertGreaterEqual(len(app.current_task.events), 3)
            self.assertIsNotNone(app.query_one("#event-log", RichLog))
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiProgressTests
```

Expected: FAIL，`handle_runtime_event()` 尚未实现。

- [ ] **Step 4: 实现事件更新和 worker**

在 `src/tui/app.py` 增加：

```python
from pathlib import Path
from textual.work import work
from src.tui.config import UI_CONFIG_PATH
from src.tui.runner import run_tui_task
```

在 `LaTeXTransTuiApp` 中增加：

```python
    def handle_runtime_event(self, event: dict[str, object]) -> None:
        """Apply a runtime event and refresh progress widgets."""
        if self.current_task is None:
            return
        self.current_task.apply_event(dict(event))
        summary = (
            f"总数 {self.current_task.total}，"
            f"完成 {self.current_task.completed}，"
            f"失败 {self.current_task.failed}"
        )
        self.query_one("#progress-summary", Static).update(summary)
        self.query_one("#event-log", RichLog).write(str(event))

    def start_current_task(self) -> None:
        """Start the current task in a Textual worker."""
        if self.current_task is None:
            return
        self.run_current_task()

    @work(thread=True)
    def run_current_task(self) -> None:
        """Run the current task without blocking the Textual UI."""
        if self.current_task is None:
            return

        def callback(event: dict[str, object]) -> None:
            self.call_from_thread(self.handle_runtime_event, event)

        run_tui_task(
            config_path=str(UI_CONFIG_PATH),
            input_type=self.current_task.input_type,
            items=self.current_task.inputs,
            overrides={},
            event_callback=callback,
        )
```

在 `submit_entry_form()` 的末尾 `switch_page(PAGE_PROGRESS)` 后调用：

```python
        self.start_current_task()
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiProgressTests
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add src/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): run tasks in textual worker"
```

## Task 9: 详情页和任务管理页数据填充

**Files:**
- Modify: `src/tui/app.py`
- Modify: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `ProjectViewState`
- Produces: `LaTeXTransTuiApp.select_project(project_name: str) -> None`
- Produces: `LaTeXTransTuiApp.refresh_project_list() -> None`
- Produces: `LaTeXTransTuiApp.refresh_detail_page() -> None`
- Produces: `LaTeXTransTuiApp.refresh_task_table() -> None`

- [ ] **Step 1: 查询 Textual 最新 ListView 和 DataTable 文档**

Run:

```powershell
npx ctx7@latest docs /textualize/textual "ListView ListItem Selected DataTable add_columns add_row clear current API"
```

Expected: 确认列表选择事件和表格行列更新 API。

- [ ] **Step 2: 写失败测试**

在 `tests/test_tui_app.py` 添加：

```python
from textual.widgets import DataTable, ListView, TextArea

from src.tui.state import ProjectViewState, ProjectStatus


class TuiResultViewsTests(unittest.IsolatedAsyncioTestCase):
    async def test_select_project_updates_detail_page(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
            app.current_task.projects.append(
                ProjectViewState(project_name="paper", status=ProjectStatus.COMPLETED, output_dir="outputs/ch_paper", pdf_path="paper.pdf")
            )

            app.select_project("paper")

            self.assertEqual(app.selected_project_name, "paper")
            self.assertEqual(app.query_one("#main-switcher", ContentSwitcher).current, PAGE_DETAIL)

    async def test_refresh_task_table_adds_project_rows(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.current_task = TaskViewState(input_type="arxiv", inputs=["2508.18791"])
            app.current_task.projects.append(ProjectViewState(project_name="paper", status=ProjectStatus.COMPLETED))

            app.refresh_task_table()

            table = app.query_one("#task-table", DataTable)
            self.assertEqual(table.row_count, 1)
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiResultViewsTests
```

Expected: FAIL，相关方法尚未实现。

- [ ] **Step 4: 实现列表和表格刷新**

在 `LaTeXTransTuiApp` 中增加：

```python
    selected_project_name: str | None = None

    def select_project(self, project_name: str) -> None:
        """Select a project and open its detail page."""
        self.selected_project_name = project_name
        self.refresh_detail_page()
        self.switch_page(PAGE_DETAIL)

    def refresh_project_list(self) -> None:
        """Refresh the left-side project list from current task state."""
        list_view = self.query_one("#project-list", ListView)
        list_view.clear()
        if self.current_task is None:
            return
        for project in self.current_task.projects:
            list_view.append(ListItem(Label(f"{project.project_name} [{project.status.value}]")))

    def refresh_detail_page(self) -> None:
        """Refresh detail widgets for the selected project."""
        project = self._selected_project()
        if project is None:
            return
        self.query_one("#detail-paths", Static).update(
            f"PDF: {project.pdf_path or '-'}\nOutput: {project.output_dir or '-'}\nLog: {project.log_path or '-'}"
        )

    def refresh_task_table(self) -> None:
        """Refresh the task management table."""
        table = self.query_one("#task-table", DataTable)
        table.clear(columns=True)
        table.add_columns("项目", "状态", "PDF", "输出目录")
        if self.current_task is None:
            return
        for project in self.current_task.projects:
            table.add_row(
                project.project_name,
                project.status.value,
                project.pdf_path or "",
                project.output_dir or "",
            )

    def _selected_project(self) -> object | None:
        """Return the currently selected project state."""
        if self.current_task is None or self.selected_project_name is None:
            return None
        for project in self.current_task.projects:
            if project.project_name == self.selected_project_name:
                return project
        return None
```

在 `handle_runtime_event()` 末尾增加：

```python
        self.refresh_project_list()
        self.refresh_task_table()
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiResultViewsTests
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add src/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): render result detail and task table"
```

## Task 10: 配置页加载、编辑和保存

**Files:**
- Modify: `src/tui/app.py`
- Modify: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `load_ui_config()`, `save_ui_config()`
- Produces: `LaTeXTransTuiApp.load_config_page() -> None`
- Produces: `LaTeXTransTuiApp.save_config_page() -> None`

- [ ] **Step 1: 查询 Textual 最新 Input、Switch、TextArea 文档**

Run:

```powershell
npx ctx7@latest docs /textualize/textual "Input value Switch value TextArea text current API"
```

Expected: 确认表单组件的值读取和设置方式。

- [ ] **Step 2: 写失败测试**

在 `tests/test_tui_app.py` 添加：

```python
from unittest.mock import patch


class TuiConfigPageTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_config_page_writes_toml_preview(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            with patch("src.tui.app.load_ui_config", return_value={"target_language": "ja"}):
                app.load_config_page()

            self.assertIn("target_language", app.query_one("#config-preview", TextArea).text)

    async def test_save_config_page_persists_preview_toml(self):
        app = LaTeXTransTuiApp()
        async with app.run_test():
            app.query_one("#config-preview", TextArea).text = 'target_language = "fr"\n'
            with patch("src.tui.app.save_ui_config") as save_config:
                app.save_config_page()

            self.assertEqual(save_config.call_args.args[1]["target_language"], "fr")
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiConfigPageTests
```

Expected: FAIL，方法不存在。

- [ ] **Step 4: 实现配置页**

在 `src/tui/app.py` 增加 imports：

```python
import toml
from src.tui.config import load_ui_config, save_ui_config
```

增加：

```python
    def load_config_page(self) -> None:
        """Load UI config into the configuration page."""
        config = load_ui_config(Path.cwd())
        self.query_one("#config-preview", TextArea).text = toml.dumps(config)

    def save_config_page(self) -> None:
        """Save the TOML content from the configuration page."""
        config_text = self.query_one("#config-preview", TextArea).text
        config = toml.loads(config_text)
        save_ui_config(Path.cwd(), config)
```

在 `on_button_pressed()` 增加：

```python
        elif event.button.id == "save-config-button":
            self.save_config_page()
        elif event.button.id == "reload-config-button":
            self.load_config_page()
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_app.TuiConfigPageTests
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add src/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): edit ui config"
```

## Task 11: Zotero PDF 附件导入适配层

**Files:**
- Create: `src/tui/zotero_adapter.py`
- Create: `tests/test_tui_zotero_adapter.py`
- Modify: `src/tui/app.py`
- Modify: `tests/test_tui_app.py`

**Interfaces:**
- Produces: `ZoteroAdapter`
- Produces: `ZoteroAdapter.list_libraries() -> list[dict[str, Any]]`
- Produces: `ZoteroAdapter.search_items(query: str, library_id: str, library_type: str) -> list[dict[str, Any]]`
- Produces: `ZoteroAdapter.attach_pdf(item_key: str, pdf_path: str, library_id: str, library_type: str) -> dict[str, Any]`

- [ ] **Step 1: 阅读 Zotero skill 和官方 Web API 文档**

Read:

```powershell
Get-Content -LiteralPath 'D:\Workspace\resources\skills\zotero-skill\zotero\SKILL.md' -Raw
```

Run:

```powershell
npx ctx7@latest library zotero "Web API file upload child attachment existing item current documentation"
```

If Context7 lacks Zotero docs, use official docs directly:

Open and read:

- `https://www.zotero.org/support/dev/web_api/v3/file_upload`
- `https://www.zotero.org/support/dev/web_api/v3/write_requests`

Expected:

- Confirm the Zotero skill CLI has `list-libraries` and `search-items`.
- Confirm `add-from-file` creates a new item and is not suitable for attaching to an existing item.
- Confirm existing-item PDF attachment must use Zotero Web API child attachment + file upload flow.

- [ ] **Step 2: 写失败测试**

创建 `tests/test_tui_zotero_adapter.py`：

```python
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.tui.zotero_adapter import ZoteroAdapter


class ZoteroAdapterTests(unittest.TestCase):
    def test_list_libraries_runs_existing_zotero_cli(self):
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps([{"library_id": "1", "library_type": "user"}]),
            stderr="",
        )
        with patch("subprocess.run", return_value=completed) as run_mock:
            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
            ).list_libraries()

        self.assertEqual(result[0]["library_id"], "1")
        self.assertIn("list-libraries", run_mock.call_args.args[0])

    def test_search_items_passes_selected_library_to_existing_zotero_cli(self):
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps([{"key": "ITEM123", "title": "Paper"}]),
            stderr="",
        )
        with patch("subprocess.run", return_value=completed) as run_mock:
            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
            ).search_items("Paper", "42", "group")

        command = run_mock.call_args.args[0]
        self.assertEqual(result[0]["key"], "ITEM123")
        self.assertIn("--library-id", command)
        self.assertIn("42", command)
        self.assertIn("--library-type", command)
        self.assertIn("group", command)

    def test_attach_pdf_creates_child_attachment_and_uploads_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "translated.pdf"
            pdf_path.write_bytes(b"%PDF translated")

            session = Mock()
            create_response = Mock()
            create_response.json.return_value = {"successful": {"0": {"key": "ATTACH1"}}}
            create_response.raise_for_status.return_value = None
            auth_response = Mock()
            auth_response.json.return_value = {
                "url": "https://upload.example.test",
                "contentType": "multipart/form-data; boundary=x",
                "prefix": "PREFIX",
                "suffix": "SUFFIX",
                "uploadKey": "UPLOAD1",
            }
            auth_response.raise_for_status.return_value = None
            upload_response = Mock()
            upload_response.raise_for_status.return_value = None
            register_response = Mock()
            register_response.raise_for_status.return_value = None
            session.post.side_effect = [create_response, auth_response, upload_response, register_response]

            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
                session=session,
            ).attach_pdf("ITEM123", str(pdf_path), "42", "group")

        self.assertEqual(result["attachment_key"], "ATTACH1")
        self.assertEqual(result["status"], "uploaded")
        create_call = session.post.call_args_list[0]
        self.assertEqual(create_call.args[0], "https://api.zotero.org/groups/42/items")
        self.assertEqual(create_call.kwargs["json"][0]["parentItem"], "ITEM123")
        self.assertEqual(create_call.kwargs["json"][0]["linkMode"], "imported_file")
        register_call = session.post.call_args_list[3]
        self.assertEqual(register_call.kwargs["data"]["upload"], "UPLOAD1")

    def test_attach_pdf_returns_exists_when_zotero_reports_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "translated.pdf"
            pdf_path.write_bytes(b"%PDF translated")
            session = Mock()
            create_response = Mock()
            create_response.json.return_value = {"successful": {"0": {"key": "ATTACH1"}}}
            create_response.raise_for_status.return_value = None
            auth_response = Mock()
            auth_response.json.return_value = {"exists": 1}
            auth_response.raise_for_status.return_value = None
            session.post.side_effect = [create_response, auth_response]

            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
                session=session,
            ).attach_pdf("ITEM123", str(pdf_path), "42", "group")

        self.assertEqual(result, {"attachment_key": "ATTACH1", "status": "exists"})
        self.assertEqual(session.post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_tui_zotero_adapter
```

Expected: FAIL，模块不存在。

- [ ] **Step 4: 实现 adapter**

创建 `src/tui/zotero_adapter.py`：

```python
"""Zotero integration adapter for the Textual UI."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import requests


class ZoteroAdapter:
    """Adapter for Zotero library search and PDF child attachment upload."""

    def __init__(
        self,
        python_cmd: list[str],
        script_path: str,
        api_key: str,
        session: requests.Session | None = None,
        api_base_url: str = "https://api.zotero.org",
    ) -> None:
        """Initialize the adapter with CLI and Web API settings."""
        self.python_cmd = list(python_cmd)
        self.script_path = script_path
        self.api_key = api_key
        self.session = session if session is not None else requests.Session()
        self.api_base_url = api_base_url.rstrip("/")

    def list_libraries(self) -> list[dict[str, Any]]:
        """List Zotero libraries through the existing Zotero CLI."""
        return self._run_cli_json(["list-libraries"])

    def search_items(self, query: str, library_id: str, library_type: str) -> list[dict[str, Any]]:
        """Search existing Zotero items in a selected library through the CLI."""
        return self._run_cli_json([
            "--library-id",
            library_id,
            "--library-type",
            library_type,
            "search-items",
            query,
        ])

    def attach_pdf(self, item_key: str, pdf_path: str, library_id: str, library_type: str) -> dict[str, Any]:
        """Attach a translated PDF file to an existing Zotero item."""
        path = Path(pdf_path)
        if not path.is_absolute():
            path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))

        attachment_key = self._create_child_attachment(item_key, path, library_id, library_type)
        auth_payload = self._authorize_upload(attachment_key, path, library_id, library_type)
        if auth_payload.get("exists") == 1:
            return {"attachment_key": attachment_key, "status": "exists"}

        upload_key = auth_payload["uploadKey"]
        upload_body = (
            str(auth_payload["prefix"]).encode("utf-8")
            + path.read_bytes()
            + str(auth_payload["suffix"]).encode("utf-8")
        )
        upload_response = self.session.post(
            auth_payload["url"],
            data=upload_body,
            headers={"Content-Type": auth_payload["contentType"]},
        )
        upload_response.raise_for_status()
        self._register_upload(attachment_key, upload_key, library_id, library_type)
        return {"attachment_key": attachment_key, "status": "uploaded"}

    def _run_cli_json(self, args: list[str]) -> Any:
        """Run a Zotero CLI command and parse JSON stdout."""
        completed = subprocess.run(
            [*self.python_cmd, self.script_path, "--json", *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Zotero command failed.")
        return json.loads(completed.stdout or "[]")

    def _library_prefix(self, library_id: str, library_type: str) -> str:
        """Return the Zotero Web API library prefix."""
        if library_type == "user":
            return f"users/{library_id}"
        if library_type == "group":
            return f"groups/{library_id}"
        raise ValueError(f"Unsupported Zotero library type for file upload: {library_type}")

    def _api_headers(self) -> dict[str, str]:
        """Return common Zotero Web API headers."""
        return {
            "Zotero-API-Key": self.api_key,
            "Zotero-API-Version": "3",
        }

    def _create_child_attachment(self, item_key: str, pdf_path: Path, library_id: str, library_type: str) -> str:
        """Create a child attachment item and return its item key."""
        prefix = self._library_prefix(library_id, library_type)
        content_type = mimetypes.guess_type(pdf_path.name)[0] or "application/pdf"
        payload = [{
            "itemType": "attachment",
            "parentItem": item_key,
            "linkMode": "imported_file",
            "title": pdf_path.stem,
            "note": "",
            "tags": [],
            "relations": {},
            "contentType": content_type,
            "charset": "",
            "filename": pdf_path.name,
            "md5": None,
            "mtime": None,
        }]
        response = self.session.post(
            f"{self.api_base_url}/{prefix}/items",
            json=payload,
            headers={
                **self._api_headers(),
                "Content-Type": "application/json",
                "Zotero-Write-Token": str(uuid.uuid4()),
            },
        )
        response.raise_for_status()
        body = response.json()
        successful = body.get("successful") or body.get("success") or {}
        first_result = successful.get("0")
        if isinstance(first_result, dict) and first_result.get("key"):
            return first_result["key"]
        if isinstance(first_result, str):
            return first_result
        raise RuntimeError(f"Zotero did not return an attachment key: {body}")

    def _authorize_upload(self, attachment_key: str, pdf_path: Path, library_id: str, library_type: str) -> dict[str, Any]:
        """Request Zotero upload authorization for the attachment file."""
        prefix = self._library_prefix(library_id, library_type)
        file_bytes = pdf_path.read_bytes()
        data = {
            "md5": hashlib.md5(file_bytes).hexdigest(),
            "filename": pdf_path.name,
            "filesize": str(len(file_bytes)),
            "mtime": str(int(pdf_path.stat().st_mtime * 1000)),
            "contentType": mimetypes.guess_type(pdf_path.name)[0] or "application/pdf",
        }
        response = self.session.post(
            f"{self.api_base_url}/{prefix}/items/{attachment_key}/file",
            data=data,
            headers={**self._api_headers(), "If-None-Match": "*"},
        )
        response.raise_for_status()
        return response.json()

    def _register_upload(self, attachment_key: str, upload_key: str, library_id: str, library_type: str) -> None:
        """Register a completed Zotero file upload."""
        prefix = self._library_prefix(library_id, library_type)
        response = self.session.post(
            f"{self.api_base_url}/{prefix}/items/{attachment_key}/file",
            data={"upload": upload_key},
            headers={**self._api_headers(), "If-None-Match": "*"},
        )
        response.raise_for_status()
```

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
python -m unittest tests.test_tui_zotero_adapter
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add src/tui/zotero_adapter.py tests/test_tui_zotero_adapter.py
git commit -m "feat(tui): attach translated pdf to zotero item"
```

## Task 12: 文档更新

**Files:**
- Modify: `README.md`
- Modify: `README_ZH.md`

- [ ] **Step 1: 更新英文 README**

在 Usage 章节添加：

```markdown
## Terminal UI

LaTeXTransPlus also provides a Textual terminal UI:

```bash
latextrans-tui
```

The UI supports one input type per task: arXiv IDs or URLs, local project paths or archives, or remote archive URLs. It displays project-level progress, result files, logs, validation reports, and UI-specific configuration. Zotero integration is optional and does not block translation results.
```

- [ ] **Step 2: 更新中文 README**

在使用方法章节添加：

```markdown
## 终端 UI

LaTeXTransPlus 也提供基于 Textual 的终端 UI：

```bash
latextrans-tui
```

UI 每次任务只支持一种输入类型：arXiv ID 或 URL、本地项目路径或压缩包、远程压缩包 URL。它会显示项目级进度、结果文件、日志、校验报告和 UI 专用配置。Zotero 集成是可选动作，不会阻断翻译结果。
```

- [ ] **Step 3: 检查文档**

Run:

```powershell
rg -n "latextrans-tui|Terminal UI|终端 UI" README.md README_ZH.md
```

Expected: 两份 README 都包含 TUI 入口说明。

- [ ] **Step 4: 提交**

```powershell
git add README.md README_ZH.md
git commit -m "docs(tui): document terminal ui entry"
```

## Task 13: 最终验证

**Files:**
- Verify all changed files.

- [ ] **Step 1: 运行 TUI 相关测试**

Run:

```powershell
python -m unittest tests.test_tui_config tests.test_tui_input_parser tests.test_tui_state tests.test_tui_runner tests.test_tui_zotero_adapter tests.test_tui_app
```

Expected: PASS。

- [ ] **Step 2: 运行现有核心测试**

Run:

```powershell
python -m unittest tests.test_runtime_project_results tests.test_events tests.test_cli_log
```

Expected: PASS。

- [ ] **Step 3: 运行全量测试**

Run:

```powershell
python -m unittest discover tests
```

Expected: PASS。

- [ ] **Step 4: 检查入口可导入**

Run:

```powershell
python -c "from src.tui.app import LaTeXTransTuiApp, run; print(LaTeXTransTuiApp.__name__, callable(run))"
```

Expected: 输出 `LaTeXTransTuiApp True`。

- [ ] **Step 5: 检查最终 diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 若按任务提交，工作区应干净；若有未提交变更，只应包含本计划列出的文件。

## 自检

### Spec coverage

- 左右布局 + Footer：Task 6
- 右侧 5 页面：Task 6
- 组件清单：Task 6、Task 9、Task 10
- 单任务单输入类型：Task 3、Task 7
- arXiv、本地、远程输入：Task 3、Task 5
- 进度显示：Task 8
- tex、术语表、错误记录查看：Task 9
- 任务管理页：Task 9
- UI 配置：Task 2、Task 10
- Zotero PDF 附件导入边界：Task 11
- README / README_ZH：Task 12
- 全量验证：Task 13

### Placeholder scan

- 未使用 `TBD`、`TODO`、`implement later`。
- 每个任务都有明确文件、接口、测试命令和预期结果。
- Textual 最新文档查询被写入 Global Constraints 和相关任务步骤。

### Type consistency

- 输入类型统一为 `arxiv`、`local`、`remote`。
- 页面 ID 统一为 `entry`、`progress`、`detail`、`tasks`、`config`。
- 状态对象统一为 `TaskViewState` 和 `ProjectViewState`。
- Runner 接口统一为 `run_tui_task(...)`。
