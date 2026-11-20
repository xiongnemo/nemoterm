# `3da1ebb8` 单文件交互与内存验收

[取用 Windows x64 试用版](https://github.com/xiongnemo/nemoterm/actions/runs/44778524143/artifacts/14651845827)。`nemoterm.exe` 为 4,942,336 字节，SHA-256 `ff51561c1f0ff279ff0e85ea2f8f8eed8fe2892536477f5aba96aac63dc55763`。本页所有 Nemoterm 数据均对应这份 EXE。[标签外形与应用进度条截图](tab-faces-3da1ebb8.md)。

[严格交互汇总](https://github.com/xiongnemo/nemoterm/actions/runs/44778524143/artifacts/14652897524) **79/81**，未执行 0 项。原始未通过：agent-image-codex, agent-image-system-codex。Codex 编辑器就绪后，Ctrl+V 与 Ctrl+Shift+V 各经系统实按和窗口消息验证，4/4 在首条提交带一张正确原图，没有重复；早于就绪时 1/4 带图。原始结果分别保留。

单窗口 160×48 字符，SarasaTermSC Nerd Light。GDI、DirectX 在 Codex、Claude Code 和 OpenCode 的物理快捷键、默认右键仅复制、可选右键复制并粘贴上合计 [18/18](https://github.com/xiongnemo/nemoterm/actions/runs/44778524143/artifacts/14653186019)。应用已开启鼠标报告。[10 个窗口的 Shift 拖选](agent-grid-3da1ebb8.png)都复制出 **中文**，并核对了两字高亮、两侧未选中的字格与客户端实际收到的文本。关闭确认选「取消」后，10 个窗口都收到了接下来键入的提交标记，不用打开设置恢复输入。英、中语言各 12/12 个实际 DPI 场景通过。

| 前端进程负载 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm，24 轮 Codex | 3.77 MB | 22.74 MB | 4.46 MB |
| GDI，24 轮 Codex | 5.52 MB | 34.60 MB | 6.96 MB |
| DirectX，24 轮 Codex | 9.78 MB | 44.89 MB | 11.29 MB |
| GDI，六种满屏负载 | 19.23 MB | 54.01 MB | 22.69 MB |
| DirectX，六种满屏负载 | 29.50 MB | 71.93 MB | 32.62 MB |

MB 按十进制计。[独立托管 Runner 的字节级复核](https://github.com/xiongnemo/nemoterm/actions/runs/44783343067)读取原始逐进程记录：六种满屏负载的最高私有工作集分别为 **19,230,720 / 29,503,488 字节**。指标只计终端前端。原版 pterm 0.85 的[轻量化调查](pterm-findings.md)区分了总工作集与私有工作集。两份 Nemoterm 导入表对比只增加 `GDI32!Polygon`；采样的真实客户端窗口未发现已知 WebView 模块或子进程。

[本次验收的原始采样、截图回执、制品身份及 REA 静态导入表](acceptance-3da1ebb8.zip)。[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44778524143)与严格交互表分别计分；ReGIS、行末宽字符、发行版 terminfo 和部分 WSL1 路径仍有未通过项。本页不代表完整 XTerm 协议认证。[覆盖范围](../docs/PROTOCOL_COVERAGE.md)。
