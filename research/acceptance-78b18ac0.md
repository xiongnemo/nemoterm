# Windows x64 试用版 78b18ac0：矩形重绘时保住正确的选区起点

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44683142606/artifacts/14605202946)（4,931,584 字节），SHA-256：`680f8492c38f319418a41e3ef976b989e1d4fe75e026176b59c5f5161183b65e`。

在应用接管鼠标时按住 Shift 和左键，若原字被替换，此次拖选会取消，不再复制新的无关文字。原位置复制到别处、或用相同字符及重音重绘，仍可继续选。两种渲染器、新旧文件的同组回放从 **20/56 提高到 56/56**。[原始截图、剪贴板和子程序回执](selection-rectangle-redraw.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,784,704 | 22,675,456 | 4,468,736 |
| Nemoterm GDI，24 轮 Codex | 5,758,976 | 37,097,472 | 7,061,504 |
| Nemoterm DirectX，24 轮 Codex | 10,084,352 | 47,427,584 | 11,739,136 |
| Nemoterm GDI，六种满屏负载 | 19,685,376 | 55,988,224 | 22,503,424 |
| Nemoterm DirectX，六种满屏负载 | 28,659,712 | 71,925,760 | 32,452,608 |

[24 轮 Codex 会话](https://github.com/xiongnemo/nemoterm/actions/runs/44683657169)固定 160×48、SarasaTermSC Nerd Light。三组均正常退出，采样时未观察到 WebView 模块或进程。压力测试的每一栏取六种满屏负载的最高值，内存上限按前端私有工作集核对。

[本版交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44683142606)验证 **80/81**。仍未通过：`agent-image-codex`。就绪后四组位图均逐像素相符。启动早期窗口消息附图 0/2、实际系统按键附图 2/2；这个时点按首批字符回显识别，未保证编辑器就绪。鼠标按住时改变行宽的选择操作复核通过 34/34。另有十项满屏客户端交互、八个 WSL Vim/tmux 场景和两种渲染器的 WSL Sixel 通过。[交互和内存原始记录](acceptance-78b18ac0.zip)。

全量工作流的严格对照还报告[宽字符编辑边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)和 [WSL1](wsl-relay-window.md) 的差异。有关就绪前图片按键的语义，见 [pterm 与 Windows Terminal 的独立对照](codex-bitmap-requests.md)。
