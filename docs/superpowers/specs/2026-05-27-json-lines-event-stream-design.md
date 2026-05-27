# JSON Lines 事件流设计

## 背景

Zotero 插件集成设计中已经明确：插件第一版会调用 LaTeXTransPlus CLI，但不会解析普通 stdout 作为精确进度。普通日志面向人类阅读，格式不稳定，也可能包含进度条、emoji、第三方工具输出和错误信息。

当前 LaTeXTransPlus 已经具备一个适合扩展的内部边界：

- `runtime.run_projects()` 接受 `event_callback`。
- 现有事件已经包含 `project_start`、项目成功和项目失败的基础信息。
- CLI 会为每个项目生成 `latextrans.log`，便于保留完整人类日志。

因此本次目标不是重写 workflow，而是在 CLI 层提供稳定、机器可读、不会与普通日志混流的 JSON Lines 事件流。

## 目标

- 新增 CLI 参数，让调用方可以获得 JSON Lines 事件流。
- 支持把事件输出到 stdout。
- 支持同时把事件写入指定 JSONL 文件。
- 启用 stdout 事件流时，stdout 每一行都必须是合法 JSON object。
- 保留现有 `latextrans.log` 作为普通日志落点。
- 第一版只提供项目级事件，满足 Zotero 插件定位结果 PDF、展示批量状态和诊断失败原因。
- 每条事件携带稳定的 `schema_version`，便于插件按版本解析。

## 非目标

本次不实现以下能力：

- 解析普通 stdout 作为进度。
- 百分比进度。
- `parse`、`translate`、`validate`、`generate_pdf` 等阶段级事件。
- 常驻服务、HTTP API 或 IPC 服务。
- 取消运行中的任务。
- 在事件流中输出完整 config、prompt、LLM payload 或 API key。
- 对启动阶段所有异常承诺 `run_error` 事件。

## 推荐方案

采用“项目级 JSON Lines 事件流”方案。

CLI 新增两个参数：

```text
--json-events stdout
--json-events-file <path>
```

行为：

- 未传任何 JSON 事件参数时，保持现有 CLI 行为。
- 传入 `--json-events stdout` 时，stdout 只输出 JSON Lines。
- 传入 `--json-events-file <path>` 时，每条事件写入该 UTF-8 JSONL 文件。
- 两个参数可以同时使用。
- 每条事件写出后立即 flush，方便 Zotero 插件实时读取。

第一版事件类型只承诺：

```text
run_start
project_start
project_complete
project_error
run_complete
```

这个方案先解决插件最需要的稳定集成问题：知道任务开始、每个项目开始、每个项目成功或失败、最终汇总和生成 PDF 路径。后续如果需要更细进度，可以在同一 schema 下新增 `stage_*` 事件。

## 备选方案与取舍

### 方案 A：项目级 JSON Lines 事件流

这是本次推荐方案。

优点：

- 改动集中在 CLI 和 runtime 边界。
- 复用现有 `event_callback`。
- 不需要深入改动 `CoordinatorAgent` 内部 workflow。
- 输出稳定，适合 Zotero 插件第一版消费。
- 不会制造不准确的百分比进度。

缺点：

- UI 只能展示项目级状态。
- 长时间翻译期间无法知道内部阶段。

### 方案 B：项目级事件加最终 JSON result 文件

在方案 A 基础上新增 `--json-result <path>`，写最终汇总结果。

优点：

- 调用方可以在进程结束后读取单个结果文件。
- 对不想 tail JSONL 的消费者更友好。

缺点：

- 与 `--json-events-file` 存在功能重叠。
- 第一版 Zotero 插件只要能读取事件流和最后的 `run_complete`，即可获得同样信息。

本次不采用，避免扩大接口面。

### 方案 C：阶段级事件骨架

在项目级事件基础上，修改 `CoordinatorAgent`，在 parse、terminology、translate、validate、generate_pdf 前后发事件。

优点：

- Zotero 插件可以展示更细阶段。
- 后续进度 UI 更自然。

缺点：

- 需要触碰更深 workflow。
- 翻译阶段内部耗时主要来自 LLM 调用，第一版仍无法准确表达进度。
- 更容易把尚未稳定的内部实现暴露成外部接口。

本次不采用，后续按插件反馈再扩展。

## CLI 设计

### `--json-events`

第一版只接受一个值：

```text
stdout
```

示例：

```bash
latextrans --arxiv 2508.18791 --json-events stdout
```

启用后：

- stdout 只输出 JSON Lines。
- 普通 console 日志不再写到 stdout。
- 普通日志仍写入每个项目目录下的 `latextrans.log`。

### `--json-events-file`

指定 JSONL 文件路径：

