# Windows 单文件 `83d584d8` 的试用验收

[原始构建](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675625577)：Windows x64 `nemoterm.exe`，4,947,456 字节，SHA-256 `fa9d5c62c8179cdee89308c96f97ecbdfff087f0f8a9f189321f6109e13593e8`。本页数字全部来自这份 EXE。Windows UI、实际键鼠和应用都在 GitHub 托管 Runner 上运行；真实客户端连接本地测试服务，不访问线上模型。源码中的[协议覆盖表](../docs/PROTOCOL_COVERAGE.md)另列未实现项。

**选择、复制与删除。** 使用 `SarasaTermSC Nerd Light`、160×48，在 Codex、Claude Code、OpenCode 的真实 GDI / DirectX 窗口检验了默认 Ctrl+Shift+C、Ctrl+Shift+V 和两种右键行为。应用打开鼠标跟踪后，Shift 拖选仍选择屏幕字格；默认右键仅复制，选用「复制并粘贴」后才在这次右键操作中送入应用。[独立复核 18/18](https://github.com/xiongnemo/nemoterm/actions/runs/44829899285/artifacts/14675638028)：逐项匹配真实键鼠动作、系统剪贴板、字格边界及接收端的唯一提交。

[逐格复核及原始读数](https://github.com/xiongnemo/nemoterm/actions/runs/44829307957/artifacts/14675995098)：十个窗口各从左、从右选一次混排文字，20/20 次字形顺序、高亮边界和剪贴板一致，10/10 个反向粘贴提交均只收到一次预期内容。单条字符消息输入两个汉字后，两次实际退格逐一擦除；单字、空格和最后提交在 10/10 个窗口通过。十个窗口包含两个额外的 Claude 启动/显示顺序对照，在每种渲染器上各执行一次。

**图片。** Codex 编辑器就绪后，Ctrl+V 与 Ctrl+Shift+V 分别用物理按键和窗口消息触发：四种组合的首次提交都收到一张与生成图样逐像素一致的 32×16 PNG，后续请求没有重复发图；[原始请求及终端输出](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14674859572)。输入框仅首次可见、尚未等到就绪的两个测试仍失败：首次请求只有文字。这些观察保留在严格总评中。

**内存。** [同机 24 轮 Codex 对话](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675662216)，每个窗口单独采样，不把 shell、控制台宿主或 agent 进程加在前端上。私有工作集与总工作集是不同指标，采样峰值不代表采样间瞬时上界：

| 前端 | 私有工作集峰值（字节） | 总工作集峰值（字节） | 私有提交峰值（字节） |
| --- | ---: | ---: | ---: |
| 原版 pterm 0.85 | 3,780,608 | 22,724,608 | 4,481,024 |
| Nemoterm GDI | 5,476,352 | 34,566,144 | 6,889,472 |
| Nemoterm DirectX | 9,805,824 | 44,941,312 | 11,345,920 |

三个客户端的选择、编辑和提交是另一个工作负载；按十个窗口取最大值，GDI 私有工作集为 12.14 MB，DirectX 为 20.18 MB（十进制）。[pterm 为什么轻](pterm-findings.md)另有原版 PE 和源码对照。对本版单文件做静态 PE 读取，共有 81 条普通、1 条延迟导入 DLL 声明，没有常见浏览器/WebView 模块；另核对十个真实窗口在启动和提交后的 20 次模块及进程快照，均未发现已知 WebView/浏览器标记；采样之外的动态加载不由静态表证明。

**六组满屏压力。** [远程内存复核](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675981766)重新读取同一 EXE 的逐笔前端样本。纯文字、内嵌图、动画、Kitty、压缩 Kitty、Unicode 混合 Kitty 六组各自在 GDI 和 DirectX 运行。取六组最大值：

| 前端 | 私有工作集（字节） | 距上限（字节） | 总工作集（字节） | 私有提交（字节） |
| --- | ---: | ---: | ---: | ---: |
| GDI | 19,333,120 | 666,880 | 56,266,752 | 22,937,600 |
| DirectX | 29,577,216 | 422,784 | 74,846,208 | 32,657,408 |

**标签和颜色。** [本版四边标签](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14674852795)的八张原图、悬停预览更新、切换后输入和复制均通过，四边的五种中键操作为 20/20。[DEC 调色板](dec-colour-table.md)涵盖报告、恢复、取消、跨 4 KiB 以及屏幕像素/Win32 实际读回，四种组合共 56/56。

[同一 EXE 的关闭确认框回执](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675681301)：中文版、英文版各四项，8/8 通过，包括取消后不用点终端就能继续输入。

双标签的独立压力用例同时显示任务栏进度、Unicode 和 Kitty 图形。[GDI](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675681614) 在 1,631 次有效前端采样中最高为 19,984,384 字节，距门槛仅 15,616 字节；[DirectX](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675511571) 在 859 次采样中最高为 29,118,464 字节。它们与单标签六组满屏负载分开统计。

**严格总评与适用范围。** [原始严格交互](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14675679014)是 **79/81**，没有跳过；两项失败均为前面记录的 Codex 输入框首次可见时贴图。[汇总和原始画面复核](https://github.com/xiongnemo/nemoterm/actions/runs/44827444033/artifacts/14676181384)还核对了 GDI、DirectX 共 8 帧 Sixel，以及 `TERM=xterm` / `xterm-256color` 下 Vim 和 tmux/Vim 的矩形选区。XTerm 的[三个行尾宽字格](column-edge-integrity.md)、[ReGIS 部分中间帧](regis-presented-pairs.md)和 WSL1 的终端尺寸等仍有差异，不宣称完整协议兼容。

[本页依据的记录包](trial-83d584d8.zip)包括未改动的 GitHub 总评、内存、键鼠、四边标签制品，以及本版 PE 导入记录。`sources.json` 给出原始下载编号和散列；总评内保留原始失败。所有编译、交互和渲染测试均在 GitHub 托管 Runner 上执行。
