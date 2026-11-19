# 按住鼠标时，应用在同一行插入或删除字符

按住 Shift，在 `K` 上按下鼠标左键。此时应用在它左侧插入两格，再把鼠标拖到 `M` 松开：应高亮并复制 `KLM`。旧版 `bec4002` 仍从屏幕原来的位置开始，复制成 `IJKLM`。如果应用删掉的恰好是按住的字，旧版还会复制补到那个位置的文字。

![同一段 GDI 选区，旧版多选了 IJ，新版高亮 KLM](selection-column-insert.png)

`b7bf0fd` 跟踪被按住的字。字移动时，它仍是选区的起点；字被删除、挤出边界或宽字被截断时，松手不会选中补位的字。应用开启鼠标跟踪时，取消这次选择后的下一个右键仍能回到应用。这个修改不增加每格或每个窗口的持久存储。

| 同一套 Windows 桌面交互 | `bec4002` | `b7bf0fd` |
| --- | ---: | ---: |
| GDI / DirectX × Sarasa / profile 默认字体，每种 15 项窗口消息 | 8/60 | 60/60 |
| GitHub Windows 桌面实际键鼠输入，每种渲染器 3 项 | 0/6 | 6/6 |

测试同时核对高亮像素、右键与快捷键复制的文本、以及应用收到的原始鼠标字节。覆盖普通和矩形选区、插入模式、横向滚动、组合字符、双宽字和双向文本。表内是新增的 66 项断言组合，不是整个项目的通过率。[旧版原始截图与回执](selection-column-before-bec4002.zip) · [新版原始截图与回执](selection-column-after-b7bf0fd.zip)。新版与旧版分别取自 [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44496986357) 与 [同一测试在旧 EXE 上的回放](https://github.com/xiongnemo/nemoterm/actions/runs/44496779434)。

这次还在同一 EXE 上复查了两个界面问题。[关闭确认记录](https://github.com/xiongnemo/nemoterm/actions/runs/44496986357/artifacts/14516256579)里，关闭标签会话、标签窗口或独立窗口，点击“取消”或按 Esc 后都能立即向原来的子进程输入，无需再点窗口。[DPI 截图与控件记录](https://github.com/xiongnemo/nemoterm/actions/runs/44496986357/artifacts/14516785258)覆盖中英文、独立及标签窗口、100/125/150/175/200% 的冷启动和运行中缩放；英文 100% 时，Sixel 和 ReGIS 的复选框说明均完整显示为两行。这是单显示器数据，多显示器之间的移动未测。[本地留存的两张截图、关闭输入和 DPI 读数](selection-ui-b7bf0fd.zip)。

另一个测试只比较字符内容：同一份输入分别送入独立构建的 XTerm 412 和两个 Windows EXE，在 28 个场景中每次查询 26 个单元格；不借用 XTerm 的鼠标策略判断 Windows 选择是否正确。旧版匹配 **724/728** 个单元格，新版 **725/728**。修复的是插入字符时边界留下半个 `中` 的情况。剩下三个差异均为同一位置：`DCH`、`DECDC` 或 `SL` 向左移动两格后，第 20 列在 XTerm 是空格 (`0x20`)，Nemoterm 是 `V` (`0x56`)。两版都如此，这三项对照仍判为失败。

[独立 XTerm 原始应答](selection-column-xterm.zip) · [旧 EXE 对照](column-cells-bec4002.zip) · [新 EXE 对照](column-cells-b7bf0fd.zip)。新版 EXE 为 4,856,320 字节，SHA-256 `30de4cef81033fb47cc1dffce629bf7cfa22542f53dd5d158874efe51b6c44e9`；旧版为 4,872,192 字节，SHA-256 `9f43a0ddc23219f3ac3974fee73b3b6f8de8f45c63adf3e668d7eef99984275e`。

完整交互回归与本节的定向检查使用同一个 EXE。[Actions 汇总、13 份分组回执与内存原始制品](selection-aggregate-b7bf0fd.zip)共 80 项，78 项通过；失败的是 `agent-image-codex` 和 `agent-image-system-codex`（客户端启动即贴纯位图）。GDI、DirectX 各 6/6 压力负载通过，前端私有工作集峰值分别为 **19,120,128** 与 **28,880,896** 字节。完整 CI 里的三个 ReGIS 核心历史画面对照作业仍失败；它们独立于 80 项交互用例。

[独立的 pterm / Nemoterm 同机对照](https://github.com/xiongnemo/nemoterm/actions/runs/44500659510)使用 160×48、SarasaTermSC Nerd Light 和同一个 Codex。五种配置按正反顺序启动，共 10/10 成功。首个回环回复显示后，pterm 两轮的前端私有工作集中位数为 3,780,608 / 3,747,840 字节；单标签 GDI 为 5,111,808 / 5,111,808，单标签 DirectX 为 9,695,232 / 9,732,096。此口径不包含客户端和控制台子进程。[未改动的完整制品](selection-pterm-b7bf0fd.zip)。