```bash
latextrans --arxiv 2508.18791 --json-events-file outputs/events.jsonl
```

行为：

- 使用 UTF-8 写入。
- 父目录不存在时自动创建。
- 文件无法创建或写入时，CLI 直接失败。
- 每条事件写入一行 JSON object，并 flush。

### 同时输出到 stdout 和文件

示例：

```bash
latextrans --arxiv 2508.18791 --json-events stdout --json-events-file outputs/events.jsonl
```

两处输出的事件内容应保持一致。

## 事件 Schema

### 通用字段

每条事件都包含：

```json
{
  "schema_version": 1,
  "type": "project_start",
  "timestamp": "2026-05-27T12:34:56.789+08:00"
}
```

字段说明：

- `schema_version`：整数，第一版固定为 `1`。
- `type`：事件类型。
- `timestamp`：ISO 8601 时间戳，包含本地时区信息。

路径字段统一使用当前平台的普通路径字符串，不强行转换为 URI。

### `run_start`

在项目准备完成、即将开始执行项目队列前发出。

示例：

```json
{
  "schema_version": 1,
  "type": "run_start",
  "timestamp": "2026-05-27T12:34:56.789+08:00",
  "total": 2,
  "config_path": "config/default.toml",
  "output_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs",
  "source_language": "en",
  "target_language": "ch"
}
```

### `project_start`

在单个项目开始处理时发出。

示例：

```json
{
  "schema_version": 1,
  "type": "project_start",
  "timestamp": "2026-05-27T12:34:57.123+08:00",
  "index": 1,
  "total": 2,
  "project_name": "2508.18791",
  "project_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\tex source\\2508.18791",
  "output_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_2508.18791",
  "log_path": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_2508.18791\\latextrans.log"
}
```

### `project_complete`

单个项目成功完成时发出。

示例：

```json
{
  "schema_version": 1,
  "type": "project_complete",
  "timestamp": "2026-05-27T12:40:00.000+08:00",
  "index": 1,
  "total": 2,
  "project_name": "2508.18791",
  "project_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\tex source\\2508.18791",
  "output_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_2508.18791",
  "pdf_path": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_2508.18791\\ch_2508.18791.pdf",
  "errors_report_path": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_2508.18791\\errors_report.json",
  "validation_summary": {"warnings": 0, "errors": 0, "total": 0},
  "error": null,
  "log_path": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_2508.18791\\latextrans.log"
}
```

### `project_error`

单个项目失败或需要用户干预时发出。

示例：

```json
{
  "schema_version": 1,
  "type": "project_error",
  "timestamp": "2026-05-27T12:41:00.000+08:00",
  "index": 2,
  "total": 2,
  "project_name": "paper",
  "project_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\tex source\\paper",
  "output_dir": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_paper",
  "pdf_path": null,
  "errors_report_path": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_paper\\errors_report.json",
  "validation_summary": {"warnings": 0, "errors": 1, "total": 1},
  "error": "PDF generation returned no output path",
  "status": "unsupported_source",
  "log_path": "D:\\Workspace\\tools\\LaTeXTransPlus\\outputs\\ch_paper\\latextrans.log"
}
```

规则：

- `pdf_path` 没有时写 `null`，不要省略。
- `error` 没有时写 `null`。
- `status` 只在 workflow 结果提供时出现，例如 `needs_term_review`、`unsupported_source`。
- `project_terms_path` 与 `project_terms_decisions_path` 在 `needs_term_review` 场景下透传。

### `run_complete`

项目队列执行结束后发出。

示例：

```json
{
  "schema_version": 1,
  "type": "run_complete",
  "timestamp": "2026-05-27T12:42:00.000+08:00",
  "ok": false,
  "total": 2,
  "completed": 1,
  "failed": 1
}
```

如果存在失败项目，`ok` 为 `false`，CLI 仍按现有规则返回非 0 exit code。

## 架构设计

### `src/events.py`

新增小模块，职责只限于事件格式化与写出。

建议接口：

```python
class JsonLinesEventSink:
    """将事件写入 stdout 和 JSONL 文件。"""

    def __init__(self, stdout: bool = False, file_path: str | None = None):
        ...

    def write(self, event: dict[str, object]) -> None:
        ...

    def close(self) -> None:
        ...
```

模块还可以提供：

```python
def build_event(event_type: str, **payload: object) -> dict[str, object]:
    """补齐 schema_version、type 和 timestamp。"""
```

实现要求：

- 使用 `json.dumps(..., ensure_ascii=False)`。
- 每条事件以 `\n` 结尾。
- 每次写出后 flush。
- 文件句柄由 sink 管理，结束时关闭。
- 不吞掉写文件错误。

### `main.py`

负责：

