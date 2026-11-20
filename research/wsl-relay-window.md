# WSL1 实际窗口的逐字节粘贴

## 当前试用版 `b04ca12a`：窗口粘贴与 Linux 读取

同一份 [Windows 单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14662764153)（SHA-256 `ab0cba09fd6c33f3620fdf7e5ae92b49b60026b5376dfae8290171c5a84045cc`）使用 GDI、DirectX，各跑默认 `^V`、自定义 `^]` 两种引用符。每组实按 Ctrl+Shift+V，再键入回车和哨兵字符。下表按子程序实收字节及每次读取的边界计数。

| 实际子程序检查 | 默认 ConPTY | 配置方案中的 Linux PTY |
| --- | ---: | ---: |
| 普通原始粘贴与 XTerm 参考相同 | 4/4 | 4/4 |
| `?2005` 逐字节引用与 XTerm 参考相同 | 0/4 | 4/4 |
| `?2004;2005;2006` 组合与 XTerm 参考相同 | 0/4 | 4/4 |
| 按行读取时完整正文和哨兵都在 | 4/4 | 4/4 |
| 正文作为一整行、哨兵作为下一行读出 | 0/4 | 0/4 |

将 Linux 接收器每次 `read` 的原始字节拼起来，与仓库中固定 XTerm 412 参考的粘贴加回车和 `7` 直接比较：普通粘贴都是 21/21 字节；逐字节引用时默认路径是 35/40 字节，带包围标记时为 47/52。两个场景缺的是引用前缀；内嵌 PTY 分别是 40/40、52/52，内容也逐字节相同。

两条路径各 16 个模式查询均相符。WSL1 把正文拆开，加上哨兵共读五次；同样的 XTerm 原始字节直接写给没有 Nemoterm 的私有 PTY，WSL1 仍是五次、原生 Linux 是两次。[默认路径及 WSL1 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14662969051) · [内嵌 PTY 窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14662923176) · [原生 Linux 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14663052442)。原始严格检查仍失败。

**窗口退出单独计分。** 原内嵌 PTY 四组均正常退出前端、删除了临时 ELF，但在 2 秒期限之后仍有两个未识别的进程，继续观察 5 秒仍存活，夹具才终止该私有作业。[同次配置窗口及直接 WSL 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14663099424)能识别两个 `init`，包括未启动 Nemoterm 的 `/bin/true` 对照；这不证明粘贴作业中原来那两个 PID 就是 `init`。

