# Windows x64 试用版 10f0390f：Windows 程序读回横向编辑后的完整字符

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44655885414/artifacts/14592374771)。nemoterm.exe，4,944,896 字节，SHA-256：e35463f852bb79b7f72f9b61ee620f2fcaf7f2378564c238bcd0d45369e8a3d6。

向右插入一格、把贴着右边界的汉字挤出后，Windows 程序不会再把边界外的 W 读成汉字的后半格。应用将一块文字向左或向右滚动时，它通过控制台 API 读到的文字也会随之移动。GDI 和 DirectX 各通过 120/120 组，核对了两端的每个字格；行尾的 12 项实际与窗口消息拖选也全部通过。[修复前后原始记录与截图](column-edge-integrity.md)。既有 XTerm 412 三格差异仍在独立的严格回放中。

| 同机负载／前端 | 私有工作集峰值（字节） | 总工作集峰值（字节） | 私有提交峰值（字节） |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,764,224 | 22,671,360 | 4,452,352 |
| Nemoterm GDI，24 轮 Codex | 5,787,648 | 37,113,856 | 7,139,328 |
| Nemoterm DirectX，24 轮 Codex | 9,981,952 | 47,296,512 | 11,603,968 |
| Nemoterm GDI，六种满屏负载 | 19,337,216 | 56,274,944 | 22,888,448 |
| Nemoterm DirectX，六种满屏负载 | 28,962,816 | 74,285,056 | 33,243,136 |

SarasaTermSC Nerd Light，160×48，每列分别取前端峰值。24 轮会话中三种前端均自然退出，受检的已加载模块与进程未发现 WebView；REA 将这一份 EXE 确认为 x86-64 原生 PE，没有 CLR 目录。

[远程交互回执](https://github.com/xiongnemo/nemoterm/actions/runs/44655885414) **79/81**。两项未过的都是 Codex 输入框就绪前粘贴图片；就绪后，两种快捷键分别经窗口消息和实际键盘发送，四种组合都在请求中收到了像素正确的图片。Codex、OpenCode、Claude 的十项满屏交互也均通过。见[原始记录](acceptance-10f0390f.zip)。另行验证了真实 Vim、tmux 中的 Vim，在两种渲染器与两种 TERM 下共 8/8；Sixel 两种渲染器各四个阶段都与参考像素一致。[已知的 ReGIS 历史重绘](regis-presented-pairs.md)与 [WSL1 按行输入差异](wsl-relay-window.md)继续单独跟踪。

同一轮 CI 的独立 MSVC 渲染诊断还发生了一次设置为 OpenGL、实际回退到 GDI 的标签切换崩溃：三次正常，第四次移走悬停观察器、要切回第一个标签时进程以 `0xC0000005` 退出。未取得异常堆栈，不能由这一行确定原因。前三次和故障那次的 `actual_renderer` 都是 1（GDI）。发生崩溃的是诊断制品 `19701b51…`，与下载的单 EXE `e35463f8…` 不同。原始四次记录已保存在上述压缩包；[同一诊断制品的异常记录回放](https://github.com/xiongnemo/nemoterm/actions/runs/44658953357)。[首次分派](https://github.com/xiongnemo/nemoterm/actions/runs/44658731039)同时选择了互斥的观察模式，夹具在启动受测程序之前拒绝了参数；不计为一次复测。

异常观察器复测的 12/12 轮使用同一故障诊断 EXE 和右侧标签栏，全部正常退出（退出码 0），也都记录为 GDI 回退。它们没有捕获原异常，不能当作 OpenGL 硬件路径通过或崩溃已修复。
