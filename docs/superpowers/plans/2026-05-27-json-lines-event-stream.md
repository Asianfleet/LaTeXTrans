# JSON Lines Event Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LaTeXTransPlus CLI 增加项目级 JSON Lines 事件流，支持 stdout 与 JSONL 文件输出，并在 stdout JSONL 模式下隔离普通日志。

**Architecture:** 新增 `src/events.py` 作为 JSONL 事件格式化与写出边界；`main.py` 负责 CLI 参数、事件 sink、run 级事件和日志模式切换；`src/runtime.py` 继续通过现有 `event_callback` 发项目级事件，但补齐 `output_dir`、`log_path`、`pdf_path` 和 `error`。默认 CLI 行为保持不变，只有显式传入 JSON 事件参数时才启用机器可读输出。

**Tech Stack:** Python 3.10+、`argparse`、`json`、`datetime`、`pathlib`、`unittest`、`unittest.mock`

---

## 文件结构

- Create: `src/events.py`
  - 定义 `SCHEMA_VERSION`、`build_event()`、`JsonLinesEventSink`，只负责 JSONL 事件格式化与写出。
- Create: `tests/test_events.py`
  - 覆盖事件基础字段、stdout JSONL、file JSONL、stdout 与 file 同时输出。
- Modify: `main.py`
  - 增加 `--json-events stdout` 与 `--json-events-file`。
  - 增加普通日志只写文件的 context。
  - 发送 `run_start` 与 `run_complete`。
  - 将 `runtime.run_projects(event_callback=...)` 接到 JSONL sink。
- Modify: `src/runtime.py`
  - 补齐项目事件 payload。
  - 增加 runtime 内部项目输出目录和日志路径 helper，避免依赖 `main.py`。
- Modify: `tests/test_cli_log.py`
  - 覆盖普通日志只写文件、不污染 stdout/stderr 的 context。
- Modify: `tests/test_runtime_project_results.py`
  - 覆盖 CLI JSON 事件接线、stdout JSONL 纯净性、文件 JSONL、runtime 项目事件字段。
- Modify: `README.md`
  - 增加 JSON Lines event stream 用法与事件示例。
- Modify: `README_ZH.md`
  - 增加中文 JSON Lines event stream 用法与事件示例。

## Task 1: 事件模块

**Files:**
- Create: `tests/test_events.py`
- Create: `src/events.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_events.py`：

```python
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from src.events import SCHEMA_VERSION, JsonLinesEventSink, build_event


class EventBuilderTests(unittest.TestCase):
    def test_build_event_adds_schema_type_and_timestamp(self):
        event = build_event("project_start", project_name="paper")

        self.assertEqual(event["schema_version"], SCHEMA_VERSION)
        self.assertEqual(event["type"], "project_start")
        self.assertEqual(event["project_name"], "paper")
        self.assertIn("T", event["timestamp"])
        self.assertRegex(event["timestamp"], r"(Z|[+-]\d\d:\d\d)$")


class JsonLinesEventSinkTests(unittest.TestCase):
    def test_stdout_sink_writes_one_json_object_per_line(self):
        stdout = StringIO()
        sink = JsonLinesEventSink(stdout=True, stdout_stream=stdout)

        sink.write({"type": "project_start", "project_name": "论文"})
        sink.close()

        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["type"], "project_start")
        self.assertEqual(payload["project_name"], "论文")

    def test_file_sink_writes_utf8_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "nested" / "events.jsonl"
            sink = JsonLinesEventSink(file_path=str(path))
            sink.write({"type": "run_complete", "ok": True})
            sink.close()

            payload = json.loads(path.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["type"], "run_complete")
        self.assertTrue(payload["ok"])

    def test_stdout_and_file_receive_same_event(self):
        stdout = StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "events.jsonl"
            sink = JsonLinesEventSink(stdout=True, file_path=str(path), stdout_stream=stdout)
            event = {"type": "project_complete", "pdf_path": r"D:\paper.pdf"}
            sink.write(event)
            sink.close()

            stdout_payload = json.loads(stdout.getvalue().strip())
            file_payload = json.loads(path.read_text(encoding="utf-8").strip())

        self.assertEqual(stdout_payload, file_payload)
        self.assertEqual(file_payload["pdf_path"], r"D:\paper.pdf")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_events
```

Expected: FAIL，错误为 `ModuleNotFoundError: No module named 'src.events'`。

