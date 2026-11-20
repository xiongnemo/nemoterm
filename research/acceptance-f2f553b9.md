# Windows x64 试用版 f2f553b9：鼠标按住后行宽改变，选区仍跟随原来的字

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44676544217/artifacts/14602885255)（4,929,536 字节），SHA-256：`559c68b808368953faecfb89357275cd98688cbb38365a8c7363cd48398407af`。

在 `E` 上按住 Ctrl+Shift 和左键，应用把行变为倍宽后再拖到 `G`，现在高亮和复制的都是 `EFG`。如果按下的字整个移出画面，这次拖选取消。两种渲染器合计 **34/34**，原试用版同组为 12/34。[实际窗口截图、剪贴板与应用输入](selection-rendition-press.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,776,512 | 22,683,648 | 4,472,832 |
| Nemoterm GDI，24 轮 Codex | 5,464,064 | 34,504,704 | 6,770,688 |
| Nemoterm DirectX，24 轮 Codex | 9,740,288 | 44,830,720 | 11,280,384 |
| Nemoterm GDI，六种满屏负载 | 18,759,680 | 53,542,912 | 22,437,888 |
| Nemoterm DirectX，六种满屏负载 | 29,478,912 | 72,753,152 | 32,620,544 |

[24 轮 Codex 会话](https://github.com/xiongnemo/nemoterm/actions/runs/44677163967)在同一台托管 Windows runner 上使用 160×48 和 SarasaTermSC Nerd Light，pterm 与 Scoop 中 0.85 原件的哈希相同。三个前端均正常退出，采样时未观察到 WebView 模块或进程。六种满屏负载的每一栏取各自最大值；内存上限以**前端私有工作集**核对。

[本版完整交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44676544217)验证 **79/81**。未通过：`agent-image-codex`、`agent-image-system-codex`。启动早期的两组里，各自的 Ctrl+V 都提交了图片，Ctrl+Shift+V 均未提交；输入框就绪后四种组合都提交了像素正确的图片。十项满屏 agent 交互、八个 Vim/tmux 窗口和两种渲染器的 Sixel 均通过。[原始制品身份、同一 EXE 的窗口和内存记录](acceptance-f2f553b9.zip)。整个 CI 仍保留严格上游[宽字符边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)和 [WSL1](wsl-relay-window.md) 的差异。

同次 [Windows ReGIS 组件](https://github.com/xiongnemo/nemoterm/actions/runs/44676544217/artifacts/14601874488)在整段输入和逐字节输入时各保留五个不匹配的历史帧（画笔回复相同）。[宽字边界](https://github.com/xiongnemo/nemoterm/actions/runs/44676544217/artifacts/14602319362)有 3/728 格不同，发生在 DCH、DECDC 和 SL；独立的 72 组整字完整性检查没有差异。[WSL1 配置测试](https://github.com/xiongnemo/nemoterm/actions/runs/44676544217/artifacts/14602094465)的三个 WSL 会话退出码均为 0，也没有残留临时 ELF，但子进程超过清理期限；两个脱离 Nemoterm 的 WSL 对照也超时。证据包 `protocol/` 内留有这些原始比较和所在制品的散列。
