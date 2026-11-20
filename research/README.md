# 当前测试版与待审阅材料

- [当前 dist 试用版 `3da1ebb8` 的四边标签截图、原始回执及下载](tab-faces-3da1ebb8.md)。
- [上一试用版 `abe6de57` 的验收、内存数据及已知差异](acceptance-abe6de57.md)。
- [`abe6de57`：按住 Shift 时文字移动，普通和矩形选区的前后画面](stationary-abe6de57.md)。
- [候选版 `28a2da26` 的交互和内存验收](acceptance-28a2da26.md)：中英文 DPI、就绪后贴图、响铃和设置复测，以及隔离单文件在右侧标签栏选区超时的原始记录。
- [候选版 `371a6f01` 的交互与内存验收](acceptance-371a6f01.md)：Windows 综合回归通过；隔离检查 169 项通过、启动早期贴图一项失败。
- [历史试用版 `03d0e0bc` 的全屏选区验收](acceptance-03d0e0bc.md)；[上一试用版的交互与内存](acceptance-706fe3ee.md)。[试用版历史和原始制品](../docs/PREVIEW_HISTORY.md)。
- [试用版的 Backspace 模式、真实按键与 XTerm 数据库差异](backspace-706fe3ee.md)。
- [Linux 调色后，窗口像素与子程序读到的文字和颜色是否一致](linux-console-palette.md)：GDI、DirectX 的整段和逐字节检查由各 3/6 到 6/6。
- [窗口或字号变化时，订阅程序收到的行列数和像素尺寸](inband-resize.md)。
- [tmux 写入系统剪贴板后，Vim 的 Shift 选区是否保留](tmux-clipboard.md)：GDI、DirectX 各测允许和拒绝写入。
- [清历史时的 Shift 拖选](selection-history-clear.md)：应用输出暂存到松手，本地菜单可以立即清除；两种渲染器共 20 个窗口。
- [应用只编辑选框旁的文字时保留矩形选区](rectangle-neighbour-edits.md)：两种渲染器各由 6/14 到 14/14，并独立核对快捷键复制和可选右键粘贴。
- [终端程序请求改变行列数时保留 Shift 选区](selection-page-size.md)：`226ddd98` 的 GDI 和 DirectX 实际窗口，修复前 4/28、修复后 28/28。
- [标签中键误关的修复和两版实际鼠标记录](tab-middle-gestures.md)。
- [Codex 输入就绪前后的贴图](codex-bitmap-requests.md)单列启动草稿和正常输入的结果；更早的 [`dc8b6913` 验收记录](https://github.com/xiongnemo/nemoterm/blob/212f1fcbf302e6b46d3ae2a887ac70915e367082/research/acceptance-dc8b6913.md) 已归档。
- [80／132 列、窗口尺寸与 Shift 选区](column-modes.md)：旧版、只改前端的版本，以及同时修复内置控制台后的原始记录和截图。
- [混合 profile 的关闭超时](profile-close-dc8b6913.md)：一次原始失败、对应转储的分析及相同 EXE 的六次独立复测。
- [主屏变窄后的 Shift 选区](selection-reflow.md)、[终端程序编辑列时的选区](selection-column-edits.md)，以及[宽字在行尾与 XTerm 的差异](column-edge-integrity.md)。
- [WSL profile 与子进程退出](wsl-profile.md)、[WSL 字节转发和窗口退出](wsl-relay-window.md)。
- [横向编辑文字时保留 ReGIS 图形](regis-horizontal.md)：旧版八种编辑会永久擦掉红线；`f20a27da` 的 36/36 个窗口重绘吻合，另列重绘前的实际差异。
- [擦除大张 ReGIS 图后保留另一屏的图](regis-sparse-erase.md)：GDI、DirectX 的旧版失败与新版回放。
- [ReGIS 首帧](regis-first-expose.md)与[窗口重绘前后画面](regis-presented-pairs.md)。
- [pterm 的进程和内存](pterm-findings.md)：原版 PuTTY 0.85 的二进制证据、私有与总工作集，以及与 Nemoterm 的比较范围。

测试需要的固定输入在 [testdata/upstream](../testdata/upstream)。已完成工作的原始截图和记录在[本轮清理前的版本](https://github.com/xiongnemo/nemoterm/tree/408a251dca608961d936f0200001cdd2f649079b/research)和[更早的归档](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)。
