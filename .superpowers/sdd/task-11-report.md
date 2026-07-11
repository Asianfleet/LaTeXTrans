# Task 11 报告：Zotero PDF 附件导入适配层

## 范围

- 新增 `src/tui/zotero_adapter.py`，提供 `ZoteroAdapter`。
- 新增 `tests/test_tui_zotero_adapter.py`，覆盖 CLI 委托和 Web API PDF 附件上传流程。
- 未修改 `src/tui/app.py` / `tests/test_tui_app.py`，因为 brief 中本任务核心是 adapter，未要求接入 UI 行为。
- 未修改 `.superpowers/sdd/progress.md`。

## Zotero 文档查询证据

- 已读取 Zotero skill：`D:\Workspace\resources\skills\zotero-skill\zotero\SKILL.md`。
- Skill 确认：
  - 现有 CLI 支持 `list-libraries`、`search-items`。
  - `add-from-file` 的语义是创建 item 并附加本地文件，不适合把翻译 PDF 附加到已有 Zotero 条目。
  - Web API 写操作需要 API key；本 adapter 仅接收构造参数 `api_key`，没有读取环境变量。
- 已运行 Context7：
  - `npx ctx7@latest library zotero "Web API file upload child attachment existing item current documentation"`
  - 返回 `/websites/zotero_support`，说明 Context7 可定位 Zotero 官方支持文档。
- 已核对官方文档：
  - `https://www.zotero.org/support/dev/web_api/v3/file_upload`
  - `https://www.zotero.org/support/dev/web_api/v3/write_requests`
- 官方 file upload 文档要点：
  - 新附件流程先创建 child attachment item：`POST /users/<userID>/items`，payload 包含 `parentItem`、`linkMode`、`contentType`、`filename` 等。
  - 上传授权使用：`POST /users/<userID>/items/<itemKey>/file`，新附件使用 `If-None-Match: *`，提交 `md5`、`filename`、`filesize`、`mtime`。
  - 授权成功可能返回 `url/contentType/prefix/suffix/uploadKey`，也可能返回 `{ "exists": 1 }`；后者表示文件已关联，无需继续上传。
  - 完整上传要求拼接 `prefix + file bytes + suffix` 后 POST 到返回的 `url`，`Content-Type` 使用返回的 `contentType`。
  - 注册上传使用：`POST /users/<userID>/items/<itemKey>/file`，表单字段 `upload=<uploadKey>`。
- 官方 write requests 文档要点：
  - `Zotero-Write-Token` 是客户端生成的随机 32 字符标识符，可用于未版本化写请求防止重复处理。

## TDD 证据

### RED 1

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：失败，符合预期。

关键输出：

```text
ModuleNotFoundError: No module named 'src.tui.zotero_adapter'
FAILED (errors=1)
```

### GREEN 1

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：通过。

关键输出：

```text
Ran 4 tests in 0.051s
OK
```

### RED 2

自审时发现官方文档要求 `Zotero-Write-Token` 为 32 字符随机标识符，先补测试断言。

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：失败，符合预期。

关键输出：

```text
AssertionError: 36 != 32
FAILED (failures=1)
```

### GREEN 2

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：通过。

关键输出：

```text
Ran 4 tests in 0.040s
OK
```

## 最终验证

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：

```text
Ran 4 tests in 0.040s
OK
```

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app
```

结果：

```text
Ran 18 tests in 11.904s
OK
```

备注：`tests.test_tui_app` 输出包含 Textual 的慢 message pump 提示，但退出码为 0，测试通过。

## 变更文件

- `src/tui/zotero_adapter.py`
  - 新增 `ZoteroAdapter`。
  - `list_libraries()` 和 `search_items()` 通过现有 Zotero CLI 运行 JSON 命令。
  - `attach_pdf()` 创建 child attachment，授权上传，处理 `{ "exists": 1 }`，上传文件体并注册 `uploadKey`。
  - 支持 `user` 与 `group` library prefix；不支持 `feed` 上传。
- `tests/test_tui_zotero_adapter.py`
  - 覆盖列库 CLI 调用。
  - 覆盖搜索时显式传递 `--library-id` / `--library-type`。
  - 覆盖 child attachment + full upload + register upload 请求顺序。
  - 覆盖 Zotero 返回已存在文件时不继续上传。
  - 覆盖 `Zotero-Write-Token` 为 32 字符且不含连字符。

## 自审

- 未读取 API key 环境变量，也未读取任何 secret 文件。
- 未使用 Zotero skill 的 `add-from-file`。
- 未新建 Zotero 条目；只创建已有 parent item 下的 child attachment。
- 未自动匹配 Zotero 条目；调用者必须传入 `item_key`、`library_id`、`library_type`。
- 所有新增类、函数和测试方法都有 docstring。
- 仅暂存/提交本任务文件；已有 `.gitignore` 外部改动未纳入本任务。

## 顾虑

- 当前 adapter 单元测试使用 mock session，未对真实 Zotero API 做端到端上传验证。
- `attach_pdf()` 目前为同步实现，后续 UI 集成时需要避免阻塞 Textual message loop。
- 当前实现不处理 Zotero 409/412/413/429 的专门用户提示，只通过 `raise_for_status()` 抛出请求异常。

## 复审修复：CLI JSON envelope 解析

### 问题

复审指出现有 Zotero CLI 的 `--json` 成功输出是 envelope：

```json
{"command": "...", "result": ...}
```

而不是裸数组。旧版 `_run_cli_json()` 直接返回 `json.loads(stdout)`，会导致 `list_libraries()` 和 `search_items()` 在真实 CLI 下返回外层 dict，不符合 brief 约定的 `list[dict]`。

### 核对证据

已核对：

```powershell
rg -n "json|command|result|print|dumps" 'D:\Workspace\resources\skills\zotero-skill\zotero\scripts\zotero.py'
```

关键代码位于 `zotero.py`：

```text
_json_dump({"command": result.command, "result": result.data}, sys.stdout)
```

因此真实成功输出确认为 `command/result` envelope。

### 修复

- `_run_cli_json()` 现在会在 stdout 为 dict 且包含 `result` 时返回 `body["result"]`。
- 保留裸数组/裸 JSON 兼容：不含 `result` 的 JSON 仍原样返回。
- CLI mock 已改为真实 envelope 输出。
- 新增测试锁定 `_run_cli_json()` 只返回 envelope 的 `result`。
- 补充断言：
  - 上传授权请求包含 `If-None-Match: *`。
  - 上传授权表单包含 `md5`、`filesize`、`contentType`。
  - 注册上传请求包含 `If-None-Match: *`。

### TDD RED

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：失败，符合预期。

关键输出：

```text
KeyError: 0
AssertionError: {'command': 'list-libraries', 'result': ...} != [{'library_id': '42', 'library_type': 'group'}]
FAILED (failures=1, errors=2)
```

### GREEN 与最终验证

命令：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_zotero_adapter
```

结果：

```text
Ran 5 tests in 0.041s
OK
```

命令：

```powershell
conda run -n latextrans python -m unittest discover tests
```

结果：

```text
Ran 221 tests in 11.273s
OK
```

备注：全量测试输出包含 TerminologyAgent 预期日志和 Textual 慢 message pump 提示，但退出码为 0。