[同一 EXE 与 Linux 接收器的独立回放](https://github.com/xiongnemo/nemoterm/actions/runs/44812462777/artifacts/14668372001)在相同的 2 秒期限内四组均自然结束、没有剩余进程。两组无窗口对照分别经过和绕过转接器，也都返回了正确正文并自然结束。这次只改了进程身份记录和超时后的观察期，没有改产品、字节判据或退出期限。**各组的原始粘贴字节仍完全相同，WSL1 的五次按行读取仍然失败。** 未复现首次退出超时，故保留两次结果；未确认其原因。[两次窗口回执、无窗口对照及原始制品散列](wsl-paste-b04ca12a.zip)。

## 较早的独立转接器对照

同一份 Windows 单 EXE `da3de317`（SHA-256 `a29758608b55f11eec245ce44e1ddc6ea53eb09142ef076413f263b8be3c776a`）分别走系统控制台和自有的 Linux PTY 转接器。两台托管 Windows runner 都运行 Ubuntu 24.04 WSL1，GDI、DirectX 各用默认 `^V`、自定义 `^]` 两种逐字节引用符。每次在实际终端窗口按 Ctrl+Shift+V，由 Linux 接收器读回数据。剪贴板包含中文、emoji、Tab 和多个换行。这里测的是文本协议，不是 Codex 图片附件。

| 独立断言 | 默认 ConPTY → `/dev/tty1` | 转接器 → `/dev/pts/0` |
| --- | ---: | ---: |
| 原始读取：普通粘贴 | 4/4 | 4/4 |
| 原始读取：XTerm `?2005` 逐字节引用 | 0/4 | 4/4 |
| 原始读取：`?2004;2005;2006` 组合 | 0/4 | 4/4 |
| 按行读取：拼接后得到正确内容 | 4/4 | 4/4 |
| 按行读取：Linux 分两次返回整行和哨兵 | 0/4 | 0/4 |

例如，`中` 的 UTF-8 为 `e4 b8 ad`。使用 `^V` 时，固定版本 XTerm 给出 `16 e4 16 b8 16 ad`。原通道收到 `16 e4 b8 ad`；新通道收到完整六字节。四个窗口均核对 Linux 接收器父进程与编译制品的散列，完成后自然退出。两组的终端模式回复均匹配。此对比使用独立的转接器制品；后续的内嵌副本需要自己的测试。

**WSL1 的按行读取仍不同。** 四组都把含内嵌换行的内容拆成五次读取（含单独的哨兵），而原生 Linux 在逐字节引用下只返回两次。单独向私有 PTY 写入固定 XTerm 原始数据，不经过任何 Windows 窗口，也能复现。两个窗口作业仍保留为失败，不重发文本、不合并分块伪造成功。[Windows GUI 与独立 Linux 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44615756739) · [原始制品和 GitHub 散列](wsl-relay-window-records.zip)。

## 关闭标签时的收尾

退出不仅取决于输出管道的 EOF。旧转接器在子程序停止读输入、父端不再读输出、以及子程序先关掉自己的终端但仍继续运行时，都可能等不到前端已关闭的通知。[旧代码](https://github.com/xiongnemo/nemoterm/actions/runs/44616128897)在原生 Linux 的三项均超过 4 秒，实际由夹具的兜底闹钟退出；WSL1 复现后两项，第一项的旧夹具未成功证明管道堵满。[首次修复](https://github.com/xiongnemo/nemoterm/actions/runs/44616204175)保留了 WSL1 的测量失败：`select` 报可写不等于还能写下一整帧。

[改为记录真正成功写入的帧后](https://github.com/xiongnemo/nemoterm/actions/runs/44616741427)，两台托管 runner 使用同一个 38,304 字节的静态 ELF（SHA-256 `8e292a12251c09a74349a17ab78b148ff7f819d2fa1dd19c48eb43279875a8fb`）。两端各通过 7 项字节/缩放/进程测试及 4 项关窗测试。堵满场景 Linux 接受 66 帧、WSL1 接受 68 帧，均发生连续超过 350 毫秒的写入停滞。三个异常关闭场景在 1.015–1.024 秒退出，子进程已回收；子程序只关闭终端、随后主动返回 37 时，仍得到 37。这里测试的是两端的真实管道关闭，不能单凭这条记录证明 Windows 用户实际点击标签时的临时文件回收。

## 首个内嵌版本 `73b8630d`

[Windows 单 EXE](https://github.com/xiongnemo/nemoterm/actions/runs/44617407295/artifacts/14575536516) 为 4,935,680 字节，SHA-256 `369e5a9b8e5fb8faee34be9a5b35304061350728a85a1996cd05c970c7591b62`。REA 的 PE 资源检查与文件字节对照均识别到 RCDATA 40003（38,304 字节），恰与同次 Linux 重建的 `8e292a12…` 转接器相同，RCDATA 40000 包含 musl 许可。

| 同一份 EXE 上的检查 | 实际结果 |
| --- | --- |
| 正常启动和结束 WSL 应用 | [Vim / tmux 内 Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44617938485/attempts/2) 共 8/8。每个窗口同时核对 GUI 临时文件与 Linux 父进程的路径和 SHA-256；退出后该文件均消失。覆盖普通点击、Shift 强制选区、矩形复制、实际 Ctrl+Shift+V、恢复备用屏幕，以及 Vim 确认 72×24、52×16 两次调整。GDI、DirectX 各覆盖 `xterm` 和 `xterm-256color`。第一次分派发生在源构建成功之前，被身份检查拒绝，没有启动 Vim。 |
| 对照 XTerm 与 WSL 按行读取 | 12/12 组原始字节正确。按行读取 1/4 组取得完整数据，仍返回五段；其余三组在最后的哨兵超时，并由测试作业强制清理。强杀 GUI 遗留的三个临时 ELF 在原始制品中保留，不能将它们记为正常关闭。 |
| 夹在两次粘贴之间的快速回车 | [单独的 Windows 复现](https://github.com/xiongnemo/nemoterm/actions/runs/44619482891)：一个独立剪贴板所有者收到取数请求后暂缓提供文字。真实键盘依次粘贴、按回车和 `7`、再次粘贴、按 `8`。GDI、DirectX 均在剪贴板仍未释放前就交付了回车和 `78`；随后才收到两份文本。它是前端按键排序问题，与 WSL1 的规范行边界分开处理。 |
| 160×48，SarasaTermSC Nerd Light，多轮 Codex | [相同 runner 的 24 轮会话](https://github.com/xiongnemo/nemoterm/actions/runs/44618243646)均正常退出。前端私有工作集峰值：pterm 3,768,320、GDI 5,550,080、DirectX 9,723,904 字节；总工作集分别为 22,667,264、34,603,008、44,785,664 字节。 |

[上述原始制品、散列与 PE 记录](wsl-bundled-73b8630d.zip)。这份 EXE 的行为不能代替后续排序修复的回放。
