# Windows x64 试用版 bdf847f9：清历史时保留正确的 Shift 选区

[下载受测 Windows x64 单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44696025018/artifacts/14611150964)。解压后只需 `nemoterm.exe`，4,947,456 字节，SHA-256 `d6605d697e3084b080e68d7a7db8ea4cfcba392a627ea85e068028c25b30ab31`。

程序清除滚动历史时，已消失的行不再被误选；仍在当前屏幕的文字可以继续用 Ctrl+Shift+C 和右键复制。GDI 和 DirectX 各通过十个窗口，包括在鼠标仍按住时直接分派本地清历史命令，或在应用输出排队后松手。[两次回放、首轮超时和逐窗截图](selection-history-clear.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,776,512 | 22,736,896 | 4,456,448 |
| NemoTerm GDI，24 轮 Codex | 5,529,600 | 34,598,912 | 6,844,416 |
| NemoTerm DirectX，24 轮 Codex | 9,707,520 | 44,847,104 | 11,268,096 |
| NemoTerm GDI，六种满屏负载 | 18,653,184 | 53,280,768 | 22,081,536 |
| NemoTerm DirectX，六种满屏负载 | 29,274,112 | 74,616,832 | 33,144,832 |

[三组 24 轮 Codex 会话](https://github.com/xiongnemo/nemoterm/actions/runs/44696751640)均为 160×48、SarasaTermSC Nerd Light；全部自然退出，前端进程及模块检查未命中 WebView。六种满屏负载另行测试，按前端私有工作集验收。

[整组交互](https://github.com/xiongnemo/nemoterm/actions/runs/44696025018)验证 **80/81**：六项选区和绑定、九项标签交互和十项满屏 agent 检查均通过。Codex 正常编辑框的四次粘贴均在首次目标提交中收到一张像素正确的图片。四个提前发键的独立会话中，有 3 次收到正确图片、1 次只收到文字、0 次没有目标请求。首次手势失败仍保留原评分。[原始记录、内存采样与产物身份](acceptance-bdf847f9.zip)。

严格对照仍报告 [XTerm 宽字边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)、[ReGIS 横向编辑的中间画面](regis-horizontal.md)和 [WSL1 按行粘贴及退出](wsl-relay-window.md)差异。这是开发试用版。
