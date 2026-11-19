# `844ad5c3`：Windows x64 单文件试用版

[下载 Actions 产物](https://github.com/xiongnemo/nemoterm/actions/runs/44629889832/artifacts/14581148646)。`nemoterm.exe` 为 4,921,856 字节；SHA-256 `ea0bfee65ecae2fd8bb24571b865812b864cc7be1e0dbc604af0797410cfc709`。新功能是[窗口宽度变化时保留固定网格上的 Shift 选区](selection-width.md)，以及[按配置方案保存 x64 WSL 的 Linux PTY 选项](wsl-profile.md)。这些测试全部在 GitHub 托管机器完成。

| 160×48 负载，SarasaTermSC Nerd Light | 前端私有工作集峰值（字节） | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm 0.85：同机 Codex 首次输入和 24 轮追问 | 3,768,320 | 22,659,072 | 4,456,448 |
| Nemoterm GDI：同样的对话 | 5,484,544 | 34,484,224 | 6,848,512 |
| Nemoterm DirectX：同样的对话 | 9,764,864 | 44,863,488 | 11,264,000 |
| GDI：六种满屏图文压力 | **18,915,328** | 53,686,272 | 22,212,608 |
| DirectX：六种满屏图文压力 | **29,360,128** | 74,100,736 | 32,837,632 |

这是各列的独立采样峰值；子程序和控制台宿主另行记录。两种渲染器都通过各自的**私有工作集**限制。[24 轮对照](https://github.com/xiongnemo/nemoterm/actions/runs/44631199901)中每个前端均有 25 条聊天请求并自然退出；检查过的模块与子进程中未观察到 WebView 运行时。

[完整交互汇总](https://github.com/xiongnemo/nemoterm/actions/runs/44629889832/artifacts/14583017550)为 **80/81**：Codex 启动阶段的窗口按键组没观察到附件，Ctrl+V、Ctrl+Shift+V 的首次手势均保留失败。同一轮真实键盘的启动测试通过；就绪后的两种绑定及两种按键途径全部通过。不要把某次启动早按的结果理解为必须先发一条消息。[原版 pterm 的对照](codex-bitmap-requests.md)。

真实 Codex、Claude Code、OpenCode 的满屏选区是 **10/10**。同一 EXE 的真实 Vim 和 tmux 内 Vim 在两个 TERM 和两种渲染器下为 **8/8**；颜色及 Sixel 各有两份通过的实际窗口记录。[原始回执、压力采样和制品清单](acceptance-844ad5c3.zip)与[横向缩放截图](selection-width.md)分开保留。

这个试用版还会在主屏自动折行后清除原来的选区；加宽窗口不会把已清掉的选区找回来。后续候选单独验收。整套回归也未全绿：[ReGIS 首次呈现](regis-presented-pairs.md)、[XTerm 的三格宽字差异](column-edge-integrity.md)与 [WSL1 的行读取、退出时限](wsl-profile.md)没有因为这次交互和内存检查通过而取消。