- [ ] **Step 3: 实现事件模块**

创建 `src/events.py`：

```python
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO


SCHEMA_VERSION = 1


def build_event(event_type: str, **payload: Any) -> dict[str, Any]:
    """构建带 schema version 和时间戳的 JSONL 事件。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "type": event_type,
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        **payload,
    }


class JsonLinesEventSink:
    """将 JSON Lines 事件写入 stdout 和可选文件。"""

    def __init__(
        self,
        stdout: bool = False,
        file_path: str | None = None,
        stdout_stream: TextIO | None = None,
    ) -> None:
        self._stdout_stream = stdout_stream if stdout_stream is not None else sys.stdout
        self._write_stdout = stdout
        self._file: TextIO | None = None
        if file_path:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file = path.open("w", encoding="utf-8", buffering=1)

    def write(self, event: dict[str, Any]) -> None:
        """写入单条 JSON object，并立即 flush。"""
        line = json.dumps(event, ensure_ascii=False) + "\n"
        if self._write_stdout:
            self._stdout_stream.write(line)
            self._stdout_stream.flush()
        if self._file is not None:
            self._file.write(line)
            self._file.flush()

    def close(self) -> None:
        """关闭由 sink 持有的文件句柄。"""
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "JsonLinesEventSink":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False
```

- [ ] **Step 4: 运行事件测试并确认通过**

Run:

```powershell
python -m unittest tests.test_events
```

Expected: PASS。

- [ ] **Step 5: 提交这一任务**

```powershell
git add src/events.py tests/test_events.py
git commit -m "feat(events): 新增 JSON Lines 事件 sink"
```

## Task 2: 普通日志只写文件的 context

**Files:**
- Modify: `tests/test_cli_log.py`
- Modify: `main.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_cli_log.py` 的 import 改成：

```python
from main import _project_log_path, _redirect_console_to_log, _tee_console_to_log
```

追加测试：

```python
    def test_redirect_console_to_log_does_not_write_to_console_streams(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "latextrans.log"

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            try:
                sys.stdout = stdout
                sys.stderr = stderr
                with _redirect_console_to_log(log_path):
                    print("stdout message")
                    print("stderr message", file=sys.stderr)
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("stdout message", log_text)
        self.assertIn("stderr message", log_text)
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_cli_log.CliLogTests.test_redirect_console_to_log_does_not_write_to_console_streams
```

Expected: FAIL，错误为 `ImportError` 或 `AttributeError`，因为 `_redirect_console_to_log` 尚不存在。

- [ ] **Step 3: 在 `main.py` 增加 context**

在 `_tee_console_to_log()` 后新增：

```python
@contextmanager
def _redirect_console_to_log(log_path: Path) -> Iterator[Path]:
    """将 stdout 和 stderr 都重定向到项目日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
        with redirect_stdout(log_file):
            with redirect_stderr(log_file):
                yield log_path
```

- [ ] **Step 4: 运行日志测试并确认通过**

Run:

```powershell
python -m unittest tests.test_cli_log
```

Expected: PASS。

- [ ] **Step 5: 提交这一任务**

```powershell
git add main.py tests/test_cli_log.py
git commit -m "feat(cli): 支持普通日志仅写入文件"
```

## Task 3: runtime 项目事件字段

**Files:**
- Modify: `tests/test_runtime_project_results.py`
- Modify: `src/runtime.py`

- [ ] **Step 1: 写成功项目事件字段测试**

在 `tests/test_runtime_project_results.py` 追加：

```python
    def test_run_projects_event_payload_includes_output_and_log_paths(self):
        events = []

        class FakeCoordinatorAgent:
            def __init__(self, config, project_dir, output_dir):
                pass

            def workflow_latextrans(self):
                return {
                    "ok": True,
                    "pdf_path": r"outputs\ch_paper\ch_paper.pdf",
                    "errors_report_path": r"outputs\ch_paper\errors_report.json",
                    "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
                    "error": None,
                }

        with patch("src.runtime.CoordinatorAgent", FakeCoordinatorAgent):
            with redirect_stdout(StringIO()):
                run_projects(
                    config={"target_language": "ch"},
                    projects=[r"D:\tex source\paper"],
                    output_dir=r"D:\repo\outputs",
                    event_callback=events.append,
                )

        start_event = events[0]
        complete_event = events[1]
        self.assertEqual(start_event["type"], "project_start")
        self.assertEqual(start_event["output_dir"], r"D:\repo\outputs\ch_paper")
        self.assertEqual(start_event["log_path"], r"D:\repo\outputs\ch_paper\latextrans.log")
        self.assertEqual(complete_event["type"], "project_complete")
        self.assertEqual(complete_event["output_dir"], r"D:\repo\outputs\ch_paper")
        self.assertEqual(complete_event["log_path"], r"D:\repo\outputs\ch_paper\latextrans.log")
        self.assertEqual(complete_event["pdf_path"], r"outputs\ch_paper\ch_paper.pdf")
        self.assertIsNone(complete_event["error"])
```

