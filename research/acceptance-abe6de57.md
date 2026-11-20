# Windows x64 试用版 `abe6de57`

[下载单文件制品](https://github.com/xiongnemo/nemoterm/actions/runs/44773123053/artifacts/14649155549)。解压后运行 `nemoterm.exe`。文件为 4,940,800 字节，SHA-256 为 `36d2434ea2645138eafc1ae54dbd4b48bb2ce82ef52a7f147ec261421ab8ff3d`。下面的结果均对应这份文件，实际窗口和进程采样来自 GitHub 托管 Runner。

- **鼠标拖选：** 修复了按住 Shift 和左键不动时，应用移动光标下的文字可能导致输出暂停的问题。右侧标签栏下，横向编辑的 60 个窗口消息用例和 15 个系统鼠标输入用例全部通过。[修复前后截图及原始回执](stationary-abe6de57.md)。
- **常用交互：** 在 Codex、Claude Code、OpenCode 中，GDI 和 DirectX 各测快捷键、默认右键复制、可选右键复制并粘贴，共 [18/18](https://github.com/xiongnemo/nemoterm/actions/runs/44776353666)。每次都在应用已接管鼠标时拖选，核对高亮、剪贴板及实际提交的文本。两个渲染器共 10 个默认网格客户端窗口通过；中英文各 12 个实际 DPI 场景通过。
- **Codex 贴图：** 编辑器就绪后，Ctrl+V 和 Ctrl+Shift+V 分别通过系统实按和窗口消息验证：4/4 次在首条请求中附上正确的 PNG，后续没有重复。提前按键的四次中三次成功，另一次窗口消息 Ctrl+V 只提交了文字。原始失败记录保留，不保证就绪前接收图片。

| 160×48，24 轮真实 Codex 会话 | 前端私有工作集峰值 | 前端总工作集峰值 | 前端私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm | 3.78 MB | 22.75 MB | 4.46 MB |
| Nemoterm GDI | 5.83 MB | 37.21 MB | 7.34 MB |
| Nemoterm DirectX | 10.04 MB | 47.38 MB | 11.64 MB |

六种满屏负载下，GDI 私有工作集峰值为 **18,808,832 字节（18.81 MB）**，DirectX 为 **29,515,776 字节（29.52 MB）**，均在本项目的 20 / 30 MB 限额内。MB 按十进制计算。[交互汇总](https://github.com/xiongnemo/nemoterm/actions/runs/44773123053/artifacts/14648894544)为 **80/81**；全部已执行，唯一红项是上述 Codex 就绪前用例。[取证包](acceptance-abe6de57.zip)内有对话内存的原始 Actions 制品、18 项绑定的独立回放结果、10 个窗口的观测记录，以及 Codex 就绪前后的原始 JSON。

[完整回归的实时状态](https://github.com/xiongnemo/nemoterm/actions/runs/44773123053)。本版供试用；ReGIS 重绘、宽字符恰在行末时的处理、发行版 terminfo 的 Backspace 行为及部分 WSL1 路径仍有未通过项。[协议差异与覆盖范围](../docs/PROTOCOL_COVERAGE.md) · [上一份分发版](acceptance-03d0e0bc.md)。
