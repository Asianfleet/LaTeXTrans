# `--project-url` 远程源码压缩包获取设计

## 背景

当前项目支持三类 TeX 源码入口：

- `--arxiv`：从 arXiv 下载源码。
- `--project`：处理本地已解压项目目录或本地压缩包。
- `--all-existing`：处理 `tex_sources_dir` 下已有项目。

现有实现的关键优势是：后续 workflow 只关心“本地项目目录”，不关心源码最初来自哪里。`runtime.prepare_projects()` 负责把不同输入统一整理成项目目录，再交给 `CoordinatorAgent` 执行后续解析、翻译、校验与编译。

用户希望补充新的联网获取渠道，但第一阶段范围已经明确收敛为：

- 只新增一个显式参数 `--project-url`
- 只支持公开可访问的远程压缩包直链
- 不支持 repo URL
- 不支持下载页、DOI、record 页面解析
- 不支持认证、cookie、token

这意味着第一阶段不做“自动发现论文源码”，而是做“当用户已经拿到远程源码压缩包直链时，工具能直接接入现有 workflow”。

## 目标

引入 `--project-url`，允许用户通过公开远程压缩包直链把 LaTeX 源码下载到本地，再复用现有本地 archive 解压与项目处理链路。

具体目标：

- CLI 新增显式输入参数 `--project-url`
- 支持一个或多个远程压缩包 URL
- 下载完成后自动接入现有 `extract_local_archive()` 流程
- 对无效 URL、非压缩包响应、下载失败、解压失败、非有效 TeX 项目给出清晰错误
- 保持批量处理语义：单个输入失败不阻断其他输入

## 非目标

本次不支持以下能力：

- repo URL，例如 GitHub 或 GitLab 仓库地址
- HTML 下载页解析
- DOI、Zenodo、Figshare、OSF、OpenReview 等 record 页面解析
- 需要登录态、cookie、token 或自定义 header 的下载
- 自动发现论文源码压缩包链接
- 为远程来源新增独立 workflow

本次也不调整 parser、translator、validator、generator 的核心行为。

## CLI 设计

### 新增参数

在 `main.py` 中新增：

```python
parser.add_argument(
    "--project-url",
    nargs="+",
    default=[],
    help="Remote project archive URL(s), comma-separated.",
)
```

### 输入形式

`--project-url` 的多值行为与现有 `--arxiv`、`--project` 保持一致：

- 支持 shell 分隔多个参数
- 支持单个参数内部使用逗号分隔多个 URL

示例：

```bash
latextrans --project-url https://example.org/paper.tar.gz
latextrans --project-url https://a/p1.zip,https://b/p2.tgz
latextrans --project-url https://a/p1.zip https://b/p2.tgz
```

### 与其他输入参数的关系

保留当前“显式输入优先”的语义：

- 只要提供了 `--arxiv`、`--project`、`--project-url` 中任意一种，就只处理这些显式输入
- 只有在完全没有显式输入时，`--all-existing` 才生效

不同输入来源允许混用。例如：

```bash
latextrans --arxiv 2508.18791 --project D:\paper_dir --project-url https://example.org/paper.tar.gz
```

工具应将三类显式输入合并后统一处理。

## 架构设计

### 总体思路

第一阶段不改变现有 workflow 主干，只在“输入收集层”新增远程压缩包下载能力。

推荐结构：

- `main.py`
  - 解析 `--project-url`
  - 调用现有 `runtime.split_cli_items()`
  - 将 `project_url_items` 传给 `runtime.prepare_projects()`
- `src/runtime.py`
  - 继续担任输入编排层
  - 负责汇总 arXiv、本地项目、本地压缩包、远程压缩包 URL
- 新增小型输入模块，例如 `src/project_sources.py`
  - 负责远程压缩包 URL 的校验、下载、落地
  - 返回本地 archive 路径

### 为什么不把下载逻辑直接堆进 `runtime.py`

`runtime.py` 现在已经承担了：

- 配置加载
- 路径归一化
- 本地 archive 解压
- 项目列表准备
- batch project 执行编排

如果把远程 URL 校验、HTTP 下载、响应判定、文件命名策略继续直接塞进 `runtime.py`，第一阶段虽然能工作，但后续一旦扩展下载页解析或更多 provider，文件职责会继续发散。

因此本次建议只抽一个很小的“远程输入 helper 模块”，边界保持单一：

- 输入：远程压缩包 URL、目标目录
- 输出：本地 archive 文件路径，或明确异常

### 数据流

完整流程如下：

1. CLI 接收 `--project-url`
2. `split_cli_items()` 将参数展开为 URL 列表
3. `prepare_projects()` 遍历这些 URL
4. 对每个 URL：
   - 调用远程下载 helper
   - helper 下载到 `tex_sources_dir` 下的本地 archive 文件
   - helper 返回本地 archive 路径
5. `prepare_projects()` 调用现有 `extract_local_archive()`
6. 解压得到项目目录后，加入 `projects`
7. 后续 workflow 与本地 archive 输入完全一致

这个设计保证远程来源在进入 coordinator 之前就被规整为本地目录，避免把来源差异扩散到业务链路。

## URL 校验与下载策略

第一阶段采取保守策略，不猜测、不兜底解析 HTML 页面。

### 允许的 URL

- 协议仅支持 `http` 与 `https`
- 目标应为公开可访问资源

### 允许的压缩格式

- `.zip`
- `.tar`
- `.tar.gz`
- `.tgz`

### 校验顺序

建议按以下顺序校验：