- [ ] **Step 2: 写异常项目事件字段测试**

继续追加：

```python
    def test_run_projects_exception_event_includes_paths_and_null_result_fields(self):
        events = []

        class FailingCoordinatorAgent:
            def __init__(self, config, project_dir, output_dir):
                pass

            def workflow_latextrans(self):
                raise RuntimeError("boom")

        with patch("src.runtime.CoordinatorAgent", FailingCoordinatorAgent):
            with redirect_stdout(StringIO()):
                run_projects(
                    config={"target_language": "ch"},
                    projects=[r"D:\tex source\paper"],
                    output_dir=r"D:\repo\outputs",
                    event_callback=events.append,
                )

        error_event = events[1]
        self.assertEqual(error_event["type"], "project_error")
        self.assertEqual(error_event["output_dir"], r"D:\repo\outputs\ch_paper")
        self.assertEqual(error_event["log_path"], r"D:\repo\outputs\ch_paper\latextrans.log")
        self.assertIsNone(error_event["pdf_path"])
        self.assertIsNone(error_event["errors_report_path"])
        self.assertIsNone(error_event["validation_summary"])
        self.assertEqual(error_event["error"], "boom")
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m unittest `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_run_projects_event_payload_includes_output_and_log_paths `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_run_projects_exception_event_includes_paths_and_null_result_fields
```

Expected: FAIL，因为 runtime 事件还没有 `output_dir` 和 `log_path`。

- [ ] **Step 4: 在 `src/runtime.py` 增加 helper**

在 `ProjectContextCallback` 后新增：

```python
def project_output_dir(output_dir: str, target_language: str, project_dir: str) -> Path:
    """返回单个项目的翻译输出目录。"""
    return Path(output_dir) / f"{target_language}_{Path(project_dir).name}"


def project_log_path(output_dir: str, target_language: str, project_dir: str) -> Path:
    """返回单个项目的 CLI 日志路径。"""
    return project_output_dir(output_dir, target_language, project_dir) / "latextrans.log"
```

- [ ] **Step 5: 补齐 `run_projects()` 事件 payload**

在 `run_projects()` 的 loop 内、`project_name` 后增加：

```python
            target_language = config.get("target_language", "ch")
            project_output_path = str(project_output_dir(output_dir, target_language, project_dir))
            log_path = str(project_log_path(output_dir, target_language, project_dir))
```

把 `project_start` payload 改成：

```python
                    {
                        "type": "project_start",
                        "index": idx,
                        "total": total_projects,
                        "project_name": project_name,
                        "project_dir": project_dir,
                        "output_dir": project_output_path,
                        "log_path": log_path,
                    }
```

把异常分支的 `project_error` payload 改成：

```python
                        {
                            "type": "project_error",
                            "index": idx,
                            "total": total_projects,
                            "project_name": project_name,
                            "project_dir": project_dir,
                            "output_dir": project_output_path,
                            "pdf_path": None,
                            "errors_report_path": None,
                            "validation_summary": None,
                            "error": str(e),
                            "log_path": log_path,
                        }
```

把正常完成后的 `event_payload` 改成：

```python
                event_payload = {
                    "type": event_type,
                    "index": idx,
                    "total": total_projects,
                    "project_name": project_name,
                    "project_dir": project_dir,
                    "output_dir": project_output_path,
                    "pdf_path": project_result.get("pdf_path"),
                    "errors_report_path": project_result.get("errors_report_path"),
                    "validation_summary": project_result.get("validation_summary"),
                    "error": project_result.get("error"),
                    "log_path": log_path,
                }
```

- [ ] **Step 6: 运行 runtime 目标测试**

Run:

