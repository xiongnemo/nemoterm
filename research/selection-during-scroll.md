# 先按鼠标、应用滚屏、再完成选区

终端程序接管鼠标时，按住 Shift 从 `A中é` 的 `A` 起选，在第一次移动鼠标前让程序把内容向下滚动一行，再拖到组合附标所在字格并松开。旧版的普通选择会多复制 `bove|\r\n#`，矩形选择会多复制 `bove\r\n`。截图中的高亮也确实越过了目标行。向上滚动的原始对照没有这一问题。

| GitHub Windows Runner | 修复前 `2ca68df` | 修复后 `6f8d382` |
|---|---|---|
| GDI 原始窗口 | [含上方的 `above` 行](pressed-scroll-before-2ca68df.png) | [只高亮目标行的四个字格](pressed-scroll-after-6f8d382.png) |
| GDI / DirectX × Sarasa / 默认 Profile 字体，普通与矩形选择 | [首轮](selection-pressed-before-2ca68df.zip)：向下 0/8，向上 8/8 | [隔开独立点击后的精确镜像回放](selection-pressed-replay-6f8d382.zip)：向下 8/8，向上 8/8 |

修复只在第一次拖动之前、被按住的行仍留在滚动区域内时同步向下移动选区起点。四个窗口均先按七个字格的实际像素确认行已移动，再比较松开后的高亮范围、系统剪贴板的完整文字（`e` 后仍是 U+0301）、子程序输入（只有两个状态应答，没有鼠标字节）。[远程回放](https://github.com/xiongnemo/nemoterm/actions/runs/44468813609)的完整选区组为 6/6。此结论不覆盖被滚动丢弃的行。

[修复后首轮原始回执](selection-pressed-after-6f8d382.zip)也保留：向下 8/8；向上在三个窗口等不到终端应答。首轮把连续的独立点击发往同一屏幕位置，可能被解释成三击而开始行选择。回放将相邻用例的点击分到不同的行；没有重发、延长时限或改动 EXE。最初直接从新源码回放旧镜像的[请求](https://github.com/xiongnemo/nemoterm/actions/runs/44468817087)被源码校验拒绝，没有启动受测程序；旧版使用[对应源码回放](https://github.com/xiongnemo/nemoterm/actions/runs/44469287310)。

`6f8d382` 镜像 SHA-256 为 `55d56d8ab68191fa724e73210b4d55c0cca5eed0ceedb97a0026a2fa49a3129d`。[同机 pterm 对照](pterm-selection-memory-6f8d382.zip)包含独立记录的 10 次 Codex 冷启动，仅适用于该镜像。上述单项通过不等于完整 CI 已通过。

相同单击脚本的[旧产品对照](selection-pressed-control-2ca68df.zip)再次得到向下 0/8、向上 8/8；新构建 `810a26f` 的[选区原始记录](selection-pressed-810a26f.zip)为向下 8/8、向上 8/8，组内全部 6 项通过。`810a26f` 实际 EXE 为 4,871,168 字节，SHA-256 `24deed2cdaa8a3743793c014048ce057333c7f9bc77c4b59de545e5b7bbd27d3`，制品 `14503279012`。该结果来自此构建本身。
