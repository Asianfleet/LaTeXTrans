# Project URL Source Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CLI 新增 `--project-url`，支持公开远程压缩包直链下载并复用现有本地 archive 解压与项目处理链路。

**Architecture:** 在 `main.py` 增加显式参数，并将解析后的 URL 列表传给 `runtime.prepare_projects()`。新增一个小型 `src/project_sources.py` 模块负责远程压缩包 URL 校验、响应判定、文件名推断和下载落地；`runtime` 只负责编排、调用下载 helper，并复用现有 `extract_local_archive()` 把下载结果转成项目目录。

**Tech Stack:** Python 3、`argparse`、`requests`、`pathlib`、`unittest`、`unittest.mock`

---

## 文件结构

- Create: `src/project_sources.py`
  - 远程压缩包 URL 校验、响应头判定、文件名推断、下载落地。
- Create: `tests/test_project_sources.py`
  - `src.project_sources` 的纯单元测试，全部使用 mock，不做真实联网。
- Modify: `main.py`
  - 增加 `--project-url` 参数，解析多值并传给 `runtime.prepare_projects()`。
- Modify: `src/runtime.py`
  - 扩展 `prepare_projects()` 签名与输入分支，处理远程压缩包 URL 并复用现有解压逻辑。
- Modify: `tests/test_runtime_project_results.py`
  - 增加 CLI 接线测试与 `prepare_projects()` 的远程 URL 分支测试。
- Modify: `README.md`
  - 记录 `--project-url` 用法和第一阶段限制。
- Modify: `README_ZH.md`
  - 记录 `--project-url` 用法和第一阶段限制。

### Task 1: CLI 接线 `--project-url`

**Files:**
- Modify: `tests/test_runtime_project_results.py`
- Modify: `main.py`

- [ ] **Step 1: 写一个失败的 CLI 接线测试**

在 `tests/test_runtime_project_results.py` 新增这个测试方法：

```python
    def test_cli_passes_project_url_items_to_prepare_projects(self):
        import main

        runtime_config = {"target_language": "ch", "paper_list": []}
        argv = [
            "latextrans",
            "--config",
            "config/test.toml",
            "--project-url",
            "https://example.test/paper.tar.gz,https://example.test/paper2.zip",
        ]

        with patch.object(main.sys, "argv", argv):
            with patch("src.runtime.load_runtime_config", return_value=runtime_config):
                with patch(
                    "src.runtime.prepare_projects",
                    return_value=(["paper"], runtime_config, "tex-source", "outputs"),
                ) as prepare_projects:
                    with patch(
                        "src.runtime.run_projects",
                        return_value={"completed_projects": [{"project_name": "paper"}], "failed_projects": []},
                    ):
                        with redirect_stdout(StringIO()):
                            main.main()

        prepare_projects.assert_called_once_with(
            config=runtime_config,
            project_items=[],
            project_url_items=[
                "https://example.test/paper.tar.gz",
                "https://example.test/paper2.zip",
            ],
            all_existing=False,
        )
```

- [ ] **Step 2: 运行单测并确认失败**

Run:

```bash
python -m unittest tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_passes_project_url_items_to_prepare_projects
```

Expected: FAIL，`argparse` 报 `unrecognized arguments: --project-url`，或 `prepare_projects()` 调用缺少 `project_url_items`。

- [ ] **Step 3: 在 `main.py` 做最小实现**

修改 `main.py`，加入参数解析、`split_cli_items()` 和新入参透传：

```python
    parser.add_argument(
        "--project-url",
        nargs="+",
        default=[],
        help="Remote project archive URL(s), comma-separated.",
    )

    args = parser.parse_args()
    arxiv_items = runtime.split_cli_items(args.arxiv)
    project_items = runtime.split_cli_items(args.project)
    project_url_items = runtime.split_cli_items(args.project_url)
```

并修改 `prepare_projects()` 调用：

