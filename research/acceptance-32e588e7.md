# Windows x64 试用版 `32e588e7`：让窗口和 Windows 子程序看到同样的列宽和文字

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44646064546/artifacts/14588991439)：`nemoterm.exe`，4,942,336 字节，SHA-256 `81542ed8bf334eb2804894ee59e02ff31a76ef4d79f5bbdf560f0b914ca2dd65`。应用请求 80／132 列时，可见窗口与原生控制台都会服从当前标签的 profile；允许换宽并要求保留时，程序读回的字和可复制的选区都能保留。[修复前后和原始记录](column-modes.md)。

| 同机负载／前端 | 私有工作集峰值（字节） | 总工作集峰值（字节） | 私有提交峰值（字节） |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,768,320 | 22,671,360 | 4,460,544 |
| Nemoterm GDI，24 轮 Codex | 5,488,640 | 34,508,800 | 6,815,744 |
| Nemoterm DirectX，24 轮 Codex | 9,682,944 | 44,769,280 | 11,206,656 |
| Nemoterm GDI，六种满屏负载 | 19,075,072 | 53,805,056 | 22,392,832 |
| Nemoterm DirectX，六种满屏负载 | 28,835,840 | 71,589,888 | 32,321,536 |

同一行各指标独立取峰值，统计前端，不把 shell、内置控制台宿主、agent 算入。[同一台托管 Windows 上的 24 轮 Codex 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44646751480)使用 160×48 与 `SarasaTermSC Nerd Light`。原版 pterm 的 SHA-256 和用户安装的 0.85 相同；三组真实前端模块／进程观测均未发现被检查的 WebView 引擎。REA 静态检查识别到 x86-64 原生 PE，没有 CLR 目录；81 个普通导入 DLL、1 个延迟导入 DLL（ICU），没有 WebView 导入。可动态加载的代码不能仅靠导入表排除。

[这份 EXE 的交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44646064546)验收 **80/81**。唯一未过的是 Codex 显示启动标记后，实际键盘按 Ctrl+Shift+V 的那次图片粘贴；正式输入框就绪后，窗口消息和实际键盘分别使用 Ctrl+V、Ctrl+Shift+V，四次均在请求中收到与生成图片完全相同的像素。Codex、OpenCode、Claude 的满屏选区用例为 **10/10**。两种渲染器各完成六种内存负载。

[多标签独立权限回放](https://github.com/xiongnemo/nemoterm/actions/runs/44647594222)：一个窗口内的两个后端初始权限相反，只对第二个标签保存两次设置，再关闭它。同窗口的另一个程序在每个阶段都能读到正确的文字与光标，GDI、DirectX 各 **7/7**。同一个程序的启动配置和真实设置操作另在两种渲染器各过 **22/22**。这两套计数独立于 81 项汇总。

全量工作流仍保留其他失败，包括 [ReGIS 历史重绘](regis-presented-pairs.md)、[行尾三个逐格差异](column-edge-integrity.md)、[WSL1 粘贴的行边界](wsl-relay-window.md)及[退出期限](wsl-profile.md)。这份试用版不代表所有 xterm 功能或所有 WSL 版本通过。[原始交互报告、身份、图片观测、内存样本和 REA 记录](acceptance-32e588e7.zip)；包内 `sources.json` 标明 GitHub 原包标识、散列及此处留存的文件。