- 解析 `--json-events` 和 `--json-events-file`。
- 初始化 `JsonLinesEventSink`。
- 在 `run_projects()` 前发 `run_start`。
- 在 `run_projects()` 后发 `run_complete`。
- 将 sink 的 `write` 接到 `runtime.run_projects(event_callback=...)`。
- 根据是否启用 stdout JSONL，选择不同日志上下文。

日志上下文需要支持两种模式：

- 默认模式：普通日志 tee 到 console stdout/stderr 和 `latextrans.log`。
- stdout JSONL 模式：普通日志只写入 `latextrans.log`，不写入 stdout，避免破坏 JSONL。

### `src/runtime.py`

保留现有 `event_callback` 设计，不引入 CLI 专属逻辑。

需要补齐项目事件 payload：

- `output_dir`：单项目输出目录。
- `log_path`：项目日志路径。
- `pdf_path`：失败时也显式给出 `None`。
- `error`：成功时显式给出 `None`。

`runtime.run_projects()` 不直接关心 stdout、stderr 或 JSONL 文件，只负责发结构化事件。

## 数据流

1. 用户调用 CLI，并传入 `--json-events stdout` 或 `--json-events-file`。
2. `main.py` 完成参数解析和配置加载。
3. `prepare_projects()` 将输入规整为本地项目目录列表。
4. `main.py` 创建 `JsonLinesEventSink`。
5. `main.py` 发 `run_start`。
6. `runtime.run_projects()` 串行处理项目。
7. 每个项目开始时发 `project_start`。
8. 每个项目成功时发 `project_complete`。
9. 每个项目失败时发 `project_error`。
10. 队列结束后，`main.py` 发 `run_complete`。
11. 如果存在失败项目，CLI 按现有规则以非 0 退出。

## 错误处理

### JSONL 输出错误

如果用户显式要求 `--json-events-file`，但文件无法创建或写入，CLI 应直接失败。调用方依赖这个输出时，静默降级会造成更难诊断的问题。

### 项目执行失败

单个项目失败时：

- 发 `project_error`。
- 记录 `error`、`validation_summary`、`errors_report_path`、`log_path`。
- 批量场景继续处理后续项目。

### 启动阶段失败

第一版不承诺稳定的 `run_error` 事件。原因是配置加载、输入准备、路径解析等失败可能发生在项目队列形成之前。调用方应同时使用：

- 进程退出码。
- stderr 或异常信息。
- 已写出的 JSONL 事件。

后续如果插件需要，也可以新增 `run_error`，但不在第一版 schema 承诺中。

## 测试设计

测试继续使用 `unittest`。

### 事件 sink 测试

覆盖：

- `build_event()` 会加入 `schema_version`、`type`、`timestamp`。
- stdout destination 每行是合法 JSON。
- file destination 写入 UTF-8 JSONL。
- 同时写 stdout 和文件时内容一致。

### CLI 测试

覆盖：

- `--json-events stdout` 会创建 stdout event sink。
- `--json-events-file <path>` 会写文件。
- stdout JSONL 模式下，stdout 不包含普通日志。
- 未传 JSON 事件参数时，现有日志行为不变。

### runtime 测试

覆盖：

- 成功项目发 `project_start` 与 `project_complete`。
- 失败项目发 `project_error`。
- `project_complete` 和 `project_error` 都包含 `output_dir`、`log_path`、`pdf_path`、`error`。
- `needs_term_review` 场景继续透传 `status`、`project_terms_path`、`project_terms_decisions_path`。

### 回归测试

保留并运行现有测试：

```bash
python -m unittest discover tests
```

## 文档更新

需要更新：

- `README.md`
- `README_ZH.md`

新增内容：

- CLI 参数说明。
- stdout JSONL 模式会让普通日志只写入 `latextrans.log`。
- 事件类型和最小示例。
- 插件或脚本消费 JSONL 的推荐方式。

## 兼容性

- 默认行为不变。
- Python API 的 `runtime.run_projects(event_callback=...)` 保留。
- 事件 schema 第一版固定 `schema_version = 1`。
- 后续扩展只新增字段或新增事件类型，不改变现有字段含义。

## 决策总结

本次选择实现项目级 JSON Lines 事件流：

- 用 `--json-events stdout` 提供实时 stdout JSONL。
- 用 `--json-events-file <path>` 提供文件 JSONL。
- stdout JSONL 模式下，普通日志只写入项目 `latextrans.log`。
- 第一版只承诺项目级事件，不做阶段进度和百分比。
- 每条事件带 `schema_version = 1`。

这个方案能以较小改动满足 Zotero 插件对稳定机器可读输出的需求，同时为后续阶段级事件保留扩展空间。