```powershell
python -m unittest `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_run_projects_event_payload_includes_output_and_log_paths `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_run_projects_exception_event_includes_paths_and_null_result_fields `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_run_projects_event_payload_preserves_term_review_status
```

Expected: PASS。

- [ ] **Step 7: 提交这一任务**

```powershell
git add src/runtime.py tests/test_runtime_project_results.py
git commit -m "feat(runtime): 补齐项目事件上下文"
```

## Task 4: CLI JSON 事件接线

**Files:**
- Modify: `tests/test_runtime_project_results.py`
- Modify: `main.py`

- [ ] **Step 1: 写 stdout JSONL 测试**

在 `tests/test_runtime_project_results.py` 追加：

```python
    def test_cli_json_events_stdout_contains_only_json_lines(self):
        import json
        import main

        runtime_config = {
            "target_language": "ch",
            "source_language": "en",
            "paper_list": [],
        }
        events_seen = []

        def fake_run_projects(**kwargs):
            kwargs["event_callback"](
                {
                    "type": "project_start",
                    "index": 1,
                    "total": 1,
                    "project_name": "paper",
                    "project_dir": r"D:\paper",
                    "output_dir": r"D:\outputs\ch_paper",
                    "log_path": r"D:\outputs\ch_paper\latextrans.log",
                }
            )
            kwargs["event_callback"](
                {
                    "type": "project_complete",
                    "index": 1,
                    "total": 1,
                    "project_name": "paper",
                    "project_dir": r"D:\paper",
                    "output_dir": r"D:\outputs\ch_paper",
                    "pdf_path": r"D:\outputs\ch_paper\ch_paper.pdf",
                    "errors_report_path": r"D:\outputs\ch_paper\errors_report.json",
                    "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
                    "error": None,
                    "log_path": r"D:\outputs\ch_paper\latextrans.log",
                }
            )
            events_seen.append(kwargs["event_callback"])
            return {"completed_projects": [{"project_name": "paper"}], "failed_projects": []}

        argv = [
            "latextrans",
            "--config",
            "config/test.toml",
            "--project",
            r"D:\paper",
            "--json-events",
            "stdout",
        ]

        with patch.object(main.sys, "argv", argv):
            with patch("src.runtime.load_runtime_config", return_value=runtime_config):
                with patch("src.runtime.prepare_projects", return_value=([r"D:\paper"], runtime_config, "tex-source", r"D:\outputs")):
                    with patch("src.runtime.run_projects", side_effect=fake_run_projects):
                        with redirect_stdout(StringIO()) as stdout:
                            main.main()

        lines = stdout.getvalue().splitlines()
        self.assertEqual([json.loads(line)["type"] for line in lines], [
            "run_start",
            "project_start",
            "project_complete",
            "run_complete",
        ])
        for line in lines:
            payload = json.loads(line)
            self.assertEqual(payload["schema_version"], 1)
            self.assertIn("timestamp", payload)
        self.assertNotIn("Console log will be saved to", stdout.getvalue())
```

- [ ] **Step 2: 写 JSONL 文件测试**

继续追加：

```python
    def test_cli_json_events_file_writes_events(self):
        import json
        import main

        runtime_config = {"target_language": "ch", "source_language": "en", "paper_list": []}

        def fake_run_projects(**kwargs):
            kwargs["event_callback"](
                {
                    "type": "project_error",
                    "index": 1,
                    "total": 1,
                    "project_name": "paper",
                    "project_dir": r"D:\paper",
                    "output_dir": r"D:\outputs\ch_paper",
                    "pdf_path": None,
                    "errors_report_path": None,
                    "validation_summary": None,
                    "error": "boom",
                    "log_path": r"D:\outputs\ch_paper\latextrans.log",
                }
            )
            return {"completed_projects": [], "failed_projects": [{"project_name": "paper"}]}

        with tempfile.TemporaryDirectory() as tmp_dir:
            events_path = Path(tmp_dir) / "events.jsonl"
            argv = [
                "latextrans",
                "--config",
                "config/test.toml",
                "--project",
                r"D:\paper",
                "--json-events-file",
                str(events_path),
            ]

            with patch.object(main.sys, "argv", argv):
                with patch("src.runtime.load_runtime_config", return_value=runtime_config):
                    with patch("src.runtime.prepare_projects", return_value=([r"D:\paper"], runtime_config, "tex-source", r"D:\outputs")):
                        with patch("src.runtime.run_projects", side_effect=fake_run_projects):
                            with self.assertRaises(SystemExit):
                                with redirect_stdout(StringIO()):
                                    main.main()

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual([event["type"] for event in events], ["run_start", "project_error", "run_complete"])
        self.assertFalse(events[-1]["ok"])
        self.assertEqual(events[-1]["failed"], 1)