```python
    projects, config, _projects_dir, output_dir = runtime.prepare_projects(
        config=config,
        project_items=project_items,
        project_url_items=project_url_items,
        all_existing=args.all_existing,
    )
```

先不要在这一任务实现 `src/runtime.py` 的内部逻辑，只需要把签名补齐，避免 CLI 测试继续卡在参数传递上：

```python
def prepare_projects(
    config: Dict[str, Any],
    project_items: Optional[Iterable[str]] = None,
    project_url_items: Optional[Iterable[str]] = None,
    all_existing: bool = False,
) -> tuple[List[str], Dict[str, Any], str, str]:
    input_items = config.get("paper_list", [])
```

- [ ] **Step 4: 重新运行单测并确认通过**

Run:

```bash
python -m unittest tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_passes_project_url_items_to_prepare_projects
```

Expected: PASS

- [ ] **Step 5: 提交这一任务**

```bash
git add main.py src/runtime.py tests/test_runtime_project_results.py
git commit -m "test(cli): 覆盖 project-url 参数接线"
```

### Task 2: 远程压缩包下载 helper

**Files:**
- Create: `tests/test_project_sources.py`
- Create: `src/project_sources.py`

- [ ] **Step 1: 先写下载 helper 的失败测试**

创建 `tests/test_project_sources.py`，先放这组测试：

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.project_sources import RemoteArchiveDownloadError, download_remote_archive


