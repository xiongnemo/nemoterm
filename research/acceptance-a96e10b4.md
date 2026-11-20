# Windows x64 试用版 a96e10b4：中键关闭标签

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44661690615/artifacts/14595528446)（4,945,408 字节），SHA-256：`01bac7bd4d51b7692d2a34086bd9b5e6d068ab6ebe3bb5efdfe3981043e6b9c6`。

在 A 标签按住中键、到 B 才松手，现在两个标签都会保留；即使按住期间 A 自行退出也不会把 B 一起关掉。四种位置下的五种手势共 **20/20**，旧版 **4/20**。同时验证了四个方向的悬停画面更新、键盘路由和 Shift 拖选复制。[两版原始窗口记录](tab-middle-gestures.md)。

| 同机前端测试（字节） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm，24 轮 Codex | 3,768,320 | 22,679,552 | 4,452,352 |
| GDI，24 轮 Codex | 5,795,840 | 37,138,432 | 7,213,056 |
| DirectX，24 轮 Codex | 9,936,896 | 47,271,936 | 11,522,048 |
| GDI，六种满屏负载 | 19,230,720 | 56,111,104 | 22,491,136 |
| DirectX，六种满屏负载 | 28,950,528 | 72,081,408 | 32,972,800 |

[多轮固定版本 Codex 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44662333039)使用 160×48、SarasaTermSC Nerd Light；三组均自然退出，所观察模块和进程未发现 WebView。REA 静态检查确认此 EXE 为 x64 PE，没有 CLR 目录。

[81 项远程交互](https://github.com/xiongnemo/nemoterm/actions/runs/44661690615)通过 79/81。Codex 启动早期的两项图片手势仍失败，正式输入框就绪后，两种按键和两种投递路径都收到一张像素正确的图片。十项满屏 agent 交互通过；真实 Vim 与 tmux 中的 Vim 在 GDI、DirectX、两种 TERM 下 8/8，Sixel 两种渲染器各通过四个阶段。[可复核的记录及制品身份](acceptance-a96e10b4.zip)。

这一版的 MSVC 诊断制品在标签切换中 8 次正常退出，实际是 GDI 回退；这没有确定此前偶发崩溃的原因。ReGIS 历史重绘、XTerm 412 的三处行尾格、WSL1 按行粘贴及退出等待仍有独立失败，不能把本版记为全绿。
