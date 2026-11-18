# 单文件预览 f564927：交互、显示和内存

测试对象是 [GitHub Windows runner 构建的 EXE](https://github.com/xiongnemo/nemoterm/actions/runs/44374468391/artifacts/14460047904)，4,865,536 字节，SHA-256 `08ecc37606889d2b5af1c1207746d877582140babdc94634235d0f5ad571d28d`。以下结果均核对了这个文件的身份。

[源构建的交互汇总](regression-receipt-f564927.zip)为 **72/74**。未通过的两项都是首次出现 Codex 输入标记时立即粘贴图片（系统按键和调试输入）。Codex 正式编辑器就绪后，两种输入方式都通过；OpenCode 的两种图片粘贴也都通过。[30 项真实客户端原始记录](agents-receipts-f564927.zip)还覆盖了 GDI、DirectX 下三个客户端的默认右键仅复制，以及可配置的复制并粘贴。首次启动未通过的原因和边界另见[独立宿主与上游源码记录](image-paste-key-protocol.md)。交互汇总不含仍有[五帧差异](regis-six-frames.md)的历史 XTerm ReGIS 回放。

在 160×48、SarasaTermSC Nerd Light 的[六个真实客户端窗口](agent-close-cancel-f564927.zip)中，测试用系统鼠标 Shift 拖选显示出来的文本、按 Ctrl+Shift+C，然后通过关闭确认的“取消”回到原标签，直接输入前缀并按 Ctrl+Shift+V、Enter。Codex、Claude Code、OpenCode 在两个渲染器上均向本地测试服务提交了一次含选区的请求，原有剪贴板内容未丢失。[完整 Profile 测试](profile-close-f564927.zip)和[独立测试](dialog-close-isolated-f564927.zip)中的关闭单标签、整窗和无标签窗口六次都收到了 `ab`（取消后）和 `abc`（Esc 后）；独立测试的整窗案例在最后“确定”前一直没有观察到原生 hover 状态，未发送该点击，该次测试未通过。

[英文和简体中文截图及 Win32 控件测量](settings-font-and-rendering-f564927.zip)来自[同一 EXE 的 DPI 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44375436069)，制品 `14459894955`。每页每种语言 22 帧，覆盖单窗口、标签窗口、冷启动和运行中改 DPI，实际窗口 DPI 为 96、120、144、168、192。字体访问和渲染两页的复选框与提示均完整、未碰到底部按钮。[保存和撤销字体权限](osc-font-operations.md)另作交互验证。单显示器上的缩放不覆盖跨屏移动。

| 160×48 的前端压力测试 | 通过数 | 私有工作集峰值 | 同一负载总工作集峰值 | 同一负载私有提交峰值 |
| --- | ---: | ---: | ---: | ---: |
| [GDI 原始记录](memory-gdi-f564927.zip) | 6/6 | 18,886,656 B | 53,567,488 B | 22,212,608 B |
| [DirectX 原始记录](memory-directx-f564927.zip) | 6/6 | 28,749,824 B | 71,868,416 B | 33,001,472 B |

两项私有工作集最大值均来自密集 Unicode 加 Kitty 图片；不包含 shell、控制台宿主及客户端进程。全部 12 项都有结束记录，未强制清理。普通 Codex 会话在同一机器上的稳定读数见 [pterm 对照](pterm-findings.md#f564927-普通-codex-会话实际驻留了什么)。

同一 EXE 的鼠标路径诊断保留了两轮记录。只将指针跳到相邻按钮中央时，[独立回放](dialog-neighbour-f564927.zip)的三个场景及[完整 Profile 顺序](profile-neighbour-f564927.zip)的单标签场景均在相邻按钮没有报告 hover 时停止，未代替用户点击。改为沿按钮内部三个不同像素移动再到中央后，[独立回放](dialog-glide-f564927.zip)的三个场景全部通过（[44378681997](https://github.com/xiongnemo/nemoterm/actions/runs/44378681997)）。六次鼠标点击都先观察到了两个原生按钮各自的 hover，再观察到目标按钮按下并捕获鼠标；每次只发出一组按下/松开。此前失败的回放保持原样。

[相同指针轨迹、包含其他设置操作的完整 Profile 顺序](profile-glide-f564927.zip)也在三个窗口模式全部通过（[44378688703](https://github.com/xiongnemo/nemoterm/actions/runs/44378688703)）。这是对同一文件的独立回放，并未覆盖旧的失败记录。

在[单独的内存回放](https://github.com/xiongnemo/nemoterm/actions/runs/44377353243)里，控制器把较大的 VT 输出写入独立的只读用途文件，子进程读取并核对字节数和 SHA-256，再按原样发往终端；高频轮询的控制 JSON 里只有文件标识。所有负载仍要求子进程收到终端的有序回复、达到完整网格、满足原内存上限和正常退出。[GDI](memory-spool-gdi-f564927.zip) 和 [DirectX](memory-spool-directx-f564927.zip) 各六项通过。这个回放没有重跑其余 62 项，也不能证明前一版本偶发的 Windows 文件替换错误只有一个原因。

在同一次源构建中：[真实 WSL Vim](preview-wsl-vim-f564927.zip) 在 `TERM=xterm` 和 `xterm-256color`、实际 GDI 和 DirectX 四种组合下，都确认普通点击到达 Vim，Shift 可复制中文且不移动 Vim 光标，Ctrl+Shift 跨行矩形选区有效，调整窗口大小后 Vim 和前端的网格一致，粘贴保存后文件字节正确。[WSL 的 img2sixel 输出](preview-wsl-sixel-f564927.zip) 在两种渲染器显示、重绘和清除时，指定区域连同一像素外边界都与独立预期逐像素一致。[WSL tput 调色板和 RGB 色块](preview-wsl-colour-f564927.zip)的原始回复和像素也已保存。这些是实际应用路径的证据，不代表所有 xterm 序列均已实现。

同一鼠标路径也在[六个真实客户端窗口](agents-grid-glide-f564927.zip)中回放（[44379572449](https://github.com/xiongnemo/nemoterm/actions/runs/44379572449)），6/6 通过：每次 Copy 后点击“取消”都经过两个按钮的原生 hover 和目标按钮按下/捕获检查，剪贴板保留原文，直接输入前缀后粘贴，HTTP 端收到选区恰好一次。未要求用户再点终端。
