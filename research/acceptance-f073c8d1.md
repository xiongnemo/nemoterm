# Windows x64 试用版 f073c8d1：Shift 只复制可见的放大行

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44673225346/artifacts/14601575029)（4,929,536 字节），SHA-256：`71911a8db87b1d10d5d23504f3fb503c2bd03dc4472465611efd826a207a98fc`。

应用把行放大后，原版跨行复制会夹带移到窗口外的文字。这个版本的 GDI 和 DirectX 原始窗口合计通过 **18/18** 个对应检查（旧版 4/18）。Windows 系统鼠标和 Ctrl+Shift+C 也通过；同一选区的 GDI 截图未变，剪贴板只剩用户看到的文本。[选区、系统剪贴板和原始截图](selection-scaled-copy.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,768,320 | 22,663,168 | 4,464,640 |
| Nemoterm GDI，24 轮 Codex | 5,775,360 | 37,122,048 | 7,208,960 |
| Nemoterm DirectX，24 轮 Codex | 10,051,584 | 47,403,008 | 11,677,696 |
| Nemoterm GDI，六种满屏负载 | 19,361,792 | 54,099,968 | 22,208,512 |
| Nemoterm DirectX，六种满屏负载 | 29,495,296 | 74,842,112 | 33,304,576 |

[24 轮 Codex 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44673805234)使用 160×48 窗口和 SarasaTermSC Nerd Light，原版 pterm 与本机 Scoop 安装的 0.85 文件 SHA-256 相同。三组都正常退出，采样时未发现 WebView 模块或进程。REA 静态检查确认此 EXE 是 x64 原生 PE。总工作集和私有工作集分别计量，六种负载的每一栏取各自最大值。

[整套交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44673225346)通过 **79/81**；未通过：`agent-image-codex`、`agent-image-system-codex`。Codex 输入框稳定后的四项贴图都收到了像素匹配的图片。十项满屏 agent 交互、Vim 及 tmux 中的 Vim 合计八个窗口、两种渲染器的 Sixel 均通过。[本版的 ReGIS 擦图回归](https://github.com/xiongnemo/nemoterm/actions/runs/44673225346/artifacts/14601390693)在两种渲染器下都完整恢复了备用屏的 101 个红色像素。[原始记录及精确制品身份](acceptance-f073c8d1.zip)。严格上游对照仍有[宽字符边界](column-edge-integrity.md)、[ReGIS 重绘](regis-presented-pairs.md)与 [WSL1 按行粘贴](wsl-relay-window.md)等已知差异。
