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

[隔离目录里的同一份 EXE](https://github.com/xiongnemo/nemoterm/actions/runs/44767889657)：交互后目录内仍只有 `nemoterm.exe`，大小、SHA-256 与源制品相同。使用 SarasaTermSC Nerd Light，Codex 确认就绪后，系统实按和窗口接口分别测试两种快捷键，**4/4** 首次提交含一张正确的 32×16 PNG，后续请求没有重复图片。早期观测分别为 api-immediate: 0/2, system-immediate: 1/2, system-caption: 1/2；没有将它们计入就绪结果。原始五份制品见证据包内 `isolated-paste.zip`。

[验收记录和原始制品标识](acceptance-28a2da26.zip)。 [Windows x64 测试与便携构建](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/job/136370287192)通过。隔离单文件作业未通过，两个作业分别计分。

原始响铃分组在[下载 EXE 时收到 HTTP 503](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/job/136370565120)，两个用例都没有运行。[同一 EXE 的独立补测](https://github.com/xiongnemo/nemoterm/actions/runs/44764046453)为 **2/2**：Windows 的 `MessageBeep` 返回成功，视觉响铃保存了三组闪烁和恢复画面。原始 77/81 保留。[全部 81 项的交互复跑](https://github.com/xiongnemo/nemoterm/actions/runs/44764982238)实际执行了全部 81 项，严格结果 **78/81**。两个 Codex 启动早期组各有一个快捷键在就绪前提交了纯文字；响铃两项通过。第三项是独立窗口设置超时，详见下文。

**设置窗口超时：** 切换到另一个 profile 并复制独立窗口后，测试发出 `WM_CLOSE`，未能在短时等待内观察到恢复为一个会话（原脚本第 757 行）。随后失败诊断也没有结束，外层 900 秒时仍记录了 5 个进程，最终由 Runner 清理。标签模式通过。这份记录不能确定关闭请求是否被成功投递、是否出现了确认框，也不能证明 UI 一直卡了 15 分钟。[原始设置制品](https://github.com/xiongnemo/nemoterm/actions/runs/44764982238/artifacts/14644109600)和[同 EXE 的设置专项诊断](https://github.com/xiongnemo/nemoterm/actions/runs/44769383351)分别保留。

设置专项复测 **2/2**。记录显示，独立窗口投递 `WM_CLOSE` 后 56 毫秒观察到只剩原会话；标签模式的新增和复制分别是 53 和 49 毫秒。三个句柄、会话号、操作前后列表和实际耗时均在证据包的 `settings-diagnostic` 中。未复现前一次关闭超时；原因未确定。

[隔离单文件原始作业](https://github.com/xiongnemo/nemoterm/actions/runs/44759373074/job/136370288813)明确记录了 150 个已通过的顶层检查；随后在标签页回归中止，本作业没有运行后面的 Codex 贴图。右侧标签栏、GDI、默认 profile 字体下，16 个矩形选区和 58 个窗口消息驱动的横向编辑用例均已完成。实按第十个横向编辑用例 `edge-right-ich` 时，两个鼠标模式的回复都正确，但等下一次终端状态回复超时，尚未执行该用例的选区像素和复制断言。收尾快照确实含同阶段的正确回复 `1b5b306e`；它在 8 秒判定前是否已对父进程可见，旧记录无法区分。原始输入、测试日志、最后快照以及制品摘要在证据包的 `single-exe-final/` 中。[同一 EXE 的选区专项](https://github.com/xiongnemo/nemoterm/actions/runs/44770876789)保留超时时松开鼠标之前的读数，另行计分。

同一 EXE 的右侧 GDI 选区专项通过：16 组矩形选区、58/58 个窗口消息横向编辑、15/15 个真实鼠标横向编辑。原先超时的用例按住鼠标时完成插入，选区像素为第 19–21 列（从零起算），右键和快捷键都复制出“中U”。原始专项制品在 `right-tab-replay/original.zip`。本次未复现超时，不替代原单文件作业未执行的后续检查。

另一次独立对照在字符移动后故意向同一窗口发送与按下位置完全相同的鼠标移动消息。旧 EXE 在普通 Shift 选区下在该具体路径超时：按住时发出的第二个状态请求未在 8 秒内收到回复，子程序回执中仍只有先前的 `1b5b306e`。该运行在这里停止，未测试后续矩形用例。此前自然发生的超时没有记录鼠标消息，不能认定两者原因相同。[旧 EXE 的对照运行](https://github.com/xiongnemo/nemoterm/actions/runs/44772466056) · [该运行未经改写的原始制品](stationary-before-28a2da26.zip)。
