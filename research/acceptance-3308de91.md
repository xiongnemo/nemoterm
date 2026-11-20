# Windows x64 试用版 3308de91：旧式调色后能读回同一行文字

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14622495149)（4,951,552 字节）；解压后运行 `nemoterm.exe`。SHA-256：`81727d3ba0a9c8deb51dd35923041081527e74645e799d9bc8ad79e52ac1fd44`。

程序使用 Linux 控制台调色命令后，窗口显示、Win32 读回的颜色和后续文字现在一致。旧版屏幕上有 16 个 `@`，子程序却读回空格。GDI、DirectX 的整段和逐字节四种组合各由 3/6 到 6/6；独立加入的大写、无效数字和标题回归各通过 9/9（包含原六项）。[新旧原始截图、字节和 Win32 记录](linux-console-palette.md)。

[整组交互](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221)在这份文件上通过 **79/81**。真实 Codex、Claude Code、OpenCode 的十个窗口场景都能在应用接管鼠标时 Shift 拖选，再用 Ctrl+Shift+C 复制 `中文`，已复核高亮覆盖四格且没有越界。[原始窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14622391223) · [选区局部图](agent-wide-3308de91.png)。矩形选区邻近文字被编辑后，GDI、DirectX 各通过默认右键 14/14、快捷键复制 4/4、可选右键复制并粘贴 6/6。[GDI 原始记录](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14621189616) · [DirectX 原始记录](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14622236169)。

两项未通过的是输入框尚未就绪时的 Codex 贴图：四次首次目标请求均只有文字。待输入框就绪再粘贴，4/4 次首次请求带一张像素相同的图片。[参考终端的同类对照](codex-bitmap-requests.md)。

| 前端、负载（字节） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm，24 轮 Codex | 3,780,608 | 22,720,512 | 4,456,448 |
| Nemoterm GDI，24 轮 Codex | 5,808,128 | 37,138,432 | 7,176,192 |
| Nemoterm DirectX，24 轮 Codex | 10,067,968 | 47,362,048 | 11,673,600 |
| Nemoterm GDI，六种满屏负载 | 19,288,064 | 55,959,552 | 22,777,856 |
| Nemoterm DirectX，六种满屏负载 | 28,684,288 | 71,966,720 | 32,980,992 |

[同机 24 轮会话](https://github.com/xiongnemo/nemoterm/actions/runs/44721354472)使用 160×48 和 `SarasaTermSC Nerd Light`，三次会话均正常退出。运行时采样未发现 WebView 模块或进程。对相同 EXE 的 REA 静态检查也覆盖 680 项普通导入、11 项延迟导入，未见已知浏览器组件；这两个检查的原始记录均随附在验收包里。上限按前端的私有工作集计算，shell、控制台宿主与 agent 子进程不计入。

`TERM=xterm`、`TERM=xterm-256color` 下，[Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14622440957) 和 [tmux 内的 Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14621314715) 共 8/8 个窗口通过鼠标、调整窗口、宽字选择、矩形复制和粘贴后保存 UTF-8 文件的检查。[Sixel 原始窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/artifacts/14622525458)的 24×18 五色图像与独立解码一致，GDI、DirectX 的绘制前、绘制后、重绘和擦除共 8/8 张截图逐像素相符。

[独立单文件回归](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221/job/136237030733)另有一次 DirectX 窗口退出超时：101 条参考应答、窗口颜色和 1,000 次保存/恢复已执行完，收到结束请求后进程在 10 秒内没有退出，作业强制清理。它与上述 81 项交互分开计数。

这是开发试用版。完整 CI 保留 [XTerm 宽字边界](column-edge-integrity.md)、[ReGIS 中间画面](regis-horizontal.md)与 [WSL1 尺寸读取](wsl-relay-window.md)等严格对照的差异。[本版原始回执索引与核对结果](acceptance-3308de91.zip)。
