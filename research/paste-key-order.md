# 粘贴后立即按回车：`fc769def` 的同文件回放

[Windows x64 单 EXE](https://github.com/xiongnemo/nemoterm/actions/runs/44619850611/artifacts/14576329075)：4,937,728 字节，SHA-256 `03bd5cb5be895898df77e397df49ec4de702f284a8c667f59b1a4adb816d0575`。以下测试均在 GitHub 托管 runner 上完成。[本版的原始制品、生产与夹具身份和散列](paste-key-order-fc769def.zip)。

**触发方式。** Windows 上由其他程序延迟提供剪贴板文字时，按「粘贴、回车、7、粘贴、8」。[旧版回执](wsl-bundled-73b8630d.zip)显示，GDI、DirectX 都先送出了回车和 `78`，然后才交付两份文本。问题在真实 WSL1 回放中首先出现，独立的 Windows 接收器也能稳定复现。

现在每个窗口按发起顺序处理系统剪贴板读取以及随后发给应用的按键。读取仍在后台；渲染、窗口消息和终端查询可以继续处理。输入队列仅在等待粘贴时存在，有大小和时限；会话关闭或重启时撤销旧请求。此行为不探测 Codex 输入框、不自动补发图片。

| 检查 | 同一 EXE 的结果 |
| --- | --- |
| 延迟读取文字后快速回车、再次粘贴 | GDI、DirectX 两台 runner 的原生接收器，在所有者放行前均未得到后续按键；放行后顺序均为「文本、回车、7、文本、8」。窗口在等待时能响应消息。[完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44619850611) 与[独立回放](https://github.com/xiongnemo/nemoterm/actions/runs/44620574928)均通过。 |
| 所有者不返回，但用户继续输入 | 实测分别在 5.032 秒（GDI）、5.047 秒（DirectX）放行回车和 `7`；随后释放剪贴板、按 `9`，接收器只有回车、`79`，没有迟到的文本。 |
| 内嵌 WSL PTY 的真实窗口 | 两种渲染器、两种引用字符的 12/12 组原始字节匹配 XTerm；四次规范行测试都完整接收文本和哨兵、自然退出、删除临时 ELF，未再出现按键跑到文本前面。**规范行测试仍是 0/4**：WSL1 内核返回五段而非预期的两段。同一文件的默认 ConPTY 对照为原始字节 4/12。详见[逐层对照](wsl-relay-window.md)。 |
| 鼠标、选区、窗口缩放 | 真实 WSL Vim / tmux 内 Vim 的 8 个场景都核对了实际 Linux 父进程和清理。GDI 与 DirectX 的普通点击、Shift 强制选区、矩形复制、粘贴保存、72×24 和 52×16 两次缩放均通过。另有真实 Codex、Claude、OpenCode 满屏选区等 10/10 项通过。 |

以上只证明列出的操作；完整交互汇总、满屏内存与 XTerm 其他协议各自验收，不计入本表。