class _FakeResponse:
    def __init__(self, headers=None, chunks=None, status_error=None):
        self.headers = headers or {}
        self._chunks = chunks or []
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error

    def iter_content(self, chunk_size=8192):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ProjectSourcesTests(unittest.TestCase):
    def test_download_remote_archive_rejects_non_http_scheme(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(RemoteArchiveDownloadError, "Only http/https URLs are supported"):
                download_remote_archive("ftp://example.test/paper.zip", tmp_dir)

    def test_download_remote_archive_saves_supported_archive(self):
        response = _FakeResponse(
            headers={"Content-Type": "application/zip"},
            chunks=[b"PK", b"DATA"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.project_sources.requests.get", return_value=response):
                archive_path = download_remote_archive("https://example.test/paper.zip", tmp_dir)

            saved = Path(archive_path)
            self.assertTrue(saved.exists())
            self.assertEqual(saved.read_bytes(), b"PKDATA")
            self.assertEqual(saved.suffix, ".zip")

    def test_download_remote_archive_rejects_html_response(self):
        response = _FakeResponse(
            headers={"Content-Type": "text/html; charset=utf-8"},
            chunks=[b"<html></html>"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("src.project_sources.requests.get", return_value=response):
                with self.assertRaisesRegex(RemoteArchiveDownloadError, "HTML pages are not supported"):
                    download_remote_archive("https://example.test/download", tmp_dir)
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
python -m unittest tests.test_project_sources
```

Expected: FAIL，`ModuleNotFoundError: No module named 'src.project_sources'`

- [ ] **Step 3: 写最小实现**

创建 `src/project_sources.py`，先实现这个最小版本：

```python
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

SUPPORTED_ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")


class RemoteArchiveDownloadError(ValueError):
    pass


def _filename_from_content_disposition(value: str) -> str | None:
    match = re.search(r'filename="?([^";]+)"?', value or "")
    if match:
        return Path(match.group(1)).name
    return None


def _guess_archive_name(url: str, headers: dict[str, str]) -> str:
    disposition_name = _filename_from_content_disposition(headers.get("Content-Disposition", ""))
    if disposition_name:
        return disposition_name
    path_name = Path(urlparse(url).path).name
    if path_name:
        return path_name
    return "downloaded-archive.zip"


def _looks_like_supported_archive(url: str, headers: dict[str, str]) -> bool:
    filename = _guess_archive_name(url, headers).lower()
    content_type = headers.get("Content-Type", "").lower()
    if filename.endswith(SUPPORTED_ARCHIVE_SUFFIXES):
        return True
    return any(token in content_type for token in ("zip", "gzip", "x-tar", "tar"))


def download_remote_archive(url: str, projects_dir: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteArchiveDownloadError("Only http/https URLs are supported.")

    target_dir = Path(projects_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            headers = dict(response.headers)
            content_type = headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                raise RemoteArchiveDownloadError("HTML pages are not supported for --project-url.")
            if not _looks_like_supported_archive(url, headers):
                raise RemoteArchiveDownloadError("Response is not a supported archive.")

            filename = Path(_guess_archive_name(url, headers)).name
            destination = target_dir / filename
            if destination.exists():
                stem = destination.stem
                suffix = "".join(destination.suffixes)
                index = 1
                while destination.exists():
                    destination = target_dir / f"{stem}_{index}{suffix}"
                    index += 1

            with destination.open("wb") as handle:
                for chunk in response.iter_content(8192):
                    if chunk:
                        handle.write(chunk)
    except requests.RequestException as exc:
        raise RemoteArchiveDownloadError(f"Failed to download remote archive: {exc}") from exc

    return str(destination)
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```bash
python -m unittest tests.test_project_sources
```

Expected: PASS

- [ ] **Step 5: 提交这一任务**

```bash
git add src/project_sources.py tests/test_project_sources.py
git commit -m "feat(input): 新增远程压缩包下载 helper"
```

### Task 3: 在 `runtime.prepare_projects()` 中接入远程 URL

**Files:**
- Modify: `tests/test_runtime_project_results.py`
- Modify: `src/runtime.py`

- [ ] **Step 1: 先写 `prepare_projects()` 的失败测试**

在 `tests/test_runtime_project_results.py` 追加这两个测试：

```python
    def test_prepare_projects_downloads_remote_archives(self):
        from src.runtime import prepare_projects

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }
            downloaded_archive = source_dir / "paper.tar.gz"
            extracted_project = source_dir / "paper"

            with patch("src.runtime.download_remote_archive", return_value=str(downloaded_archive)) as download_mock:
                with patch("src.runtime.extract_local_archive", return_value=str(extracted_project)) as extract_mock:
                    projects, returned_config, projects_dir, returned_output_dir = prepare_projects(
                        config=config,
                        project_items=[],
                        project_url_items=["https://example.test/paper.tar.gz"],
                        all_existing=False,
                    )

        download_mock.assert_called_once_with("https://example.test/paper.tar.gz", str(source_dir))
        extract_mock.assert_called_once_with(str(downloaded_archive), str(source_dir))
        self.assertEqual(projects, [str(extracted_project.resolve())])
        self.assertEqual(returned_config, config)
        self.assertEqual(projects_dir, str(source_dir.resolve()))
        self.assertEqual(returned_output_dir, str(output_dir.resolve()))

    def test_prepare_projects_skips_failed_remote_archives(self):
        from src.runtime import prepare_projects
        from src.project_sources import RemoteArchiveDownloadError

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = {
                "paper_list": [],
                "tex_sources_dir": str(tmp_path / "tex-source"),
                "output_dir": str(tmp_path / "outputs"),
            }

            with patch(
                "src.runtime.download_remote_archive",
                side_effect=RemoteArchiveDownloadError("Response is not a supported archive."),
            ):
                with self.assertRaisesRegex(ValueError, "No valid TeX projects available for processing."):
                    with redirect_stdout(StringIO()) as stdout:
                        prepare_projects(
                            config=config,
                            project_items=[],
                            project_url_items=["https://example.test/download"],
                            all_existing=False,
                        )

        self.assertIn("[SKIP] Failed to download remote archive https://example.test/download", stdout.getvalue())
```

- [ ] **Step 2: 运行这两个测试并确认失败**

Run:

```bash
python -m unittest \
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_prepare_projects_downloads_remote_archives \
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_prepare_projects_skips_failed_remote_archives
```

Expected: FAIL，因为 `src.runtime` 还没有导入或使用 `download_remote_archive`

- [ ] **Step 3: 在 `src/runtime.py` 接入远程 URL**

先补 import：

```python
from src.project_sources import RemoteArchiveDownloadError, download_remote_archive
```

然后在 `prepare_projects()` 中加入新分支。把函数开头改成：

```python
def prepare_projects(
    config: Dict[str, Any],
    project_items: Optional[Iterable[str]] = None,
    project_url_items: Optional[Iterable[str]] = None,
    all_existing: bool = False,
) -> tuple[List[str], Dict[str, Any], str, str]:
    input_items = config.get("paper_list", [])
    projects_dir = str(resolve_path(config.get("tex_sources_dir", "tex source")))
    output_dir = str(resolve_path(config.get("output_dir", "outputs")))

    os.makedirs(projects_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    paper_list = extract_arxiv_ids(input_items)
    project_items = [item for item in (project_items or []) if item]
    project_url_items = [item for item in (project_url_items or []) if item]
```

更新显式输入判定：

```python
    if paper_list or project_items or project_url_items:
        projects: List[str] = []
```

在本地 `project_items` 分支后面追加远程 URL 分支：

```python
        for project_url in project_url_items:
            try:
                archive_path = download_remote_archive(project_url, projects_dir)
                projects.append(extract_local_archive(archive_path, projects_dir))
            except RemoteArchiveDownloadError as e:
                print(f"[SKIP] Failed to download remote archive {project_url}: {e}")
            except Exception as e:
                print(f"[SKIP] Failed to extract remote archive {project_url}: {e}")
```

最后把无输入错误文案改成包含新参数：

```python
        raise ValueError(
            "No input provided. Use --arxiv, --project, or --project-url. "
            "To process existing projects, pass --all-existing."
        )
```

- [ ] **Step 4: 运行目标测试并确认通过**

Run:

```bash
python -m unittest \
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_cli_passes_project_url_items_to_prepare_projects \
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_prepare_projects_downloads_remote_archives \
  tests.test_runtime_project_results.RuntimeProjectResultTests.test_prepare_projects_skips_failed_remote_archives
```

Expected: PASS

- [ ] **Step 5: 提交这一任务**

```bash
git add src/runtime.py tests/test_runtime_project_results.py
git commit -m "feat(runtime): 接入 project-url 远程压缩包输入"
```

### Task 4: 补一条混合输入回归测试

**Files:**
- Modify: `tests/test_runtime_project_results.py`

- [ ] **Step 1: 增加混合输入测试**

在 `tests/test_runtime_project_results.py` 添加：

```python
    def test_prepare_projects_combines_local_and_remote_inputs(self):
        from src.runtime import prepare_projects

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            local_project = tmp_path / "local-paper"
            local_project.mkdir()
            source_dir = tmp_path / "tex-source"
            output_dir = tmp_path / "outputs"
            extracted_project = source_dir / "remote-paper"
            config = {
                "paper_list": [],
                "tex_sources_dir": str(source_dir),
                "output_dir": str(output_dir),
            }

            with patch("src.runtime.download_remote_archive", return_value=str(source_dir / "remote-paper.zip")):
                with patch("src.runtime.extract_local_archive", return_value=str(extracted_project)):
                    projects, _, _, _ = prepare_projects(
                        config=config,
                        project_items=[str(local_project)],
                        project_url_items=["https://example.test/remote-paper.zip"],
                        all_existing=False,
                    )

        self.assertEqual(
            projects,
            [
                str(local_project.resolve()),
                str(extracted_project.resolve()),
            ],
        )
```

- [ ] **Step 2: 运行测试并确认通过**

Run:

```bash
python -m unittest tests.test_runtime_project_results.RuntimeProjectResultTests.test_prepare_projects_combines_local_and_remote_inputs
```

Expected: PASS

- [ ] **Step 3: 提交这一任务**

```bash
git add tests/test_runtime_project_results.py
git commit -m "test(runtime): 覆盖本地与远程输入混合场景"
```

### Task 5: 更新 README 与中文 README

**Files:**
- Modify: `README.md`
- Modify: `README_ZH.md`

- [ ] **Step 1: 先写文档内容**

在 `README.md` 的 “Translate local projects” 附近补这一节：

````markdown
## Translate from a remote source archive URL

Pass a public remote archive URL directly:

```bash
latextrans --project-url https://example.org/paper_source.tar.gz
```

`--project-url` supports public `http`/`https` archive URLs only. Supported formats are `.zip`, `.tar`, `.tar.gz`, and `.tgz`.

This first-stage implementation does not support HTML download pages, DOI or record pages, repository URLs, or authenticated downloads.
````

在 `README_ZH.md` 的对应位置补这一节：

````markdown
## 通过远程源码压缩包 URL 翻译

可以直接传入公开可访问的远程压缩包 URL：

```bash
latextrans --project-url https://example.org/paper_source.tar.gz
```

`--project-url` 第一阶段仅支持公开 `http`/`https` 压缩包直链。支持的格式包括 `.zip`、`.tar`、`.tar.gz` 和 `.tgz`。

当前阶段不支持 HTML 下载页、DOI 或 record 页面、repo URL，以及需要认证的下载。
````

- [ ] **Step 2: 补一个混合输入示例**

在两个 README 中都增加一行示例，明确它可以与其他显式输入并存：

```markdown
latextrans --arxiv 2508.18791 --project-url https://example.org/paper_source.tar.gz
```

- [ ] **Step 3: 检查文案一致性**

人工检查以下几点：

- `README.md` 与 `README_ZH.md` 对支持范围描述一致
- 两份文档都明确写出了只支持直链压缩包
- 两份文档都明确列出了不支持项

- [ ] **Step 4: 提交这一任务**

```bash
git add README.md README_ZH.md
git commit -m "docs(README): 记录 project-url 输入方式"
```

### Task 6: 最终验证

**Files:**
- Test: `tests/test_project_sources.py`
- Test: `tests/test_runtime_project_results.py`

- [ ] **Step 1: 运行新增测试集合**

Run:

```bash
python -m unittest tests.test_project_sources tests.test_runtime_project_results
```

Expected: PASS

- [ ] **Step 2: 快速检查帮助输出**

Run:

```bash
python main.py --help
```

Expected: 输出中包含 `--project-url`，help 文案为 `Remote project archive URL(s), comma-separated.`

- [ ] **Step 3: 检查最终 diff 只包含任务相关文件**

Run:

```bash
git diff --stat
git status --short
```

Expected: 只包含：

- `main.py`
- `src/runtime.py`
- `src/project_sources.py`
- `tests/test_runtime_project_results.py`
- `tests/test_project_sources.py`
- `README.md`
- `README_ZH.md`

- [ ] **Step 4: 提交最终收尾修正（如果 Step 1-3 产生了必要调整）**

```bash
git add main.py src/runtime.py src/project_sources.py tests/test_runtime_project_results.py tests/test_project_sources.py README.md README_ZH.md
git commit -m "chore: 完成 project-url 远程源码输入验证"
```

## 自检

### Spec coverage

- `--project-url` CLI 参数：Task 1
- 远程压缩包 helper：Task 2
- `prepare_projects()` 集成：Task 3、Task 4
- 错误处理与 skip 语义：Task 2、Task 3
- README / README_ZH 文档更新：Task 5
- 最终验证：Task 6

未发现 spec 要求缺失。

### Placeholder scan

- 未使用 `TODO`、`TBD`、`implement later`
- 每个代码步骤都给出了具体测试或实现片段
- 每个验证步骤都给出了明确命令与预期结果

### Type consistency

- `project_url_items` 在 `main.py`、`prepare_projects()`、测试中保持同名
- `download_remote_archive()` 统一返回本地 archive 路径字符串
- `RemoteArchiveDownloadError` 统一作为远程下载层的显式错误类型
