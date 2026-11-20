# Windows x64 试用版 `8f375f7d`：应用恢复列宽后，窗口与原生程序都保留正确的文字

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44651165951/artifacts/14591596296)：`nemoterm.exe`，4,928,000 字节，SHA-256 `1a4052ce02d121e831706499a9c4d331f4716e61e3ef6a6d1c19d6e225db8ea9`。

在 GDI 和 DirectX 上，[同一组列宽恢复检查](column-modes.md)各从 53/68 提升到 68/68。51 项回答与真实 XTerm 412 逐字节比较，17 项验证本地禁止程序改宽；每项均检查 Windows 子程序读回的文字、尺寸和光标。应用已接管鼠标时，实际按 Shift 拖选 `A中Z`，恢复宽度后可以用 Ctrl+Shift+C 复制。明确清屏时高亮消失。[窗口截图和原始失败、成功记录](column-saved-readback.zip)。

| 同机负载／前端 | 私有工作集峰值（字节） | 总工作集峰值（字节） | 私有提交峰值（字节） |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,796,992 | 22,757,376 | 4,468,736 |
| Nemoterm GDI，24 轮 Codex | 5,464,064 | 34,496,512 | 6,819,840 |
| Nemoterm DirectX，24 轮 Codex | 9,662,464 | 44,716,032 | 11,165,696 |
| Nemoterm GDI，六种满屏负载 | 19,734,528 | 56,647,680 | 22,773,760 |
| Nemoterm DirectX，六种满屏负载 | 29,200,384 | 74,403,840 | 32,890,880 |

统计的是前端，未把 shell、内置控制台和客户端合并；每个指标分别取峰值。两组都使用 160×48 及 SarasaTermSC Nerd Light。[同机 24 轮实测](https://github.com/xiongnemo/nemoterm/actions/runs/44651890203)使用的官方 pterm 与开发电脑安装的 0.85 散列一致。三组会话均自然退出，采集的进程与已加载模块没有匹配到受检 WebView 组件。REA 静态确认本预览是 x86-64 原生 PE，没有 CLR 目录；81 个普通导入 DLL、680 个函数，一个延迟加载的 ICU DLL（11 个函数）。相对上一版，新增的静态导入只有 `IsProcessorFeaturePresent`。导入表不能排除运行时动态加载。

[同一份 EXE 的交互](https://github.com/xiongnemo/nemoterm/actions/runs/44651165951) **79/81**。未过的是 Codex 启动早期的两组：窗口消息的 Ctrl+V 与 Ctrl+Shift+V，以及实际键盘的 Ctrl+V，没有收到图片；实际键盘 Ctrl+Shift+V 收到一张。输入框就绪之后，两种按键途径各试两种绑定，四次都在请求中收到了像素正确的图片。Codex、OpenCode 和 Claude 的十项满屏交互全部通过。两种渲染器各完成六种满屏负载。另在托管 WSL 上测试了真实 Vim 和 tmux 内 Vim：每种渲染器用 `TERM=xterm` 与 `TERM=xterm-256color`，共 8/8 个窗口，覆盖实际鼠标、矩形复制、粘贴和改窗。两端的 Sixel 绘制、重绘和擦除亦通过此次像素对照。

[原始交互、内存与 REA 记录](acceptance-8f375f7d.zip)内的 `sources.json` 列出远程制品 ID、下载包散列和保存的成员。全量工作流仍有独立失败，包括 [ReGIS 历史重绘](regis-presented-pairs.md)、[三格宽字差异](column-edge-integrity.md)和 [WSL1 按行粘贴](wsl-relay-window.md)、[退出期限](wsl-profile.md)。
