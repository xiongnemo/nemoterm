# tmux 写剪贴板时，Vim 里的 Shift 选区会被覆盖吗？

不会。在当前 `bdf847f9` 试用版上，tmux 可以按 profile 的权限写 Windows 剪贴板；已经用 Shift 从屏幕上选中的文字仍然是独立的。默认右键和 Ctrl+Shift+C 都能把原选区重新复制到剪贴板。

[远程回放](https://github.com/xiongnemo/nemoterm/actions/runs/44700026729)使用同一个 Windows x64 单文件，SHA-256 `d6605d697e3084b080e68d7a7db8ea4cfcba392a627ea85e068028c25b30ab31`；在 GitHub 托管 WSL1 上启动真实 tmux 3.4 和 Vim，外层 `TERM=xterm-256color`、内层 `tmux-256color`，字体 SarasaTermSC Nerd Light。先让 Vim 接管鼠标，用实际 Shift 拖选 `中文`，再让已连接的 tmux 使用 `load-buffer -w` 写入另一段 Unicode。四个新进程分别使用两种渲染器和两种权限。

| profile | tmux 写入后 Windows 的内容 | 随后右键复制、再用快捷键复制 | tmux 自己的缓冲区 |
| --- | --- | --- | --- |
| 默认（允许写） | `tmux → 剪贴板 🍵`，剪贴板序号改变 | 两次都是 `中文` | 仍是 tmux 写入的文字 |
| 禁止应用用 OSC 52 写剪贴板 | 原来的哨兵文字，序号未变 | 两次都是 `中文` | 仍是 tmux 写入的文字 |

两个渲染器均符合上表，**4/4**。四份客户端输出各包含一个带正确载荷的 OSC 52，均位于 Vim 回显的后续标记之前；所以拒写的两个窗口不是因为 tmux 没发请求。分别对窗口像素取样，选中的两个汉字占四格，旁边两格未选；在 tmux 写入前后，包含这六格的截图区域逐像素相同。Vim 的光标、模式、缓冲区以及 tmux 未进入复制模式都由应用独立报告。

同一作业中的四个常规 Vim/tmux 用例也通过，包括调整窗口、矩形复制和保存粘贴后的文件。它们与新增四项分别计数；没有修改原来 80/81 的整组交互评分。这次不验证远程读取系统剪贴板。

[原始 GitHub 制品](https://github.com/xiongnemo/nemoterm/actions/runs/44700026729/artifacts/14612268541) · [完整原始 ZIP、GitHub 散列和独立像素／字节核对](tmux-clipboard.zip)。本次未改动 `dist/nemoterm.exe`。
