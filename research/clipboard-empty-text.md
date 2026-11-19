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

同一 EXE 的[独立内存对照](https://github.com/xiongnemo/nemoterm/actions/runs/44492689635)在同一台 GitHub Windows Runner 上反向重复启动五种配置。固定 160×48、SarasaTermSC Nerd Light、真实 Codex 的首个回环回复后，取各轮私有工作集的中位数：pterm 为 3,739,648 和 3,780,608 字节；Nemoterm 单标签 GDI 为 5,095,424 和 5,115,904 字节；单标签 DirectX 为 9,699,328 和 9,728,000 字节。十个进程均自然退出，受检的前端模块和拥有的子进程无 WebView/Chromium 命中。[原始对照制品](clipboard-clients-bec4002.zip)另含未改写的 OpenCode 首轮失败记录。内存门槛另看压力负载。

## OpenCode：一张已附上的图为什么出现两份 HTTP 请求？

[首轮](https://github.com/xiongnemo/nemoterm/actions/runs/44492336169)的四次动作中有三次确实提交了图片，但每次收到两份各带一张正确图片的请求。另一次普通 Ctrl+V 超过 60 秒，没到提交阶段；同一窗口稍后的失败记录已有 `[Image`，中间没有再次粘贴。两项断言均保留。

[独立对照](https://github.com/xiongnemo/nemoterm/actions/runs/44493444752)在同一产品和 OpenCode 1.19.3 上，用实际键盘和窗口接口，分别测试两个快捷键、默认及禁用标题代理两套客户端配置。[四个原始制品](clipboard-opencode-titles-bec4002.zip)包含逐请求的标记、像素和截图。固定版本的 [ensureTitle](https://github.com/anomalyco/opencode/blob/e3c4eb242585dcd77be1a867391b7c25fd47ce52/packages/opencode/src/session/prompt.ts#L193-L236)会在首条真实输入后，给相同消息历史加上一条固定的生成标题指令。诊断只记录其中是否出现这条精确的用户消息，不按请求顺序猜测，也不丢弃任何请求。

| OpenCode 配置 | 真实 Ctrl+V | 真实 Ctrl+Shift+V | 接口 Ctrl+V | 接口 Ctrl+Shift+V |
| --- | --- | --- | --- | --- |
| 默认 | 1 正文 + 1 标题 | 1 正文 + 1 标题 | 1 正文 + 1 标题 | 1 正文 + 1 标题 |
| 仅在隔离测试配置禁用标题 | 1 正文 | 1 正文 | 附件超时；未提交 | 1 正文 |

表中的每份请求各含一张像素正确的 PNG；“标题”有上述精确指令，“正文”无该指令。默认四个场景在窗口显示了图片，随后一次 Enter 产生两种请求，按原来的严格单请求验收仍为 0/4。禁用标题时为 3/4；第四例的后续屏幕已有附件，不能算成按时送达。两种配置下，默认 Ctrl+Shift+V 的实际键盘与窗口接口都能附图。没有更改用户的 OpenCode 配置。

[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44491317295)的两组 160×48 压力测试各 6/6：同一 EXE GDI 最高私有工作集为 19,136,512 字节，DirectX 为 28,749,824 字节。[两组原始压力制品及 13 份交互分组记录](clipboard-aggregate-bec4002.zip)。逐份核对 EXE SHA-256、合并不重名的用例后，共 80 项、78 项通过；失败的是 `agent-image-codex`、`agent-image-system-codex`，两项都在客户端启动时贴纯位图。等待 Codex 就绪的对应组通过。DPI、设置、标签、选区、鼠标、文件传输、Unicode 边界和 WSL Sixel 作业通过；既有三个 ReGIS 核心历史画面作业仍失败。
