# 当前测试版与待审阅材料

本目录只留当前工作的记录。测试所读取的固定输入另存于 [testdata/upstream](../testdata/upstream)；旧版截图、运行日志和原始失败均可从[清理前的提交](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)查阅。

- 当前 `dist/nemoterm.exe` 对应 `97f8b05b`。[同一 EXE 的交互报告与原件](preview-97f8b05b.zip)为 **81/81**，覆盖 13 组。160×48 六种压力场景的前端私有工作集峰值为 GDI 19,415,040 字节、DirectX 28,565,504 字节。[真实应用回放](xterm-clients-97f8b05b.zip)包含 Vim 和 tmux 内 Vim 各 4/4、Sixel 和颜色，以及真实客户端默认网格 10/10。
- [已归档的 `6a2dc83` 与 `23d8118` 原始记录](../docs/PREVIEW_HISTORY.md#6a2dc83-后续回放)。
- [右键粘贴后立即按回车：`9d1da87` 原始失败](selection-enter-before-9d1da87.zip)。[托管 Windows 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44541755199)中，Shift 拖选 `RUN` 后右键“复制并粘贴”，紧接着 Enter。剪贴板正确，子程序却只收到回车；两侧状态回复可见，没有粘贴内容或括号标记。其余五个选择用例通过。 [修复版 `b3274ed` 的同一窗口回放](selection-enter-after-b3274ed.zip)在两次状态回复之间依次收到完整的括号粘贴 `RUN` 和单个 CR，剪贴板仍是 `RUN`，选择组 6/6。[该 EXE 与原版 pterm 的十次前端内存对照](selection-enter-pterm-b3274ed.zip)另行记录普通 Codex 工作负载。
- [连续两次右键粘贴的旧版失败回执](local-paste-before-6a2dc83.zip)：开启“复制并粘贴”，在同一个窗口消息批次中分别选中 `ONE`、`TWO` 并右键。预览版子程序收到两个带括号的 `TWO`，而剪贴板最后是预期的 `TWO`。[远程窗口对照](https://github.com/xiongnemo/nemoterm/actions/runs/44535472277)保留了完整终端输入；测试使用原生窗口消息，这不是对真实手速的测量。 [同样窗口消息在修复版的回执](local-paste-after-9d1da87.zip)：`9d1da87` 按点击时的内容入队，子程序按顺序收到 `ONE`、`TWO`，各一次，剪贴板仍是 `TWO`。选择分组 6/6。两份包保留所选原件、完整制品 ID 与摘要；新包还含 REA 对此 EXE 的静态导入记录。
- [应用输出与键入时的滚动行为](scrollback-modes.md)：原版 XTerm、Windows 旧版和开发分支的逐字节与窗口位置对照。另附[滚动历史满后矩形高亮范围的修复与截图](scrollback-modes.md#滚动历史已满时的矩形高亮)。
- [pterm 为什么轻量](pterm-findings.md)：指定的本机 0.85 二进制、REA 静态导入、私有工作集与总工作集的区别，以及该推论的边界。[同一台 Windows runner 上实按 24 条追问的原始记录](agent-session-97f8b05b.zip)：pterm / GDI / DirectX 均显示全部回复；整段采样的前端私有工作集峰值分别为 3.82 / 5.86 / 10.09 MB。
- 待审阅的兼容性取舍：[Codex 启动草稿和图片粘贴](codex-bitmap-requests.md)、[宽字在行尾移动时的三个 XTerm 差异](column-edge-integrity.md)、[ReGIS 图形重绘前后的实际画面](regis-presented-pairs.md)。
