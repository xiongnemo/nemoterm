# Nemoterm 的现代终端协议范围

Nemoterm 的目标是兼容 `TERM=xterm` / `xterm-256color` 应用，覆盖 Windows Terminal 和 Alacritty 实际支持的现代控制序列，并支持 Sixel。以两者固定版本的能力合起来做对照；某个扩展只在其中一方实现，仍然要看。`TERM` 是应用查找终端能力的名字，不意味着需要运行 Linux XTerm，也不等于承诺 XTerm 所有历史机型、X11 行为和私有扩展。

## 这些序列是做什么的？

终端收到字节后，有的显示为文字，有的执行操作。下面的 `ESC` 是一个字节 `0x1B`；`CSI` 通常写作 `ESC [`，`OSC` 是 `ESC ]`，`DCS` 是 `ESC P`，`APC` 是 `ESC _`。记号里的分隔空格不是要输入的空格。字符串常用 `ST`（`ESC` 后接反斜线）结束；OSC 也常用 `BEL` 结束。例：`\x1b[31m错误\x1b[0m` 中，应用真正发出 ESC 字节时，终端用红色显示“错误”，然后恢复默认样式。

| 应用想做的事 | 代表序列或模式 | 用户能看到的效果 |
| --- | --- | --- |
| 控制一行文字 | `CR`、`LF`、`BS`、`HT`、`BEL` | 回到行首、换行、后退、制表、响铃。进度条可以回到行首重写一行。 |
| 移动光标、编辑屏幕 | `CSI 4;10H`、`CSI 2J`、`CSI K`；插删字格或行、设置滚动区；`ESC 7` / `ESC 8` | 定位到第 4 行第 10 列、清屏、清除行尾、保存或恢复光标。编辑器只需重写变动的位置。 |
| 控制样式和颜色 | `CSI … m`（SGR），如 `1`、`4`、`38;5;n`、`38;2;r;g;b`、`0`；`OSC 4/10/11/12` 与相应复位 | 粗体、下划线、256 色、真彩色；调整或查询调色板、默认前景、背景、光标色。 |
| 进入全屏、成帧更新 | `CSI ?1049h/l`、`?25h/l`、`?2026h/l` | Vim 或 agent 可以切换备用屏、显示或隐藏光标；同步更新让用户看到画完的一帧。这里 `h/l` 分别表示开启或关闭。 |
| 收按键、鼠标、焦点、粘贴 | 应用光标键/小键盘、`CSI u` 键盘协商；`?1000/1002/1003`、`?1006`、`?1004`、`?2004`；Windows 特有的 `?9001` | 应用能区分方向键和修饰键，收到点按、拖动、滚轮、焦点及带边界的粘贴。`1002` 等决定**何时**上报，`1006` 决定**如何编码坐标**。 |
| 查询终端 | `CSI 6n` → `CSI 行;列R`；DA、模式查询 `DECRQM`、光标样式及尺寸查询 | 程序既会往终端写，也会从输入流读回复。检查能力时，回复的字节和状态与画面同样重要。 |
| 设置标题、链接、目录和剪贴板 | `OSC 0/2` 标题、`OSC 8` 超链接、`OSC 7` 当前目录、`OSC 52` 文本剪贴板；`OSC 133` 命令边界、`OSC 9;4` 进度 | 可点击的链接可以有自己的显示文字；shell 能报告工作目录、命令开始/结束和进度。剪贴板读写各自受权限控制。 |
| 在字符网格里画图 | Sixel：`DCS … q 数据 ST`；另有 Kitty 图形 `APC G … ST`、iTerm2 图片 `OSC 1337` | **Sixel 是必需项**。其余图片协议按传输方式和子命令分别记录，支持显示 PNG 不等于也支持从文件、共享内存或动画帧读取。 |

Shift 拖选屏幕文字、Ctrl+Shift+C/V 和可配置右键是 **Nemoterm 自己的操作**。子程序开启鼠标上报后，普通拖动可以交给它，按住 Shift 则由终端选中屏幕上看得见的字。它不依赖子程序实现 `OSC 52`。同样，Sixel 是程序把图片**输出到窗口**，而从系统剪贴板给 Codex **输入一张附件**是另一个方向，两项分别验收。

## 判断一项是否属于目标

