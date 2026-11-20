# Windows x64 试用版 03d0e0bc：全屏左上角可以按 Shift 选字

[下载 Windows x64 单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14632717790)，解压后运行 `nemoterm.exe`。文件大小 4,955,648 字节，SHA-256 `7df6a717ad351e19b713a19953ca445a71232d938ffff3c90ee25b6a25ce41a4`。

旧版在全屏的独立窗口、标签栏在下方或右侧时，会把屏幕左上角的 Shift＋左键当成打开系统菜单，选不中第一行。现在按 Shift 可从这里拖选。独立窗口不按 Shift 点该处仍打开原来的系统菜单，旁边的普通点击照常交给接管鼠标的应用。

| 原生 Windows 鼠标和键盘操作 | GDI | DirectX |
| --- | ---: | ---: |
| [上一版](https://github.com/xiongnemo/nemoterm/actions/runs/44745725419)：独立窗口及标签栏四个位置 | 2/5 | 2/5 |
| [本版](https://github.com/xiongnemo/nemoterm/actions/runs/44746106994)：相同手势、字体和布局 | 5/5 | 5/5 |
| 本版同步刷新期间选区、复制与右键行为 | 13/13 | 13/13 |

字体为 `SarasaTermSC Nerd Light`。每个全屏窗口都实际复制了 `A中Z`，按 Ctrl+Shift+V 后子程序收到相同的 UTF-8 文本和粘贴边界。独立 Linux Runner 从原始窗口 PNG 核对高亮的四个字格和字形，旁边的 `!` 未选中。[原始截图、剪贴板、子程序字节、两版结果和 EXE 标识](acceptance-03d0e0bc.zip)。

在同一 EXE 的 [10 个真实客户端窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996/artifacts/14633122365) 中，Codex、Claude Code 和 OpenCode 的选区交互均通过。[完整回归及内存结果](https://github.com/xiongnemo/nemoterm/actions/runs/44745154996)另计；上一版的内存数字不作为本版测量值。
