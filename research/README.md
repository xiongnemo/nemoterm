# 当前测试版与待审阅材料

本目录只留当前工作的记录。测试所读取的固定输入另存于 [testdata/upstream](../testdata/upstream)；旧版截图、运行日志和原始失败均可从[清理前的提交](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)查阅。

- [当前测试版的跨标签修复、画面和内存记录](tab-drag-release.md)。`dist/nemoterm.exe` 对应 `6a2dc83`。其[完整交互回执](interaction-report-44525718005.zip)覆盖 13 组、81/81；报告只对所列交互负责。另一次同文件回放的[右键策略原始回执及启动贴图失败记录](right-click-6a2dc83.zip)：右键 12/12，整个客户端组 29/30。
- [同一测试版的聊天正文贴图复核](chat-attachments-6a2dc83.zip)：[Windows 回放 44533935921](https://github.com/xiongnemo/nemoterm/actions/runs/44533935921) 客户端组 30/30。六个贴图场景各测两个快捷键；12 次在带有本次输入标记的第一条聊天请求中均收到一张像素正确的 PNG。OpenCode 四次还各有一张图出现在独立标题请求中。Codex 本轮首次看到输入文字即贴图也通过，不改变此前的启动草稿失败。
- [重新构建后的全套交互报告](interaction-report-44529182879.zip)：`23d8118` 的 EXE（SHA-256 `30d406988c7b2a58f2f51c19ea5b6a78dfbf9442ea7837121a052899bf857c50`）为 79/81，仅 Codex 首次显示输入文字即贴图的窗口接口与系统键盘两项失败。就绪后两项均通过，选择 6/6、实际客户端默认网格 10/10；160×48 压力负载 GDI 和 DirectX 各 6/6，私有工作集峰值分别为 18,718,720 和 28,733,440 字节。这份报告对应另一份 EXE，不替换 `dist` 版本或其原始记录。
- [连续两次右键粘贴的旧版失败回执](local-paste-before-6a2dc83.zip)：开启“复制并粘贴”，在同一个窗口消息批次中分别选中 `ONE`、`TWO` 并右键。预览版子程序收到两个带括号的 `TWO`，而剪贴板最后是预期的 `TWO`。[远程窗口对照](https://github.com/xiongnemo/nemoterm/actions/runs/44535472277)保留了完整终端输入；测试使用原生窗口消息，这不是对真实手速的测量。
- [pterm 为什么轻量](pterm-findings.md)：指定的本机 0.85 二进制、REA 静态导入、私有工作集与总工作集的区别，以及该推论的边界。
- 待审阅的兼容性取舍：[Codex 启动草稿和图片粘贴](codex-bitmap-requests.md)、[宽字在行尾移动时的三个 XTerm 差异](column-edge-integrity.md)、[ReGIS 图形重绘前后的实际画面](regis-presented-pairs.md)。
