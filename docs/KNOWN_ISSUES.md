# v0 已知问题与使用限制

适用于 Windows x64 单文件 `7faa7fac`（[下载与构建记录](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14677562291)）。下面列的是这份 EXE 在 GitHub 托管 runner 上的结果。普通 shell 或其他 WSL 版本不一定会遇到相同问题。

## 已知兼容问题

| 场景 | 会看到什么 | 使用建议与证据 |
| --- | --- | --- |
| ReGIS 图形和文字在同一区域内滚动、插删 | 部分画面与 XTerm 412 不同。例如在红线上删除字符，两端重绘前的红线不同；这一组横向编辑在重绘后相同。其他擦除和滚动场景仍有差异。 | 对依赖 ReGIS 逐帧显示的应用，不要假设画面与 XTerm 完全相同。[GDI 原始画面](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14676732209) · [DirectX 原始画面](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14677772860) · [横向编辑图解](../research/regis-horizontal.md) |
| WSL1 中，应用开启逐字节引用粘贴（`?2005`） | 默认 ConPTY 路径可能漏掉多字节字符的引用前缀。即使原始字节完整，WSL1 也可能把带换行的内容分成多次按行读取。 | 「配置方案 → Shell → x64 WSL 会话使用 Linux PTY」可以改善原始字节传输；对按行拆分没有同样效果。这与平时粘贴单行命令不同。[窗口实测](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/job/136623650218) · [绕过终端的对照](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/job/136623650232) |
| WSL1 应用按像素查询窗口大小 | 应用通过 `TIOCGWINSZ` 可得到字符行列，但像素宽高可能是 `0×0`。依赖它为 Sixel 图片计算显示尺寸的程序可能选错大小。 | 若应用提供按字符数或显式像素尺寸显示的选项，可避开这次查询。[本版窗口及 PTY 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/job/136623650302) |
| 关闭 WSL1 Bash 会话 | 默认、启用及禁用 Linux PTY 的三个用例中，退出后的清理都未在检查期限内完成。这条失败发生在退出阶段，不表示设置未保存，也不足以证明进程永久残留。 | [本版退出检查及日志](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/job/136623650043) |
| 与 Linux XTerm 412 对照退格键 | 显式选择 Terminfo 键盘，而两端的 terminfo 数据库不同时，Backspace 在某些模式下发送 `08`（BS）或 `7F`（DEL）的结果不同。 | 要逐字节对照，请使用同一份数据库。[两份数据库及四种配置的原始结果](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14676562505) |
| 在行尾宽字旁删除字符、删除列或左移 | 区域右端的 `中V` 左移后，Nemoterm 保留 `V`，XTerm 412 在特定布局下会将它清空。这是有意保留完整字符的差异。 | 早先「在行末插入一个汉字，下一行的首字消失」是另一处缺陷，**本版已修复**。[逐格原始记录](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14676459213) · [两个场景的对照](../research/column-edge-integrity.md) |

## Codex 刚启动时贴图

Codex 0.167.0 刚出现文字提示时，图片输入可能还没就绪，第一次粘贴不一定生成附件。等编辑器就绪再粘贴，看到附件后即可发送，不必先发文字。本版在编辑器就绪后，两组贴图测试都通过；两组提前粘贴的失败也保留在[原始交互结果](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14678590150)。[原版 pterm 和 Windows Terminal 的对照](../research/codex-bitmap-requests.md)也观察到这个时序差异。它属于客户端启动限制，不作为 v0 阻塞项。

## v0 的验收边界

- **协议范围：** 可以运行声明 `TERM=xterm` 或 `xterm-256color` 的应用，不承诺与 XTerm 412 的所有私有序列和行为逐项相同。Kitty 图片的文件和共享内存传输、Kitty 动画，以及 OSC 633 的补全扩展尚未实现。[协议支持表](PROTOCOLS.md)按功能列出已实现和缺失项。
- **窗口交互：** 本版在 Codex、Claude Code、OpenCode 的十个真实窗口中用 Sarasa Light 测了 GDI 和 DirectX 的中文矩形选区，截图和系统剪贴板均符合预期。[交互回执与窗口原图](../research/column-edge-integrity.md#行尾输入一个汉字时下一行的第一个字消失)。
- **内存口径：** 比较前端进程的私有工作集，GDI 要低于 20 MB，DirectX 不超过 30 MB，1 MB = 1,000,000 字节。本版 [24 轮 Codex 对话](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247/artifacts/14678240461)的采样峰值为 GDI **5,767,168 字节**、DirectX **10,027,008 字节**。六种满屏压力用例需单独看[同一份 EXE 的完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44832796247)，不能用对话采样或旧版成绩替代。
