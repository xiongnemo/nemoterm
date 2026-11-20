# Windows x64 试用版 03d0e0bc：全屏左上角可以按 Shift 选字

[下载 Windows x64 单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14632717790)，解压后运行 `nemoterm.exe`。文件大小 4,955,648 字节，SHA-256 `7df6a717ad351e19b713a19953ca445a71232d938ffff3c90ee25b6a25ce41a4`。

旧版在全屏的独立窗口、标签栏在下方或右侧时，会把屏幕左上角的 Shift＋左键当成打开系统菜单，选不中第一行。现在按 Shift 可从这里拖选。独立窗口不按 Shift 点该处仍打开原来的系统菜单，旁边的普通点击照常交给接管鼠标的应用。

| 原生 Windows 鼠标和键盘操作 | GDI | DirectX |
| --- | ---: | ---: |
| [上一版](https://github.com/xiongnemo/nemoterm/actions/runs/44745725419)：独立窗口及标签栏四个位置 | 2/5 | 2/5 |
| [本版](https://github.com/xiongnemo/nemoterm/actions/runs/44746106994)：相同手势、字体和布局 | 5/5 | 5/5 |
| 本版同步刷新期间选区、复制与右键行为 | 13/13 | 13/13 |

字体为 `SarasaTermSC Nerd Light`。每个全屏窗口都实际复制了 `A中Z`，按 Ctrl+Shift+V 后子程序收到相同的 UTF-8 文本和粘贴边界。独立 Linux Runner 从原始窗口 PNG 核对高亮的四个字格和字形，旁边的 `!` 未选中。[原始截图、剪贴板、子程序字节、两版结果和 EXE 标识](acceptance-03d0e0bc.zip)。

在同一 EXE 的 [10 个真实客户端窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14633122365) 中，Codex、Claude Code 和 OpenCode 的选区交互均通过。[完整回归及内存结果](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996)保留了原始回执。下表列出同一轮托管 Windows 测得的峰值。

本版的前端内存实测（十进制 MB；不计 shell 和控制台宿主）：

| 负载 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm 原版，24 轮 Codex | 3.79 MB | 22.69 MB | 4.48 MB |
| Nemoterm GDI，24 轮 Codex | 5.87 MB | 37.21 MB | 7.32 MB |
| Nemoterm DirectX，24 轮 Codex | 10.03 MB | 47.37 MB | 11.66 MB |
| Nemoterm GDI，六种满屏负载 | 18.86 MB | 53.67 MB | 22.93 MB |
| Nemoterm DirectX，六种满屏负载 | 28.96 MB | 72.15 MB | 32.56 MB |

[真实 Codex 对话的原始内存取样](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14634285555)。REA 在本 EXE 中查到 684 个普通导入和 11 个延迟导入，未见已知 WebView 依赖；对话结束时的进程和模块取样也未见已知 WebView。

六种满屏负载均达标：[GDI](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14633838964) 实测峰值 18,862,080 字节（要求 <20,000,000）；[DirectX](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14634107401) 28,958,720 字节（要求 ≤30,000,000）。

`TERM=xterm` 和 `xterm-256color` 的 [Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14633486027)、[tmux 内 Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14632874230) 共八个窗口。[Sixel](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14633750489) 两种渲染器八张图通过像素比对。[中英文 DPI](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14634295203) 各 12/12。两种渲染器的默认右键、快捷键复制、可选右键复制并粘贴各通过 14、4、6 项。

[Codex 实际贴图回执](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14633103475)：正常编辑器就绪后 4/4 首条提交有正确图片；在初始输入框抢先粘贴的 4/4 首条提交只有文字。输入提示可见不等于编辑器已能接收附件。v0 要求就绪后一次粘贴只附上一张正确图片；就绪前不保证贴图，也不自动补发，以免重复添加。[Windows Terminal 和原版 pterm 的对照](codex-bitmap-requests.md)也观察到了相同的启动时序。

[整体交互](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14634632147) 79/81；未通过项目：agent-image-codex、agent-image-system-codex。

[独立 Runner 核对真实客户端的输入框像素和提交回执](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14635120591)：10/10。

仍保留原始差异：[ReGIS 横向编辑的中间帧](regis-horizontal.md)、[宽字在边界的行为](column-edge-integrity.md)、[Backspace 与系统 terminfo 的差异](backspace-706fe3ee.md)及托管 WSL1 的回归不计为通过。[协议覆盖表](../docs/PROTOCOL_COVERAGE.md)单列尚未实现的序列。
