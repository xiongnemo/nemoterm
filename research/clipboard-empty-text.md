# 剪贴板里既有位图，又有空文本

在 Codex 编辑器已经就绪时，如果 Windows 剪贴板同时提供图片和空文本，`6bed777` 的默认 Ctrl+Shift+V 什么也不发送。相同会话条件下，普通 Ctrl+V 可以附上同一张图片。这个终端问题与 [Codex 启动草稿尚未接受位图](codex-bitmap-requests.md) 是两种不同的情况。

[旧版实测](https://github.com/xiongnemo/nemoterm/actions/runs/44491225196) · [两个未改写的原始制品](clipboard-empty-text-6bed777.zip)。EXE SHA-256 为 `e50c888b1933893896de9889492b886a160f157ed3c4cd3ebbcd8c7d685019de`，固定 Codex 0.167.0 为 `edfdd48f8b458af0906e507b4cb05217b326c3d6e515e9f024e05e3b8d650f70`。实际键盘和窗口接口各用两个新会话，均先观察到 idle、提示文本重绘，再发布含 `CF_UNICODETEXT`（单个 NUL）与 `CF_DIB` 的剪贴板并分别按下两个快捷键。两次 Ctrl+V 都提交了一张像素正确的 32×16 PNG；两次 Ctrl+Shift+V 均没显示附件。失败后的独立 WinForms 读图控制一次成功、一次超时，原样保留。

独立的 ConPTY 输入接收器在前后两个 DSR 应答之间读字节。原版十项通过五项：纯位图交给应用；非空文本无论先后顺序均作为文本粘贴；两个空格保持不变；只有空文本时不产生输入。其余五项全部收到零字节：位图搭配空 Unicode（两个发布顺序）、空 ANSI、两个空格式，以及空 Unicode 搭配非空 ANSI 和位图。最后一种应该贴 ANSI 文字，前四种应该将一次 Ctrl+V 交给应用。

[修复](https://github.com/xiongnemo/nemoterm/commit/bec4002)在锁住剪贴板的工作线程中检查文本的第一个字符。文件列表及非空文本保持优先，空文本才尝试 ANSI 或位图。终端先释放剪贴板再交给应用，不复制像素，不重发按键。固定输入见 [远程回放方法](../docs/INTERACTION_ACCEPTANCE.md)。

[修复后同一套回放](https://github.com/xiongnemo/nemoterm/actions/runs/44492053927) · [两个原始制品](clipboard-empty-text-bec4002.zip)。`bec4002` EXE 的 SHA-256 为 `9f43a0ddc23219f3ac3974fee73b3b6f8de8f45c63adf3e668d7eef99984275e`。两版均为 4,872,192 字节。客户端摘要相同。修复后的每次成功提交都只有一张逐像素正确的图片；四个客户端自然退出并恢复测试剪贴板。

| 观测（旧版 → 修复版） | 结果 |
| --- | --- |
| 真实 Windows Ctrl+V；窗口接口 Ctrl+V | 2/2 → 2/2 |
| 真实 Windows Ctrl+Shift+V；窗口接口 Ctrl+Shift+V | 0/2 → 2/2 |
| 原生子进程精确输入 | 5/10 → 10/10 |

在四个先前完全无输入的位图场景，修复版都只发一个 `16`（十六进制 Ctrl+V）；有非空 ANSI 备选时，子程序收到一对 bracketed-paste 界符包住的 `fallback`。非空 Unicode `正文`、单纯空格、只有空文本、只有图片的行为逐字节不变。这些比较没有在第一次按键失败后补按。