1. 先看应用所需的 xterm 行为，再对照 [Alacritty 支持表（固定版本）](https://github.com/alacritty/alacritty/blob/aa5d942f46c40184a3f214830ff5f7989f4733a1/extra/man/alacritty-escapes.7.scd)、[Windows Terminal 解析器（固定版本）](https://github.com/microsoft/terminal/blob/5f7dc283013152f89bfb76950515c33f45157ad7/src/terminal/parser/OutputStateMachineEngine.cpp)及其 [VT](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences) 和 [shell 集成说明](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration)。按方向、参数、开关、可见效果及回复字节核对。上游写的是部分支持，就只引用它实际支持的部分。
2. **编号相同不代表语义相同。** 例如 Alacritty 的 `OSC 50` 支持 `CursorShape`；`7faa7fac` 的 [OSC 50 处理函数](../vendor/putty-0.85/terminal/nemo_font_ops.inc)实现的是字体查询和设置，没有该光标子命令。跨终端设置光标形状可用 `DECSCUSR`，例如 `CSI 2 SP q` 表示常亮方块（`SP` 是实际空格）。与这个已交付版本分开，开发版按 [Alacritty 使用的 vte 0.15.0 解析代码](https://github.com/alacritty/vte/blob/3b3da71c34cc1256c7e20981cf03f8eb95e08ffc/src/ansi.rs) 分派 `CursorShape=0/1/2`（方块、竖线、下划线），维持原有闪烁模式。是否兼容按新 EXE 的状态回复、光标像素和字体权限回归分别验收。
3. [XTerm 控制序列手册](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)还收录 VT52、Tektronix 绘图、打印机转发、ReGIS 等。仅因列在该手册，并不成为 v0 阻塞项。已实现的功能和重现过的差异保留在[详细支持表](PROTOCOLS.md)和[已知问题](KNOWN_ISSUES.md)里。Kitty、iTerm2、VS Code 的私有扩展也按子命令评估；不能因一条常用命令推及整个厂商命名空间。

## 两个参考终端实际列了哪些 OSC？

[Alacritty 固定版本的支持表](https://github.com/alacritty/alacritty/blob/aa5d942f46c40184a3f214830ff5f7989f4733a1/extra/man/alacritty-escapes.7.scd)把 `0`、`2`、`4`、`8`、`10`、`11`、`12`、`50`、`52`、`104`、`110`、`111`、`112` 列为已实现，明确拒绝 `1`（图标名称）。部分编号只实现特定参数，如 `50` 的光标形状。这是该手册的清单，不是其代码路径的全集：例如它依赖的 vte 解析器还识别 `OSC 22` 鼠标指针形状，这也不同于 `OSC 50` 的文字光标。

Windows Terminal 还有一批按子命令分派的 OSC。下面列出会影响现代应用的几个区别；上游的解析入口、具体操作和 Nemoterm 的当前实现要分开看。[微软固定版本的处理函数](https://github.com/microsoft/terminal/blob/5f7dc283013152f89bfb76950515c33f45157ad7/src/terminal/adapter/adaptDispatch.cpp) · [Nemoterm 的详细支持表](PROTOCOLS.md)。

| 控制串 | 参考实现的效果 | Nemoterm 的边界 |
| --- | --- | --- |
| `OSC 9;4`、`OSC 133;A/B/C/D`、`OSC 1337;SetMark` | 任务栏进度、提示符与命令边界、添加标记 | 有对应处理。`SetMark` 不代表要实现 iTerm2 的所有 `1337` 命令。 |
| `OSC 633;Completions;…` | 将 shell 给出的候选项交给 Windows Terminal 的补全界面 | 现有 `633` 命令标记和目录支持不包含补全菜单。 |
| `OSC 777;notify;标题;正文` | 上游启用桌面通知功能后才显示通知 | 当前 `777` 分支只识别内部文字排版提示，没有此通知子命令。 |
| `OSC 9001;CmdNotFound;命令名` | Windows Terminal 可向应用层请求查找缺失的命令 | 当前前端没有这个 OSC 操作。已有的 `CSI ?9001h` 是 Win32 键盘输入模式，不会搜索或安装软件。 |

这是一份范围说明，**不是逐项一致性认证**。`7faa7fac` 的[原始验收包](../research/trial-7faa7fac.zip)包括单文件身份、内存采样、实际客户端按键/选区、渲染画面和未通过的交互用例；[v0 验收结果](KNOWN_ISSUES.md#v0-的验收边界)给出统计和适用范围。
