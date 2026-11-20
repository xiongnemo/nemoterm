# Windows x64 试用版 9521179a：编辑选框旁的内容后仍能复制

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44714993575/artifacts/14619940872)，解压后运行 `nemoterm.exe`（4,933,120 字节）。SHA-256：`ee317bc6b8218f6e4dfbe376cda6076b583fc835c6fdbb8d3697f492a0d97224`。

用 Ctrl+Shift+鼠标左键框选多行文字后，子程序仅在选框旁边插入或删除字符，高亮和复制现在会保留。如果编辑切开宽字符或移动了框内的一行，选区取消，下一次右键由应用处理。旧版默认右键在 GDI、DirectX 各通过 6/14，新版各 **14/14**；另各有四次快捷键复制和六次可选右键粘贴通过。[原始截图、剪贴板和子程序字节](rectangle-neighbour-edits.md)。

[整组交互](https://github.com/xiongnemo/nemoterm/actions/runs/44714993575)在同一 EXE 上通过 **79/81**，包括选区和绑定 6/6、全屏客户端 10/10、标签 9/9。两种渲染器下的真实 Codex、Claude Code、OpenCode 在程序接管鼠标时都能用 Shift 从宽字的半格开始拖选，并用 Ctrl+Shift+C 复制 `中文`。[十次实按与原始窗口制品](https://github.com/xiongnemo/nemoterm/actions/runs/44714993575/artifacts/14620100425) · [实际像素裁图](agent-wide-9521179a.png)。

在正式输入框里贴图，4/4 次首次目标请求各带一张像素正确的图片。刚看到输入文字就贴的四次，正确图片 0 次、只有文字 4 次、未收到目标请求 0 次。保留启动阶段的原分数；[pterm、Windows Terminal 的对照](codex-bitmap-requests.md)也区分首次回显和编辑器就绪。

| 前端（字节） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm，24 轮 Codex | 3,776,512 | 22,675,456 | 4,456,448 |
| NemoTerm GDI，24 轮 Codex | 5,488,640 | 34,545,664 | 6,799,360 |
| NemoTerm DirectX，24 轮 Codex | 9,732,096 | 44,818,432 | 11,272,192 |
| NemoTerm GDI，六种满屏负载 | 19,124,224 | 55,762,944 | 22,876,160 |
| NemoTerm DirectX，六种满屏负载 | 29,171,712 | 74,502,144 | 32,669,696 |

[同机 24 轮会话](https://github.com/xiongnemo/nemoterm/actions/runs/44715873926)使用 160×48、SarasaTermSC Nerd Light。三次会话均自然退出，采集的前端模块与进程中没有发现 WebView。另按六种满屏文字和图形负载核对原始采样，GDI 和 DirectX 各通过六项。工作集只计前端，不包括独立的 shell、控制台宿主或客户端进程。

对于 `TERM=xterm` 和 `TERM=xterm-256color`，真实 Vim、tmux 内的 Vim 在 GDI 和 DirectX 上共完成 8/8 个窗口场景，包括调整窗口和跨两行框选，剪贴板都是 `中文`、换行、`CU`。另有四个 tmux OSC 52 允许或拒绝的窗口场景完成。

WSL 中输出的 Sixel 五色测试图（24×18 像素）在 GDI 和 DirectX 窗口中各验证了绘制前、绘制后、强制重绘及擦除四个阶段。将原始 PNG 的检查区域与独立解码结果逐像素比较，8/8 阶段相符。[两组原始窗口与 WSL1 尺寸记录](https://github.com/xiongnemo/nemoterm/actions/runs/44714993575/artifacts/14619946262)。

这是开发试用版。单文件来自成功的 source-host 构建；发布这份实测记录时，独立单文件套件及 MinGW 便携构建的长期回归尚在运行。完整 CI 的严格参考对照仍报告差异，包括 [XTerm 宽字边界](column-edge-integrity.md)、[ReGIS 中间画面](regis-horizontal.md)和 [WSL1 的终端读取](wsl-relay-window.md)。[本版已核对的原始回执和制品身份](acceptance-9521179a.zip)。