```

- [ ] **Step 3: 运行 CLI JSON 测试并确认失败**

Run:

```powershell
python -m unittest `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_json_events_stdout_contains_only_json_lines `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_json_events_file_writes_events
```

Expected: FAIL，`argparse` 不认识 `--json-events` 或 `--json-events-file`。

- [ ] **Step 4: 在 `main.py` 增加 imports 和参数**

新增 import：

```python
from src.events import JsonLinesEventSink, build_event
```

在 parser 中增加：

```python
    parser.add_argument(
        "--json-events",
        choices=["stdout"],
        default="",
        help="Emit JSON Lines events to the selected destination.",
    )
    parser.add_argument(
        "--json-events-file",
        type=str,
        default="",
        help="Write JSON Lines events to this file.",
    )
```

- [ ] **Step 5: 接入 sink、run 事件和日志模式**

在 `target_language = ...` 后增加：

```python
    source_language = config.get("source_language", "en")
    emit_json_stdout = args.json_events == "stdout"
    event_sink = JsonLinesEventSink(
        stdout=emit_json_stdout,
        file_path=args.json_events_file or None,
    )
```

替换 `project_log_context()`：

```python
    @contextmanager
    def project_log_context(idx: int, total: int, project_dir: str) -> Iterator[None]:
        log_path = _project_log_path(output_dir, target_language, project_dir)
        if emit_json_stdout:
            with _redirect_console_to_log(log_path):
                print(f"Console log will be saved to: {log_path}")
                yield
        else:
            with _tee_console_to_log(log_path):
                print(f"Console log will be saved to: {log_path}")
                yield
```

把 `runtime.run_projects()` 调用和退出判断包成：

```python
    try:
        event_sink.write(
            build_event(
                "run_start",
                total=len(projects),
                config_path=args.config,
                output_dir=output_dir,
                source_language=source_language,
                target_language=target_language,
            )
        )
        project_status = runtime.run_projects(
            config=config,
            projects=projects,
            output_dir=output_dir,
            event_callback=lambda event: event_sink.write(build_event(event["type"], **{k: v for k, v in event.items() if k != "type"})),
            project_context=project_log_context,
        )
        event_sink.write(
            build_event(
                "run_complete",
                ok=not should_exit_with_failure(project_status),
                total=len(projects),
                completed=len(project_status["completed_projects"]),
                failed=len(project_status["failed_projects"]),
            )
        )
    finally:
        event_sink.close()

    if should_exit_with_failure(project_status):
        sys.exit(1)
```

- [ ] **Step 6: 运行 CLI JSON 测试并确认通过**

Run:

```powershell
python -m unittest `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_json_events_stdout_contains_only_json_lines `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_json_events_file_writes_events
```

Expected: PASS。

- [ ] **Step 7: 运行既有 CLI 接线测试**

Run:

```powershell
python -m unittest `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_uses_runtime_prepare_and_run_projects `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_passes_project_url_items_to_prepare_projects `
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_passes_runtime_config_overrides
```

Expected: PASS。

- [ ] **Step 8: 提交这一任务**

```powershell
git add main.py tests/test_runtime_project_results.py
git commit -m "feat(cli): 输出 JSON Lines 项目事件"
```

## Task 5: README 文档

**Files:**
- Modify: `README.md`
- Modify: `README_ZH.md`

- [ ] **Step 1: 更新英文 README**

在 `README.md` 的 Usage 章节加入：

````markdown
## Emit JSON Lines Events

For integrations such as Zotero plugins, LaTeXTransPlus can emit stable project-level JSON Lines events:

```bash
latextrans --arxiv 2508.18791 --json-events stdout
latextrans --arxiv 2508.18791 --json-events-file outputs/events.jsonl
latextrans --arxiv 2508.18791 --json-events stdout --json-events-file outputs/events.jsonl
```

When `--json-events stdout` is enabled, stdout contains only JSON objects, one per line. Human-readable workflow logs are still written to each project's `latextrans.log`.

The first schema version emits these event types:

- `run_start`
- `project_start`
- `project_complete`
- `project_error`
- `run_complete`

