# LaTeX 编译卡死问题记录：algorithm2e caption

## 背景

处理 `outputs\ch_2205.05124` 时，翻译后的 `acl_latex.tex` 已生成，但 `pdflatex` 编译长时间无结果。一次独立复现中，`pdflatex` 运行 120 秒仍未退出，只生成了早期的 `acl_latex.pdf`、`.aux`、`.out` 和 `.log`。

原目录中还残留了：

```text
acl_latex.synctex(busy)
build_pdflatex\acl_latex.synctex(busy)
```

这通常说明上一次编译进程曾被中断，或仍处于 SyncTeX 写入未完成状态。

## 现象

日志没有明确报错，尾部停在正文前几页附近。例如基线编译日志显示已经完成到第 2 页，并继续处理第 115 行附近的引用警告，之后不再输出。

这类情况不能只根据日志最后一行判断根因，因为 TeX 卡住时最后输出的位置可能只是最后一次成功 flush 的位置，并不一定是实际触发点。

## 定位过程

本次在临时目录中拆分原 `acl_latex.tex`，按正文结构生成多个独立测试文件：

```text
outputs\ch_2205.05124\2205.05124\compile_isolation_tmp\split_tests
```

拆分时需要注意：

- 临时目录必须复制 `.sty`、`.bst`、`.bib`、图片等资源文件。
- 如果资源没复制，所有分段都会在导言区或 `\includegraphics` 处失败，容易误判成正文问题。
- 每个分段使用独立 build 目录，并用超时包装器运行 `pdflatex`。

分段结果：

- `chunk_01_abstract_intro.tex`：正常结束。
- `chunk_02_algorithm_only.tex`：超时。
- `chunk_03_post_algorithm_to_main_table.tex`：正常结束。
- 后续正文、相关工作、参考文献、附录表格分段：均正常结束。

继续缩小后发现：

- 保留完整 algorithm 块但删除 `\caption`：正常结束。
- 保留整篇文章但只注释 algorithm 的 `\caption`：正常结束。
- 删除整个 algorithm 块：正常结束。

## 根因判断

触发点是原文件中的 algorithm 标题：

```tex
\caption{提取 $\zsteer$ 用于句子\label{alg: extract_steering_vector}}
```

该行位于 `algorithm2e` 的 `algorithm` 环境中。在当前组合下：

- `pdflatex`
- `ctex`
- `acl.sty`
- `algorithm2e`
- 双栏 ACL 模板

`algorithm2e` 的 caption 机制会导致编译长时间无输出卡住。删除该 `\caption` 后，完整文档可以在 30 秒内完成 `pdflatex` 编译。

## 处理建议

本次已验证可行的规避方式是：绕过 `algorithm2e` 的 `\caption`，但用 `\refstepcounter{algocf}` 手动推进算法计数器并保留 `\label`，这样正文中的 `\ref` 仍可解析。

```tex
\refstepcounter{algocf}\label{alg: extract_steering_vector}
\textbf{算法~\thealgocf: 提取 $\zsteer$ 用于句子}\par
\smallskip
```

其他可选方式：

1. 将 algorithm 的 `\caption` 改为普通加粗文本，不走 `algorithm2e` 的 caption 机制。
2. 保留算法内容，但去掉 `\label`，先确认是否只有 caption-label 组合触发问题。
3. 如果必须保留编号和引用，改用更简单的 `figure`/`table` 包装，或在正文中手写编号说明。
4. 对中文标题尤其谨慎；如果 caption 必须存在，可先改成纯英文短标题验证。

如果后续自动修复器要处理类似问题，应优先做最小化修改：只替换触发卡死的 caption，不要同时重排算法体。

## 排查清单

遇到 LaTeX 编译卡死时，按以下顺序处理：

1. 用独立 build 目录和明确超时复现，避免污染原输出目录。
2. 查看 `.log` 尾部，但不要把最后输出行直接当成根因。
3. 按章节、浮动体、公式、算法、表格拆分成临时文件。
4. 临时目录复制所有依赖资源，再跑分段编译。
5. 找到超时分段后继续二分，直到定位到具体环境或命令。
6. 用“只删除一行”或“只注释一个环境”的对照实验确认根因。

## 本次结论

`ch_2205.05124` 的卡死不是图片、参考文献或附录表格导致的，而是 `algorithm2e` 环境中的 `\caption` 触发。正文其他部分在拆分测试中均能完成编译。
