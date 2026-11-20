# Nemoterm Windows x64：28a2da26 验收

**本轮记录：** 交互报告已出。分发版本以 [README 下载区](../README.md#下载) 为准。

[下载单文件制品](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/artifacts/14641122715)，解压后运行 `nemoterm.exe`。4,940,800 字节，SHA-256 `1bbae45b5cccb638f4cced63e0faee546ff92bf72d03a9c906a39bb9fbaf801f`。此页的产品数据均对应这份 EXE，构建、桌面交互和内存采样均来自 GitHub 托管 Runner。

「窗口 → 字符编码 → 画线字符」的页标题和分组说明现在都会切换到中文。[修复前后截图](line-drawing-comparison.png) · [原始图片、英文和中文控件回执](line-drawing-titles.zip)。[DPI 回归](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/artifacts/14640023541)用英文和简体中文分别完成 12/12 个场景：独立窗口和标签模式均覆盖 100% 至 200% 真实缩放以及运行中改变比例。

[交互总表](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/artifacts/14643255599)：**77/81**；原始已运行但未通过：agent-image-codex；agent-image-system-codex。未执行：bell-api、bell-visual。Codex 编辑器就绪后，两种粘贴快捷键分别用 Windows 实按和窗口接口验证。4/4 次首条消息都恰好带一张正确的图片，后续无重复。首次看到输入提示即按键的四次，4 次只有文字，0 次附上正确图片；此时不保证输入框能接收附件。两种时机的原始成绩分别保留。

Codex、Claude Code、OpenCode 分别在 GDI 和 DirectX 下验证了快捷键复制/粘贴、默认右键只复制和可选的右键复制并粘贴：**18/18**。其中 18 次拖选时应用已接管鼠标。每次都验证 Shift 选区的高亮和两侧未选中字格，读回剪贴板，并核对客户端实际提交的文本只出现一次。默认右键不改变输入框；选择“复制并粘贴”后，不需要再按粘贴键。[原始记录](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/artifacts/14642296304) · [十个默认网格窗口的独立像素复核](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/artifacts/14642473331)。[查看三个客户端的 Shift 拖选前后对照图](system-selection-28a2da26.png)。

GDI 和 DirectX 各通过 5 种全屏布局、13 项同步刷新期间的选区操作、24 项复制与右键绑定。四个位置的标签栏及窗口缩放、鼠标、字体缩放和文件拖放均已在此版执行。Git Bash 启动和关闭 24/24 无残留；首次查询可用 shell 不创建 Default profile。

| 负载（只计前端进程） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮真实 Codex | 3.77 MB | 22.72 MB | 4.46 MB |
| Nemoterm GDI，24 轮真实 Codex | 5.58 MB | 34.64 MB | 6.84 MB |
| Nemoterm DirectX，24 轮真实 Codex | 9.69 MB | 44.83 MB | 11.16 MB |
| GDI，六种 160×48 满屏负载 | 19.47 MB | 54.28 MB | 22.54 MB |
| DirectX，相同六种负载 | 29.18 MB | 72.15 MB | 33.26 MB |

内存采用十进制 MB。GDI 私有工作集要求 <20,000,000 字节，实测 19,468,288；DirectX 要求 ≤30,000,000 字节，实测 29,184,000。使用 SarasaTermSC Nerd Light。REA 静态读得 685 个普通导入和 11 个延迟导入，与上一版一致；实测时采样的前端模块和进程也未出现已知 WebView。Shell、控制台宿主和客户端的内存不计入前端。

`TERM=xterm` 和 `xterm-256color` 在 Vim 及 tmux 内 Vim 的八个窗口均通过。Sixel 的绘制、重绘和擦除共八帧与原图逐像素一致。[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074)另有 ReGIS、宽字符边界、系统 terminfo 与部分 WSL1 路径的红项；本页不声明所有转义序列或 OSC 完全等同原版 XTerm。[协议覆盖表](../docs/PROTOCOL_COVERAGE.md)。

只改字号不改网格时，本轮托管 WSL1 客体的 `TIOCGWINSZ` 留在 640×480，实际终端文字区是 800×576。见[该作业的原始数据](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/artifacts/14640462871)。

[验收记录和原始制品标识](acceptance-28a2da26.zip)。 尚在运行：Windows x64 综合回归、隔离单文件回归。

原始响铃分组在[下载 EXE 时收到 HTTP 503](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/job/136370565120)，两个用例都没有运行。[同一 EXE 的独立补测](https://github.com/xiongnemo/nemoterm/actions/runs/44764046453)为 **2/2**：Windows 的 `MessageBeep` 返回成功，视觉响铃保存了三组闪烁和恢复画面。原始 77/81 保留。[全部 81 项的交互复跑](https://github.com/xiongnemo/nemoterm/actions/runs/44764982238)也使用同一份 EXE，单独报告。
