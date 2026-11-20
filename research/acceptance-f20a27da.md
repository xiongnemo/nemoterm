# Windows x64 试用版 f20a27da：横向编辑后保留 ReGIS 图形

[下载受测单文件及其清单](https://github.com/xiongnemo/nemoterm/actions/runs/44692457263/artifacts/14609725291)。解压后只需 `nemoterm.exe`（4,947,456 字节），SHA-256 `3edfab2cd2a9eef007a2bdfaf7991390ce46f979b1ea69c7df4545dc6d0da86c`。

应用在图上插删字符或列、横向滚动时，旧版会永久擦掉原本未被删除的线段。修复版的 GDI 与 DirectX 在逐字节和整段写入下，36/36 个窗口重绘后与 XTerm 412 的同一画面逐像素一致（旧版 4/36）。文字应答均正确；重绘前仍有八种编辑画面不同。[真实窗口截图和剩余差异](regis-horizontal.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,768,320 | 22,708,224 | 4,468,736 |
| Nemoterm GDI，24 轮 Codex | 5,455,872 | 34,549,760 | 6,754,304 |
| Nemoterm DirectX，24 轮 Codex | 9,674,752 | 44,806,144 | 11,173,888 |
| Nemoterm GDI，六种满屏负载 | 19,963,904 | 56,827,904 | 23,064,576 |
| Nemoterm DirectX，六种满屏负载 | 28,635,136 | 71,614,464 | 32,243,712 |

[三组 24 轮 Codex 会话](https://github.com/xiongnemo/nemoterm/actions/runs/44693076370)均为 160×48，使用 SarasaTermSC Nerd Light，正常退出，无 WebView 模块或进程命中。每种渲染器的六种满屏压力场景分别取各列的最高值，内存上限按前端私有工作集计算。

[81 项交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44692457263)验证 **79/81**。六项选区和绑定、十项满屏 agent 交互均通过。另在[四个 GDI／DirectX 实际窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44694679112)中，子程序在按住 Shift 的过程中移动文字，正向拖选和反向矩形框选均保留四格高亮，两种复制操作均得到 `A中Z`，同一行的图形保持完整。Codex 正常输入框的四个新会话（实按或窗口消息，Ctrl+V 或 Ctrl+Shift+V）在第一次目标提交中均带一张像素正确的图片。在四个提前发键的会话中，首次目标提交只有文字，两项相应测试均保留为失败。[请求回执、交互汇总和内存原始记录](acceptance-f20a27da.zip)。

全量回归仍报告 [XTerm 宽字边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)和 [WSL1 按行粘贴及退出](wsl-relay-window.md)差异。此包是开发试用版。
