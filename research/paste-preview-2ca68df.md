# 单文件测试版 `2ca68df`：交互、内存与已知问题

[GitHub Windows x64 构建与完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44464971332) 的源码为 `2ca68dff4d3285054693abf3c6f3e4d4c4dc70e1`。受测 EXE 为 4,854,784 字节，SHA-256 `f2cb4fbae5a52ba3be8e4abb979a363e2b279591269b43838ee1da40957f7ca0`，制品 `14501593009`。本页数据仅适用于该文件。

## 实际使用

- 连续粘贴 4096 行和第二段 Unicode 文本时，修复前只收到 8 或 20 行。修复后，GDI、DirectX 的接口和 Windows 实按 `Ctrl+Shift+V` 均逐字收到完整两段，各段的括号标记也正确。[完整前后对照](consecutive-paste.md)。
- [同一镜像的交互汇总](paste-interaction-2ca68df.zip)核验 **78/80**。其中[默认网格回执](paste-agent-grid-2ca68df.zip)的 10 项全部通过：Codex、OpenCode、Claude，含普通与嵌套 PowerShell 启动及指定的字序配置，在 GDI / DirectX 上验证显示的字符、系统 Shift 拖选、复制、取消关闭后返回键盘输入和服务端实际收件。
- [真实客户端 30 项记录](paste-agent-cases-2ca68df.zip)中有两项失败，均是 Codex 刚启动时立即贴图（窗口接口、系统键盘）；就绪后的两个输入路径通过。没有用重试替换首次结果。这个汇总也不包含另行计分的独立 WinPTY 或上游 ReGIS 对照。
- 同一 CI 的配置与关闭窗口、真实 DPI、WSL Vim、WSL Sixel 和 terminfo 颜色作业通过。ReGIS 在原始 XTerm 残留画面对照仍有差异；Windows 实际窗口的绘图作业通过。不能将其标成全部 xterm 兼容。

补充回放发现一个未包含在上述 80 项计数里的边界：鼠标按下后、第一次拖动前，应用主动把行向下滚动时，选区可能带上邻行。受测 EXE 的两种渲染器、两个字体配置均复现；反向滚动对照正确。[向下滚动与剪贴板的原始回执](selection-pressed-before-2ca68df.zip) · [GDI 实际窗口](pressed-scroll-before-2ca68df.png) · [远程重放](https://github.com/xiongnemo/nemoterm/actions/runs/44467312884)。此版本仍含该问题。

## 内存

[同一台 GitHub Windows runner 上的十次冷启动](pterm-paste-memory-2ca68df.zip)（[工作流](https://github.com/xiongnemo/nemoterm/actions/runs/44466135631)），网格 160×48，字体 SarasaTermSC Nerd Light，两个可执行文件分别按各自哈希核对。以下是 Codex 回复后约 2.8–3.0 秒采样的**前端中位数**，范围为两次相反启动顺序，不包含 shell、控制台宿主或 Codex。单位为十进制 MB。

| 前端 | 私有工作集 | 总工作集 |
|---|---:|---:|
| pterm 0.85 | 3.75–3.77 | 21.80–22.58 |
| Nemoterm GDI（单标签） | 5.08–5.11 | 33.12–34.03 |
| Nemoterm DirectX（单标签） | 9.67–9.71 | 44.62–44.65 |

另有[六种 GDI 负载](paste-memory-gdi-2ca68df.zip)及[六种 DirectX 负载](paste-memory-directx-2ca68df.zip)，全部通过。各列为整个采样期间的独立最大值；两种渲染器最高私有工作集都出现在密集 Unicode 与 Kitty 图像同屏时。

| 前端 | 私有工作集峰值 | 总工作集峰值 | 私有提交量峰值 |
|---|---:|---:|---:|
| GDI | 19,267,584 B | 54,030,336 B | 22,892,544 B |
| DirectX | 28,848,128 B | 71,991,296 B | 32,325,632 B |

[REA 静态 PE 记录](rea-2ca68df-imports.json.gz)识别出 81 个常规 DLL 描述符、672 个常规导入，以及 11 个 ICU 延迟导入；与 `7ec651d` 按 DLL 名和符号/序号比较，新增一个 `IsProcessorFeaturePresent`，无移除。未发现 WebView 导入；静态导入不穷尽运行时加载。pterm 的 Win32 原生绘制、压缩回滚和按需重绘依据见 [pterm 研究](pterm-findings.md)。

## 独立 Claude / WinPTY 对照

[原始 3/4 记录](unicode-boundary-first-2ca68df.zip)：两种 Nemoterm 渲染器将 `e` 和组合重音按原序粘入；系统 ConPTY、WinPTY 独立驱动的 Claude 均将其按 NFC 送达服务端，未启用工具。WinPTY 没在正常视图的 15 秒期限内显示回复，随后退出也超时。

[配对诊断的五个原始回执](unicode-bridge-pair-2ca68df.zip)（[精确镜像回放](https://github.com/xiongnemo/nemoterm/actions/runs/44466529392)）保留原有流程和时限，另用同版本的 WinPTY 原生接口串行轮询读写。原驱动记录中，粘贴与回车在写入入口的同一毫秒内返回，服务在启动后 3,015 ms 发完回复，15 秒内未看到正常回复，诊断性重绘后才在 18,062 ms 读到标记。这次自然退出，但显示检查仍失败。串行驱动中，服务在 1,781 ms 发完，1,875 ms 首见回复，2,953 ms 完成自然回收。两组使用新会话；一次配对不能证明桥接方式是唯一原因。两条独立 WinPTY 路径都没有启动 Nemoterm。
