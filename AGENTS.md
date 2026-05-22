# Repository Guidelines

## Project Structure & Module Organization

LaTeXTrans is a Python package for translating LaTeX paper sources and generating translated PDFs. The CLI entry point lives in `main.py`, while reusable package code is under `src/`. Agent orchestration code is in `src/agents/`, LaTeX parsing/compilation helpers are in `src/formats/latex/`, and runtime/config helpers are in `src/runtime.py` and `src/config.py`. Default configuration lives in `config/default.toml`. Terminology CSVs are stored in `terms/`, examples and sample PDFs/images in `examples/`, evaluation scripts in `evaluation/scripts/`, and tests in `tests/`.

## Build, Test, and Development Commands

- `pip install -e .`: install the package in editable mode with console scripts.
- `latextrans --arxiv 2508.18791`: run the translation workflow for an arXiv ID.
- `latextrans --project D:\path\to\paper_source.tar.gz`: process a local LaTeX project or archive.
- `python -m unittest discover tests`: run the current test suite.

Install MiKTeX or TeXLive before testing PDF compilation paths.

## Coding Style & Naming Conventions

Use Python 3.10+ style with 4-space indentation, explicit imports, and `pathlib.Path` for filesystem paths where practical. Keep functions small and name helpers with clear snake_case verbs, such as `_safe_extract_tar` or `load_runtime_config`. Preserve existing public CLI option names and configuration keys. When editing configuration examples, keep TOML keys aligned with `config/default.toml`.

## Testing Guidelines

Tests currently use the standard `unittest` framework. Add tests under `tests/` with filenames like `test_runtime_config.py` and test classes ending in `Tests`. Prefer temporary directories and environment variable isolation for filesystem or configuration behavior. Run `python -m unittest discover tests` before submitting changes.

## Project Lessons

- This project has two configuration loading paths: both `main.py` and `src/runtime.py` load configuration. Changes to configuration semantics must extract shared helpers; otherwise, the CLI entry point and runtime helper can easily drift into inconsistent behavior.
- When removing legacy compatibility, clean it up thoroughly. Do not only update configuration examples or entry-point parameters; also inspect and remove leftover compatibility logic in low-level helpers, alias mappings, fallback branches, and old tests to keep documentation and runtime behavior from drifting again.
- Future development should not assume English-to-Chinese translation by default. Any work involving translation direction, prompts, glossaries, language configuration, or tests should be reviewed for multilingual support. If the user mentions only one case, such as "English-to-Chinese", pause first to note that it may affect multilingual capability and confirm whether the change should target only that language pair.
- New tool agents should log their `execute()` flow through `BaseToolAgent.log`, including start, key processing milestones, failure branches, and successful output paths, so workflow logs remain consistent across agents.
- 远程下载 helper 不能只清理网络异常；文件打开或写入阶段的 `OSError` 也要清理半成品 archive，避免后续 `--all-existing` 或解压流程误处理坏包。
- 批量输入的 skip 语义需要覆盖“部分失败、部分成功继续处理”的回归测试，不能只测单个失败后整体报错。
- 新增显式输入参数时，要同步检查 `--all-existing` 的优先级说明、help 文案和 README，避免文档仍只提旧参数。

## Commit & Pull Request Guidelines

Recent commits use short messages such as `chore: ignore generated files` and `Update README`. Prefer concise, imperative messages; use a scoped conventional prefix when helpful, for example `fix(config): resolve API key from env`. Pull requests should describe the workflow affected, list verification commands, and note configuration changes.

## Security & Configuration Tips

Do not commit API keys. Store secrets in environment variables. Treat `outputs/`, `tex source/`, downloaded archives, and compiled PDFs as generated artifacts unless a fixture is intentionally added for tests or documentation.
