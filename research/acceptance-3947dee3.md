# `3947dee3`：实际交互与内存

[单文件候选](https://github.com/xiongnemo/nemoterm/actions/runs/44607488923/artifacts/14571391046)是 Windows x64 的 `nemoterm.exe`，4,866,048 字节，SHA-256 `3119a405be7f6d3a88ecee19e82e768fab37a5530a6f4bb26d6ef069d4a499b2`。以下观测来自 GitHub 托管 runner；产品、字体、窗口、输入和原始记录均绑定这份文件。完整回归包含独立的 XTerm 历史画面对照，不能用交互通过率替代。

[完整交互报告](https://github.com/xiongnemo/nemoterm/actions/runs/44607488923/artifacts/14572393552)为 **79/81**，未通过的两项均为 Codex 启动时贴图。[原始 GitHub 制品及其散列](acceptance-3947dee3.zip)包括三份前端进程采样、常规和满屏客户端回执、12 个内存工作负载、真实 WSL1 客户端、两组协议差异和原始交互汇总。

| 操作 | 同一候选的实际结果 |
| --- | --- |
| 全屏应用接管鼠标后，用 Shift 选字；应用又请求当前屏幕 | [真实 GDI 和 DirectX](selection-screen.md) 均保留高亮，右键复制 `BCD`。两种渲染器共 14/14，旧版 6/14。额外在已经拖出高亮时让子程序写入屏幕请求，松手后检查快捷键、右键和应用原始输入，两种渲染器共 8/8。确实换屏或清屏时，两版均把下一次独立右键交回应用。 |
| 在真实 Codex、OpenCode、Claude 的 160×48 窗口选取中英文、组合字符和图标 | 两种渲染器的 10/10 项通过；包括视觉顺序、复制和提交回环验证。30 项常规客户端用例中 28 项通过；默认右键仅复制、显式右键复制并粘贴及快捷键都在其中。 |
| 从剪贴板发送图片 | Codex 正式输入框接手后的窗口按键和真实键盘均通过，两种快捷键各提交一张正确图片；两个 OpenCode 用例通过。两项 Codex 启动草稿测试的 `Ctrl+V` 和 `Ctrl+Shift+V` 都没在期限内出现附件，原测试记为失败。[其他终端的对照](codex-bitmap-requests.md)。 |
| WSL1 运行 Vim，以及 tmux 内 Vim | GDI、DirectX 各用 `TERM=xterm` 和 `TERM=xterm-256color`。直接启动 4/4，tmux 内 4/4；覆盖键盘、缩放以及应用接管鼠标后的本地选区。 |
| WSL1 使用 terminfo 输出颜色、使用 img2sixel 输出图形 | 两个窗口后端分别通过颜色 2/2、Sixel 2/2。以上 WSL 均在托管 runner，不使用开发电脑的发行版。 |

**与指定的 pterm 比内存。** [同一台 runner 的 24 轮 Codex 追问](https://github.com/xiongnemo/nemoterm/actions/runs/44608688848)使用 SarasaTermSC Nerd Light 和 160×48。每个窗口都收到初始回复和 24 个不同提示的回复，25 个聊天请求，三次自然退出。单位为十进制 MB；只计前端，shell、Codex 和控制台宿主各自的进程内存不计入。

| 24 轮会话的采样峰值 | 私有工作集 | 总工作集 | 私有提交量 |
| --- | ---: | ---: | ---: |
| pterm 0.85 | 3.77 MB | 22.72 MB | 4.46 MB |
| Nemoterm GDI | 5.76 MB | 37.13 MB | 7.21 MB |
| Nemoterm DirectX | 10.13 MB | 47.46 MB | 11.80 MB |

另外独立测了 160×48 的六种满屏工作负载：从密集文字、内嵌图片、动画到压缩和 Unicode 占位的 Kitty 图形，每个后端六项都通过。GDI 的私有工作集最高 **19,103,744 字节**，总工作集最高 53,329,920、私有提交最高 22,179,840；DirectX 对应为 **29,118,464**、72,335,360 和 32,727,040 字节。各列均是采样峰值，不保证同时出现。

pterm 的 SHA-256 与指定的本机安装文件相同。三个会话结束前的模块与进程快照均未出现检测列表中的 WebView 运行时。与上一候选相比，PE 静态导入仅新增一个已存在 DLL 的 `IsProcessorFeaturePresent` 声明，没有新 DLL 名称。运行时采样和静态表分别记录。

**具体仍不同的地方。** [宽字跨边界左移](column-edge-integrity.md)有 3/28 行与原版 XTerm 的回复不同；同一 EXE 在另外 72 种按完整源字推导的情况都保留了字符。ReGIS 的[历史滚动画面和调色时机](regis-presented-pairs.md)仍未完全一致。WSL1 使用 `?2005` 时仍不能保证引用后的 UTF-8 与内嵌换行逐字节送达；本轮四次原生窗口测试中，一次 GDI 场景在规范行读取阶段超时并强制清理。保留原作业的失败。这些情况都不宜据此宣称完全模拟 XTerm。