1. 校验 URL scheme 是否为 `http` 或 `https`
2. 初步检查 URL path 后缀是否匹配支持格式
3. 发起下载请求并跟随有限次重定向
4. 根据响应头确认是否为压缩包：
   - `Content-Type`
   - `Content-Disposition` 中的文件名
5. 若响应为 HTML 页面，则直接判定为不支持的输入

第一阶段不做以下行为：

- 不从 HTML 中提取下载链接
- 不解析 DOI 跳转结果
- 不根据页面文案猜测附件

## 本地落地与命名

远程下载的压缩包应先保存到 `tex_sources_dir` 下，再复用现有本地 archive 解压逻辑。

文件命名优先级建议如下：

1. `Content-Disposition` 中的文件名
2. URL path basename
3. 基于 URL 生成稳定兜底名

命名要求：

- 保留压缩格式扩展名
- 同名时避免覆盖已有文件
- 命名规则应可预测，方便排查失败输入

不要求第一阶段为远程下载文件建立额外元数据索引。只要命名稳定且不覆盖已有文件即可。

## 错误处理

### 错误分类

对用户可见的错误至少区分以下几类：

- 非法 URL，例如 scheme 不是 `http` 或 `https`
- URL 响应不是受支持的压缩包
- URL 响应为 HTML 页面
- 下载失败，例如网络错误、4xx、5xx、超时
- 下载成功但解压失败
- 解压成功但未形成可处理的 TeX 项目

### 批量处理语义

保持与当前项目一致的风格：

- 单个输入失败时打印明确 `[SKIP] ...` 原因
- 继续处理其他输入
- 所有显式输入处理完后，如果没有任何有效项目，抛出：

```text
No valid TeX projects available for processing.
```

### 为什么要区分“压缩包有效”和“TeX 项目有效”

远程压缩包并不等于论文源码。它可能是：

- supplementary materials
- 图片或数据集压缩包
- 代码快照
- 仅包含 PDF 或其他非 TeX 资源的 wrapper

因此，第一阶段不能把“下载成功”误当成“输入成功”。最终仍要以现有项目识别链路是否接受该目录为准。

## 对现有模块的影响

### `main.py`

需要新增：

- `--project-url` 参数
- `project_url_items = runtime.split_cli_items(args.project_url)`
- 向 `runtime.prepare_projects()` 传递 `project_url_items`

### `src/runtime.py`

建议修改 `prepare_projects()` 签名，例如：

```python
def prepare_projects(
    config: Dict[str, Any],
    project_items: Optional[Iterable[str]] = None,
    project_url_items: Optional[Iterable[str]] = None,
    all_existing: bool = False,
) -> tuple[List[str], Dict[str, Any], str, str]:
```

新增处理分支：

- 遍历 `project_url_items`
- 调用远程下载 helper
- 下载成功后调用 `extract_local_archive()`
- 将结果加入 `projects`

### 新输入模块

建议新增一个小型模块，例如 `src/project_sources.py`，提供类似以下接口：

```python
def download_remote_archive(url: str, projects_dir: str) -> str:
    """Download a remote archive URL into projects_dir and return local archive path."""
```

如需拆分，可进一步内部拆成：

- URL 校验
- 响应头判定
- 文件名推断
- 下载落地

但第一阶段不需要过度抽象成 provider framework。

## 测试设计

第一阶段测试重点应放在 CLI 参数接线、`prepare_projects()` 分支、远程下载 helper 的行为。

### CLI 测试

新增或扩展现有 CLI 测试，断言：

- `--project-url` 能被 argparse 正确解析
- 解析后的值会被 `split_cli_items()` 展开
- `runtime.prepare_projects()` 会收到 `project_url_items`

### `prepare_projects()` 测试

覆盖以下场景：

- 只有 `project_url_items`，且下载成功
- 多个 URL 中部分成功、部分失败
- `--arxiv`、`--project`、`--project-url` 混合输入
- 所有远程 URL 都失败时，最终抛出 `No valid TeX projects available for processing.`

### 远程下载 helper 测试

使用 `unittest.mock` patch 网络请求，不做真实联网测试。

建议覆盖：

- 非 `http/https` URL 被拒绝
- 后缀合法且响应为压缩包时下载成功
- 后缀不明显但响应头表明是压缩包时允许下载
- 响应为 `text/html` 时拒绝
- HTTP 错误、超时、网络异常
- 文件名推断与同名冲突处理

## 文档更新

至少更新以下文档：

- `README.md`
- `README_ZH.md`

新增使用示例，并明确第一阶段限制。例如：

```bash
latextrans --project-url https://example.org/paper_source.tar.gz
```

文档中必须明确写清：

- 仅支持公开远程压缩包直链
- 支持 `.zip`、`.tar`、`.tar.gz`、`.tgz`
- 不支持下载页、DOI 页面、repo URL、认证下载

## 未来扩展预留

虽然第一阶段只做直链压缩包 URL，但本设计应为未来扩展保留清晰落点。

后续若要扩展，可沿以下顺序推进：

1. HTML 下载页解析
2. 少数高价值科研仓储 record 页解析
3. repo URL 支持
4. 认证下载

这些扩展都应优先复用本次新增的远程输入模块，而不是继续把分支堆进 `prepare_projects()`。

## 决策总结

本次设计选择：

- 新增显式参数 `--project-url`
- 第一阶段只支持公开远程压缩包直链
- 只在输入层新增下载能力
- 下载后完全复用现有本地 archive 解压与项目目录处理链路
- 采取保守校验与明确拒绝策略，不实现页面解析或 provider 适配

这是当前需求下风险最低、收益最直接的最小增量方案。