Each event includes `schema_version`, `type`, and `timestamp`. Project events also include `project_name`, `project_dir`, `output_dir`, and `log_path`; completion and error events include `pdf_path`, `errors_report_path`, `validation_summary`, and `error`.
````

- [ ] **Step 2: 更新中文 README**

在 `README_ZH.md` 的使用方法章节加入：

````markdown
## 输出 JSON Lines 事件

面向 Zotero 插件等集成场景，LaTeXTransPlus 可以输出稳定的项目级 JSON Lines 事件：

```bash
latextrans --arxiv 2508.18791 --json-events stdout
latextrans --arxiv 2508.18791 --json-events-file outputs/events.jsonl
latextrans --arxiv 2508.18791 --json-events stdout --json-events-file outputs/events.jsonl
```

启用 `--json-events stdout` 后，stdout 只包含 JSON object，每行一条。普通 workflow 日志仍会写入每个项目目录下的 `latextrans.log`。

第一版 schema 输出这些事件类型：

- `run_start`
- `project_start`
- `project_complete`
- `project_error`
- `run_complete`

每条事件都包含 `schema_version`、`type` 和 `timestamp`。项目事件还包含 `project_name`、`project_dir`、`output_dir` 和 `log_path`；完成与失败事件还包含 `pdf_path`、`errors_report_path`、`validation_summary` 和 `error`。
````

- [ ] **Step 3: 检查文档中参数名一致**

Run:

```powershell
rg -n -- "--json-events|--json-events-file|JSON Lines" README.md README_ZH.md
```

Expected: 两份 README 都包含 `--json-events`、`--json-events-file` 和 JSON Lines 说明。

- [ ] **Step 4: 提交这一任务**

```powershell
git add README.md README_ZH.md
git commit -m "docs(cli): 记录 JSON Lines 事件流用法"
```

## Task 6: 最终验证

**Files:**
- Verify all modified files.

- [ ] **Step 1: 运行事件与 CLI 目标测试**

Run:

```powershell
python -m unittest tests.test_events tests.test_cli_log tests.test_runtime_project_results
```

Expected: PASS。

- [ ] **Step 2: 运行全量测试**

Run:

```powershell
python -m unittest discover tests
```

Expected: PASS。

- [ ] **Step 3: 检查 CLI help**

Run:

```powershell
python main.py --help
```

Expected: help 输出包含：

```text
--json-events {stdout}
--json-events-file JSON_EVENTS_FILE
```

- [ ] **Step 4: 检查最终 diff 范围**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 若采用逐任务提交，`git status --short` 应为空；若提交被延后，只应出现这些文件：

- `main.py`
- `src/events.py`
- `src/runtime.py`
- `tests/test_events.py`
- `tests/test_cli_log.py`
- `tests/test_runtime_project_results.py`
- `README.md`
- `README_ZH.md`

- [ ] **Step 5: 如有未提交的任务相关收尾变更则提交**

```powershell
git add main.py src/events.py src/runtime.py tests/test_events.py tests/test_cli_log.py tests/test_runtime_project_results.py README.md README_ZH.md
git commit -m "chore(cli): 完成 JSON Lines 事件流验证"
```

Expected: commit succeeds，随后 `git status --short` 为空。

## 自检

### Spec coverage

- `--json-events stdout`：Task 4、Task 6
- `--json-events-file <path>`：Task 1、Task 4、Task 6
- stdout JSONL 模式隔离普通日志：Task 2、Task 4
- `schema_version = 1` 与 timestamp：Task 1、Task 4
- `run_start` 与 `run_complete`：Task 4
- `project_start`、`project_complete`、`project_error`：Task 3、Task 4
- `output_dir`、`log_path`、`pdf_path`、`error` 等项目字段：Task 3
- README / README_ZH 文档：Task 5
- 全量验证：Task 6

### Placeholder scan

- 未使用 `TBD`、`TODO`、`implement later`。
- 每个代码修改步骤都包含具体代码片段。
- 每个测试步骤都包含明确命令和预期结果。

### Type consistency

- 事件 sink 名称统一为 `JsonLinesEventSink`。
- 事件构造函数统一为 `build_event(event_type, **payload)`。
- runtime helper 名称统一为 `project_output_dir()` 和 `project_log_path()`。
- CLI 参数统一为 `--json-events` 与 `--json-events-file`。
