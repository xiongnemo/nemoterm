# 当前测试版与待审阅材料

本目录只留当前工作的记录。测试所读取的固定输入另存于 [testdata/upstream](../testdata/upstream)；旧版截图、运行日志和原始失败均可从[清理前的提交](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)查阅。

- 当前 `dist/nemoterm.exe` 对应 `b3274ed`。[同一 EXE 的 13 组交互报告和原始回执](preview-b3274ed.zip)为 79/81，仅 Codex 启动时立即贴图的两项未过。160×48 压力场景 GDI、DirectX 各 6/6，前端私有工作集峰值为 18,812,928 和 29,585,408 字节。[应用回放与截图](xterm-clients-b3274ed.zip)：WSL 中 Vim 和 tmux 内 Vim 各 4/4、Sixel 两个渲染器均正确显示、重绘和擦除，还包含颜色与默认网格真实客户端回执。
- [已归档的 `6a2dc83` 与 `23d8118` 原始记录](../docs/PREVIEW_HISTORY.md#6a2dc83-后续回放)。
- [右键粘贴后立即按回车：`9d1da87` 原始失败](selection-enter-before-9d1da87.zip)。[托管 Windows 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44541755199)中，Shift 拖选 `RUN` 后右键“复制并粘贴”，紧接着 Enter。剪贴板正确，子程序却只收到回车；两侧状态回复可见，没有粘贴内容或括号标记。其余五个选择用例通过。 [修复版 `b3274ed` 的同一窗口回放](selection-enter-after-b3274ed.zip)在两次状态回复之间依次收到完整的括号粘贴 `RUN` 和单个 CR，剪贴板仍是 `RUN`，选择组 6/6。[该 EXE 与原版 pterm 的十次前端内存对照](selection-enter-pterm-b3274ed.zip)另行记录普通 Codex 工作负载。
- [连续两次右键粘贴的旧版失败回执](local-paste-before-6a2dc83.zip)：开启“复制并粘贴”，在同一个窗口消息批次中分别选中 `ONE`、`TWO` 并右键。预览版子程序收到两个带括号的 `TWO`，而剪贴板最后是预期的 `TWO`。[远程窗口对照](https://github.com/xiongnemo/nemoterm/actions/runs/44535472277)保留了完整终端输入；测试使用原生窗口消息，这不是对真实手速的测量。 [同样窗口消息在修复版的回执](local-paste-after-9d1da87.zip)：`9d1da87` 按点击时的内容入队，子程序按顺序收到 `ONE`、`TWO`，各一次，剪贴板仍是 `TWO`。选择分组 6/6。两份包保留所选原件、完整制品 ID 与摘要；新包还含 REA 对此 EXE 的静态导入记录。
- [pterm 为什么轻量](pterm-findings.md)：指定的本机 0.85 二进制、REA 静态导入、私有工作集与总工作集的区别，以及该推论的边界。
- 待审阅的兼容性取舍：[Codex 启动草稿和图片粘贴](codex-bitmap-requests.md)、[宽字在行尾移动时的三个 XTerm 差异](column-edge-integrity.md)、[ReGIS 图形重绘前后的实际画面](regis-presented-pairs.md)。
