# Windows x64 试用版 226ddd98：程序调整窗口后仍可复制原选区

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44687000276/artifacts/14606599292)（4,947,456 字节），SHA-256：`bd8cf49fe772b29d9a22789c330ce57693d3a088e192532225af4d2f5f09e934`。在应用已接管鼠标时用 Shift 选中 `A中Z`，即使应用再次请求当前行数、或者 profile 禁止应用改窗口大小，也能继续用 Ctrl+Shift+C 或默认右键复制。[GDI、DirectX 的实际窗口前后对照：4/28 → 28/28](selection-page-size.md)。同一 EXE 还通过了此前的 56 项矩形重绘和 34 项按住鼠标时改变行宽的检查。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,809,280 | 22,736,896 | 4,501,504 |
| Nemoterm GDI，24 轮 Codex | 5,697,536 | 37,023,744 | 7,127,040 |
| Nemoterm DirectX，24 轮 Codex | 9,990,144 | 47,304,704 | 11,587,584 |
| Nemoterm GDI，六种满屏负载 | 19,562,496 | 54,067,200 | 22,933,504 |
| Nemoterm DirectX，六种满屏负载 | 29,089,792 | 74,002,432 | 32,796,672 |

[24 轮 Codex 会话](https://github.com/xiongnemo/nemoterm/actions/runs/44687813544)均使用 160×48 和 SarasaTermSC Nerd Light，三组自然退出，采样时未观察到 WebView 模块或进程。六种满屏负载按每列各取最高值；上限按前端私有工作集计算。

[81 项交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44687000276)验证 **80/81**。Codex 正常输入框里的四次粘贴都提交了一张像素正确的图片。启动早期的实际键盘两次均提交了图片；窗口消息 Ctrl+V 提交了图片，Ctrl+Shift+V 在看不到附件后停在回车之前，没有目标请求，不能判为提交了纯文字。十项满屏 agent 交互、八个默认 WSL Vim/tmux 窗口、两种渲染器的 WSL Sixel 均通过。[同一 EXE 的原始交互、内存和协议记录](acceptance-226ddd98.zip)。

整套 CI 仍有严格对照失败：[宽字边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)与 [WSL1 按行粘贴](wsl-relay-window.md)。WSL profile 的三次 WSL 窗口运行均返回 0、临时 ELF 均被清理，但其子进程没有在四秒内全部消失；没有 Nemoterm 的两个 WSL 控制也超过了四秒。不能将这些结果记为全量通过。
