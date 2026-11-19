# 当前测试版与待审阅材料

本目录只留当前工作的记录。测试所读取的固定输入另存于 [testdata/upstream](../testdata/upstream)；旧版截图、运行日志和原始失败均可从[清理前的提交](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)查阅。

- [最新试用版 `3947dee3` 的内存、真实客户端、WSL1 和已知差异](acceptance-3947dee3.md)；[主屏/备用屏下 Shift 选区的前后截图](selection-screen.md)。

- 当前单文件是 `cf091974`：[交互报告及六类压力场景的原始样本](preview-cf091974.zip)为 **81/81**，GDI 和 DirectX 私有工作集峰值分别为 **19,701,760 / 29,061,120 字节**。另有[真实客户端内存对照](agent-session-cf091974.zip)、[滚动中矩形复制](selection-region-after-cf091974.zip)和 [Vim、tmux、颜色与 Sixel](xterm-clients-cf091974.zip)的同一 EXE 记录。
- 历史 `42232a2d` 测试版，[交互报告](https://github.com/xiongnemo/nemoterm/blob/ba1cc8fec99470377b668bd3a3a8cc6275b203a8/research/preview-42232a2d.zip)为 **79/81**。两项未过的都是 Codex 刚显示输入文字时粘贴位图；正式输入框就绪后两种快捷键均通过。六种压力场景的前端私有工作集峰值为 GDI 19,656,704 字节、DirectX 29,196,288 字节。[真实应用回放](https://github.com/xiongnemo/nemoterm/blob/ba1cc8fec99470377b668bd3a3a8cc6275b203a8/research/xterm-clients-42232a2d.zip)包括 Vim 和 tmux 内 Vim 各 4/4、颜色与 Sixel 各 2/2，以及默认网格 10/10。
- [已归档的 `6a2dc83` 与 `23d8118` 原始记录](../docs/PREVIEW_HISTORY.md#6a2dc83-后续回放)。
- [右键粘贴后立即按回车：`9d1da87` 原始失败](selection-enter-before-9d1da87.zip)。[托管 Windows 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44541755199)中，Shift 拖选 `RUN` 后右键“复制并粘贴”，紧接着 Enter。剪贴板正确，子程序却只收到回车；两侧状态回复可见，没有粘贴内容或括号标记。其余五个选择用例通过。 [修复版 `b3274ed` 的同一窗口回放](selection-enter-after-b3274ed.zip)在两次状态回复之间依次收到完整的括号粘贴 `RUN` 和单个 CR，剪贴板仍是 `RUN`，选择组 6/6。[该 EXE 与原版 pterm 的十次前端内存对照](selection-enter-pterm-b3274ed.zip)另行记录普通 Codex 工作负载。
- [连续两次右键粘贴的旧版失败回执](local-paste-before-6a2dc83.zip)：开启“复制并粘贴”，在同一个窗口消息批次中分别选中 `ONE`、`TWO` 并右键。预览版子程序收到两个带括号的 `TWO`，而剪贴板最后是预期的 `TWO`。[远程窗口对照](https://github.com/xiongnemo/nemoterm/actions/runs/44535472277)保留了完整终端输入；测试使用原生窗口消息，这不是对真实手速的测量。 [同样窗口消息在修复版的回执](local-paste-after-9d1da87.zip)：`9d1da87` 按点击时的内容入队，子程序按顺序收到 `ONE`、`TWO`，各一次，剪贴板仍是 `TWO`。选择分组 6/6。两份包保留所选原件、完整制品 ID 与摘要；新包还含 REA 对此 EXE 的静态导入记录。
- [多行文本粘贴 `476a2c76`：两份 Windows 原始记录和 REA 导入表](paste-lines-476a2c76.zip)。旧版 `97f8b05b` 的 GDI、DirectX 都不识别 `?2006`；发送的内容和紧接的 Enter 分别只有 CRLF 7/17、LF 9/17 与 XTerm 相符。[修复后](https://github.com/xiongnemo/nemoterm/actions/runs/44564122496)，两种渲染器、两种换行格式各 17/17，同时比较模式回复和确切输入。
- [局部滚屏中的矩形选区](scrollback-modes.md#矩形跨过-tui-的滚动区域)：`42232a2d` 的 GDI、DirectX 各通过 23 项实际键鼠检查。附修复前后截图、系统剪贴板与子进程输入，覆盖显式复制及右键复制并粘贴。
- [应用输出与键入时的滚动行为](scrollback-modes.md)：原版 XTerm、Windows 旧版和开发分支的逐字节与窗口位置对照。另附[滚动历史满后矩形高亮范围的修复与截图](scrollback-modes.md#滚动历史已满时的矩形高亮)。
- [pterm 为什么轻量](pterm-findings.md)：指定的本机 0.85 二进制、REA 静态导入、私有工作集与总工作集的区别，以及该推论的边界。[42232a2d 与原版 pterm 的 24 轮 Codex 对照](https://github.com/xiongnemo/nemoterm/blob/ba1cc8fec99470377b668bd3a3a8cc6275b203a8/research/agent-session-42232a2d.zip)：原版 / GDI / DirectX 前端私有工作集峰值分别为 3.78 / 5.49 / 9.66 MB。
- [XTerm 逐字节粘贴](../docs/INTERACTION_ACCEPTANCE.md#逐字节粘贴xterm-私有模式-2005)：`42232a2d` 尚不识别 `?2005`。在 GDI/DirectX 及 CRLF/LF 四组中，[实际粘贴数据](paste-quote-pipe-42232a2d.zip)各有 8/19 组与原版相同，都是不需要逐字节引用的阶段。
- 待审阅的兼容性取舍：[Codex 启动草稿和图片粘贴](codex-bitmap-requests.md)、[宽字在行尾移动时的三个 XTerm 差异](column-edge-integrity.md)、[ReGIS 图形重绘前后的实际画面](regis-presented-pairs.md)。
- 历史测试版 `9b5e1111`：[Windows 粘贴阶段的 114 项原始回执](paste-quote-native-9b5e1111.zip)均通过；[真实 WSL1 子程序的首轮回执](paste-quote-wsl-9b5e1111.zip)仍有逐字节引用、行边界和退出差异。详见[两端具体收到什么](../docs/INTERACTION_ACCEPTANCE.md#逐字节粘贴xterm-私有模式-2005)。[同机内存首轮](agent-session-9b5e1111-initial.zip)中，pterm 完成了 24 轮。GDI 的最后一轮先绘出回复结尾，随后才显示完整代码块；保存的最后一帧确有全部 16 行。这次未测完 DirectX，不能据此宣称候选版通过内存验收。
- 测试版 `9b5e1111` 的[交互报告及内存原始记录](https://github.com/xiongnemo/nemoterm/blob/b34d1a21f80027faf082357a522132b98fb0fdf0/research/interaction-9b5e1111.zip)：79/81，只有两次 Codex 启动草稿贴图未过。160×48、SarasaTermSC Nerd Light、每种渲染器六项压力的前端私有工作集峰值为 **GDI 19,333,120 / DirectX 28,909,568 字节**，总工作集各为 56,213,504 / 72,110,080 字节。[独立的 Linux 和 WSL1 对照](paste-quote-hosts-9b5e1111.zip)保留 PTY 原始读取及 Windows 宿主读事件。
- [`9b5e1111` 与原版 pterm 的同机 24 轮比较](https://github.com/xiongnemo/nemoterm/blob/b34d1a21f80027faf082357a522132b98fb0fdf0/research/agent-session-9b5e1111.zip)：基于同一份回复、实际 160×48 窗口、真实后端和私有工作集样本。聚合时同时要求最后一行、回复结尾和完整代码块出现在同一次屏幕读取中。

- [拖入 WSL 的资源管理器路径，以及修改默认 shell 后继续拖文件](drop-shell-paths.md)：旧版 6/18，候选 `cf091974` 18/18；两种渲染器的原始回放、Bash、PowerShell 和 cmd 的文件内容均有记录。
