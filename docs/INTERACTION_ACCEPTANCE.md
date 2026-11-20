# 远程测试与交互验收

完整 `ci.yml` 的 **windows-trial** 作业在 Linux Runner 上只读汇总同一份 Windows EXE 的原始制品。下载 `windows-trial-<run>-<attempt>` 后打开 `report/report.md`：含单文件下载入口、严格交互总数和失败名单、24 轮对话及六种满屏负载的私有工作集、实际 agent 窗口的选区、Sixel，以及 Codex 就绪前后各快捷键首次提交的结果。附件含原始交互报告、逐项数字和从原始截图裁出的选区。早期粘贴的红项照常保留；报告不代替整套协议测试。对已有完整运行，使用 `font-zoom-replay.yml` 的 `suite=windows-trial`、`source_run` 和 `source_commit`，无需再运行 Windows 桌面用例。


所有自动测试在 GitHub-hosted runner 上执行。开发电脑只编辑源码、提交、调度 Actions 和下载证据；不需要启动测试终端、接管焦点或修改本机剪贴板。

这里的 xterm 兼容性指应用在 `TERM=xterm` 或 `xterm-256color` 下能够正确交互。Nemoterm 的 Windows 启动代码设置 `TERM=xterm-256color`、`COLORTERM=truecolor` 和 `TERM_PROGRAM=nemoterm`。新构建通过进程内的 `WSLENV` 列表将这些变量传给 Linux 子程序；保留调用方已有的其他条目及显式方向。`shells` 组在实际 WSL Bash 中读取继承的 `TERM`，再用系统 `tput` 分别按默认条目和显式 `TERM=xterm` 移动光标，以终端返回的位置验收。这个检查覆盖名称、颜色能力查询和光标寻址；它不是所有 terminfo 能力的认证。 同一 shell 组还会在两个条目下启动真实 `less`：方向键下滚一行、Page Down 翻页、搜索到指定文本、退出后恢复先前的屏幕。逐步保存窗口文字和截图。原版 XTerm 的特定 ReGIS 逐帧对照单独报告，不代表普通 TUI 的兼容性；原失败记录仍保留。

窗口宽度引起主屏软折行时，`selection` 组使用真实 Shift 拖动，核对选区内的字形、窄窗口与恢复后复制的文字，以及应用实际收到的鼠标事件。[修复前后回放和证据](../research/selection-reflow.md)。

内存核对：从同一 EXE 的 Actions 下载源构建 ZIP、同机 24 轮 agent 对照 ZIP，以及 `interaction-memory-gdi`、`interaction-memory-directx` 两份 ZIP，按此顺序运行 `python scripts/review-frontend-memory.py SOURCE.zip AGENT.zip GDI.zip DX.zip`。脚本只读制品：它检查 EXE 的实际字节和三份来源清单，核对字体、真实网格、渲染器及进程数，然后从每个负载的逐次采样重新计算前端私有工作集、总工作集和私有提交峰值。三列的峰值不必来自同一时刻。

## 入口

完整回归（包含重新构建）：

```powershell
gh workflow run ci.yml --ref <branch> -f scope=full
```

手动调度的验收按 run ID 隔离；同分支之后推送文档或测试脚本不会取消它。普通 push 仍只保留同一工作分支上较新的运行。

`Test and build` 汇总 Linux ASan/UBSan、C/C++ 单元测试、MSVC 渲染诊断、MinGW 原生协议和像素测试、单 EXE 完整套件、profile 持久化、DPI/双语界面，以及下表的 81 项检查（69 项交互、12 项完整 Sarasa 网格负载）。单 EXE、DPI 和交互任务共用这次 source-host 构建的准确 EXE，并校验来源提交、大小及 SHA-256。

只回放测试脚本，不重复编译：

```powershell
gh workflow run font-zoom-replay.yml --ref <branch> -f suite=interaction -f source_run=<run-id> -f source_commit=<40-character-sha>
```

`suite=close-cancel` 在双标签下分别关闭当前会话、关闭整个窗口，再在独立窗口重复。先让子进程接收实际按键 `a`，用鼠标点关闭确认的 Cancel，立即按 `b`；再次关闭时用 Esc 取消，再按 `c`。取消后不点击终端、不请求激活、不打开设置。检查原子进程收到的精确字节、键盘焦点、现存会话和最后点 OK 的效果。原始记录在制品的 `dialog-close-input.json`。完整回归的 profile 任务也运行这套检查。

`suite=fullscreen` 在独立窗口和标签窗口中让子程序发送 `CSI 10 ; Ps t`，用 Win32 读取顶层窗口的实际矩形、边框和最大化状态。进入时必须铺满显示器；退出时必须完整恢复原状。禁用远程调整大小或锁定窗口后，进入和切换请求都必须保持原状。两份结果和被测 EXE 的哈希保存在同一制品中。

同一入口记录 `CSI 9 ; Ps t` 的工作区边界、原窗口与每一步的四边坐标、有无标题栏及 Windows 最大化状态。单轴最大化应保持另一轴不变；禁用远程调整大小或锁定窗口时应忽略应用请求。对当前 `f2f553b9` 的[原始失败回放](https://github.com/xiongnemo/nemoterm/actions/runs/44680175234/artifacts/14603833745)为 12/36。独立上游对照使用 `protocol-reference.yml -f family=window-maximise`：XTerm 412 在专用 Xvfb + Openbox 中运行，记录 5 组输入的客户区、外框、窗口管理器属性和终端回复。

`suite=font-ops` 在同一个 EXE 上分别验证 GDI 和 DirectX。先用独立启动的 Sarasa、Consolas 窗口核对实际字形和字符格，再验证标签间字体互不影响，以及从“窗口 → 外观 → 字体访问”保存配置和撤销权限。原始数据和首次失败见 [OSC 50 实测](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/osc-font-operations.md)。

`suite=rendering-settings` 在远程显示器实际支持的缩放比例下打开英文、简体中文“渲染”页，记录两个复选框的文字边界、与底部按钮的间距和窗口截图。分别检查标签窗口、独立窗口和运行中改变 DPI 的情况。

`suite=wsl-tui` 在单独的 Windows runner 上只安装所需 WSL 环境，记录直接运行的 `less` 与 `script` 记录器运行的 `less`，并区分窗口 API 和系统导航键。记录器的成功不能替代直接运行。

`suite=wsl-sixel` 用 Ubuntu 的 `img2sixel` 经 WSL 终端输出一张彩色 PNG，保存实际 Sixel 字节并用 `sixel2png` 独立解码。分别核验真实 GDI、DirectX 对应位置的每个像素、四边一像素范围、重绘及清除后的结果，同时保留工具版本、文件摘要和原始截图。工具只安装在 runner 上。

同一 `wsl-sixel` 回放也覆盖可选内嵌 Linux PTY。`wsl-pty-geometry-{gdi,directx}/geometry.json` 分别记录启动、拉大窗口、放大字号的 Windows 客户区测量，Linux 程序的 VT 查询及 `TIOCGWINSZ`；`-fixed` 两个目录是「调整字体、保持行列」的独立窗口。`startup.json` 保存不经过产品的 PTY 对照。另用相同散列的内嵌 ELF 在原生 Linux 和托管 WSL1 直接读回四项尺寸、检验无效包；详见 `linux-pty-pixels-*` 和 Windows 制品的 `wsl-relay-records`。同一行列下像素未更新仍记失败。该检查不作为收集剪贴板和退出回执的前置条件。

下载同一源构建的 `wsl-vim`、`wsl-tmux-vim`、`wsl-sixel` 三份原始 ZIP 后，可用 `python scripts/review-wsl-window-records.py <vim.zip> <tmux-vim.zip> <sixel.zip>` 离线复核。脚本读取 Vim 逐次写出的光标、尺寸与内容，比较选区与相邻格的截图变化，检查粘贴后保存的 UTF-8 文件，以及 Sixel 绘制、重绘、擦除时包含边界的像素。

`suite=wsl-colour` 使用 Ubuntu 自带的 `tput` 和 `ncurses-term` 的三个条目画色块。分别记录真实 `setaf`/`setab` 字节，再检查 GDI 和 DirectX 的每一个色块像素、相邻空白、重绘和退出备用屏幕后的背景。`xterm-direct` 使用仅蓝色分量相差 1 的两个 RGB 值，能检出调色板量化。

`suite=wsl-vim` 在两个 TERM 条目和实际 GDI、DirectX 下启动 Vim。普通鼠标点击须改变 Vim 自己报告的光标，Shift 拖选须复制完整中文字且不移动 Vim 光标；窗口两次改尺寸后 Vim 与前端应报告同一网格；最后用快捷键粘贴，验证保存文件的 UTF-8 字节和退出后的画面。

`tabs` 分组的 `tab-clipboard-ownership` 在同一原生窗口打开两个 profile：GDI 标签使用默认右键仅复制，DirectX 标签显式设置右键复制并粘贴。两个子进程都打开应用鼠标报告和带边界的粘贴。用系统按键切换标签后，分别检查双方收到的完整字节、选区像素和系统剪贴板，区分当前输入与后台误收。

`suite=wsl-tmux-vim` 仅在 GitHub 托管 Windows runner 上运行，并记录 `wsl --list --verbose` 确认 Ubuntu-24.04 使用 WSL1。相同四组输入通过 tmux 到达 Vim；检查外层 `xterm` / `xterm-256color`、内层 `tmux-256color`、两次实际缩放，以及 Shift 拖选和矩形选择后 tmux 没进入复制模式。每次检查通过该次回放独占的 tmux socket 读取状态，不占用 Vim 的键盘输入。这项测试不使用开发电脑的 WSL，也不证明 WSL2 的行为。

同一工作流还在 GDI、DirectX 各启动两次相同的 `xterm-256color` 会话：默认权限以及关闭应用写系统剪贴板。Vim 开启鼠标后，用实际 Shift 拖选 `中文`，再让连接中的 tmux 使用 `load-buffer -w` 写入另一段 Unicode。保存客户端实际输出中的 OSC 52 与后续 Vim 画面标记、tmux 自己的缓冲区字节、Windows 剪贴板值和序号、窗口像素，以及实按右键和 Ctrl+Shift+C 的结果。四个独立结果在 `wsl-tmux-clipboard-*/result.json`，与原有四种 TERM/渲染器交互分别计数。

`suite=profile-env` 可让 `--profile 名称` 和 Windows 跳转列表所用的 `@名称` 分别在父环境未设、设置了不同 `TERM`、已有全部 WSL 转发规则时启动子进程，读取其真实 `TERM`、`COLORTERM`、`TERM_PROGRAM`。

`f628d89` 单文件预览的[完整回放和内存数据](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/right-button-release.md#complete-interaction-replay)为 74/74。另一个 MinGW 便携构建出现[混合 profile 关闭超时](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/mixed-profile-close-f628d89.md)；`tabs-close-replay.yml` 的 `profiles-mingw` 和 `profiles-api-mingw` 使用原失败产物，分别回放带探针和内置自动化的操作。

`interaction` 可额外传 `-f 'groups=["shells","clipboard"]'` 只重跑指定组；留空执行全部。

`suite` 还可选 `single`、`dpi`、`font-bell`、`ui-regression`、`shell-lifetime`、`tcap`、`unicode-boundary`。回放允许源 run 的其他测试失败，但要求 source-host 构建成功；生产代码或构建配方与该产物不一致就拒绝回放。`tcap` 对同一单 EXE 检查数据库键盘的 1,293 条原生输入流及四种独立 SetTcap/GetTcap 权限组合；45 个 F35 用例缺少 Windows 物理映射，40 个 Shift+PageUp/PageDown 用例保留本地滚动绑定，均明确列出并由核心测试覆盖。查看结果用 `gh run view <run-id>`；下载证据用 `gh run download <run-id> --dir <new-directory>`。

`shell-lifetime` 在同一个准确 EXE 上交替执行 12 次普通 Git Bash 复制/关闭和 12 次带进程观察的复制/关闭，随后执行 2 次正常连接对照和 4 次受控的延迟客户端检查。完整 CI 也会自动调用此工作流。每次保留独立结果；原先的 3 秒回收门槛不变。失败后额外观察 12 秒并采集遗留进程的命令行、线程和转储，只用于诊断，不能把失败改成通过。[`5f2a7e46` 的首次检查](https://github.com/xiongnemo/nemoterm/actions/runs/44642856432/job/135980481231)在启动任何重复用例之前因夹具缺少 `require_clean_fixture` 参数退出。补齐参数并要求干净工作区后，[同一 EXE 的回放](https://github.com/xiongnemo/nemoterm/actions/runs/44644768586)完整执行并通过 24 项重复操作和六个连接对照。已发现的关闭残留及修复验证见 [Git Bash 关闭调查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/git-bash-close-race.md) 和 [关闭后连接检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/closed-console-connections.md)。

同一套回放另开一台全新的 Windows Runner，核对首次运行 `--list-shells` 的结果。裸命令以及带 `--tabs`、`--no-tabs` 的两种调用都必须在各自 10 秒期限内返回相同的六种候选 shell，且不能创建 Default Profile。最后正常启动一个子程序，检查 `--list-shells` 作为子程序参数时会被原样转交，并确认这次正常启动会创建 Default。此项独立于 Git Bash 关闭检查；两项分别保留原始结果。 [首次使用的前后回执](../research/shell-list-first-use.zip)：`5c3a8d5c` 第一次查询就写入了 Default；`371a6f01` 三种查询均返回相同清单且未写入，随后正常启动会创建 Default。旧版另有一次 `--list-shells` 等待 10 秒超时，没有遗留进程；同一 EXE 重放 24/24 通过，修正版另测 24/24 也通过，两组均自然退出。现有证据无法把那次超时归因于配置写入。

`suite=paste-lines` 还使用真实 Windows 剪贴板延迟交付来验证会话隔离：先确认后台读取已经开始，关闭窗口（GDI、DirectX）或在同一 HWND 内重启 shell（GDI，四次），再放行旧文字。两个存活的子进程都不得收到旧文字；重新发起粘贴时只能由目标收到一次。保留各自的实际输入字节和自然退出状态。`tabs-close-replay.yml` 的 `sessions-mingw`、`restart-mingw` 可以复核原先失败的便携 EXE；不要用便携结果替单文件签收。[同一单文件与便携原失败记录](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/acceptance-fc769def.md)。

`single-exe.yml` 保留独立手动入口，正常 push/PR 由完整 CI 调用，避免重复构建。上游协议对照与内存/句柄诊断继续使用仓库中已有的专用远程工作流，不需要本机补跑。

仅补齐已测便携包的许可文本，使用同一回放入口的 `-f suite=portable-notices`，并提供原 `source_run` 和 `source_commit`。它在托管 Ubuntu Runner 上验证原构建成功、生产源码未变、二进制哈希一致，再添加 Ncurses/X11 许可和打包记录；所有原文件必须逐字节不变。它不重建或执行产品，也不会把原回归中的失败改成通过。当前产物和首次回放失败均见 [完整回归记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-product-regression.md)。

重新采集旧 XTerm 对照数据也使用远程入口：

```powershell
gh workflow run protocol-reference.yml --ref <branch> -f family=historical-xterm
```

此入口覆盖 25 个原先没有直接 CI 入口的采集脚本，分十一组执行 33 次采集，包括四批完整字符集映射、输入/粘贴、校验和、编辑、键盘和 XTSETTCAP 研究。它只构建一次固定提交的上游 XTerm，各组核对同一二进制哈希，在自己的 Xvfb 显示中执行。日志和新观测独立上传；不覆盖仓库内的历史参考数据，也不把采集成功当成 Nemoterm 已支持对应协议。运行控制器拒绝本机及 self-hosted runner。可用 `-f historical_group=keys` 等参数只重跑一组；`legacy-modifiers` 并行执行三个键盘配置分组，每组保留全部正常对照和状态检查。

完整 ncurses 数据库及 termcap 键盘研究也在托管 Runner 上执行：

```powershell
gh workflow run protocol-reference.yml --ref <branch> -f family=terminfo-database
```

此入口固定 ncurses/XTerm 源码提交，由上游 `tic` 编译整个数据库、`libtinfo` 读取按键，再将编译后的只读 C 表逐项与原始观测比对。默认还运行独立 XTerm 启动键盘采集；仅修改数据导出或验证时，可加 `-f terminfo_skip_keys=true` 单独检查数据库。该专项不构建 Nemoterm，不作为产品协议或内存验收；证据及范围见 [数据库记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-database.md)。

ReGIS 上游对照使用 `-f family=regis`。它明确启用固定版本 XTerm 的 ReGIS，在私有 Xvfb 显示中对 61 个场景分别发送整段和逐字节输入，保留原始回复、386 张初始/步骤截图、像素格式、编译开关及自然退出结果。新增调色板对照必须绘制规定数量的可见像素，避免黑底黑图掩盖变化。脚本拒绝本机和 self-hosted runner。通过采集不代表 Nemoterm 已实现 ReGIS，范围和产物见 [ReGIS 对照记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/vector-graphics-source-review.md)。

后续 ReGIS 采集已加入每步完整重绘后的截图，以及双向共享调色板场景，加上备用屏幕、滚动边界及主/备用屏清除历史后共 67 个场景；旧参考截图保持不变。`family=regis-core` 执行原生解析器、真实终端输入、图像视图与调色板对照。完整 `scope=full` 现在也包含这组检查，并用同一次 source-host 的单 EXE 运行 `regis-window.yml`：GDI、请求 OpenGL、强制 DirectX 和直接读取已呈现 GDI 客户区四组原生测试。OpenGL 如回退则明确记录实际渲染器，不将 GDI 结果算作 OpenGL 通过。窗口测试检查独立定义的像素几何和生命周期，不取代仍然失败的历史 XTerm 画面对比。

只修正窗口测试脚本时可回放同一 EXE：

```powershell
gh workflow run font-zoom-replay.yml --ref <branch> -f suite=regis-window -f source_run=<run-id> -f source_commit=<40-character-sha>
```

该入口要求原 source-host 构建成功、生产源码未变、EXE 大小和 SHA-256 与清单一致。结果范围和未完成项见 [ReGIS 图像视图记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-image-views.md)。

ReGIS 生产代码变化后的定向重建使用 `protocol-reference.yml -f family=regis-product`，重新构建同一单文件配方后运行四组窗口检查。它不代替 `ci.yml -f scope=full` 完整回归。备用屏幕和滚动边界的失败、修复与证据见 [边界记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-screen-edges.md)。

`protocol-reference.yml -f family=regis-discovery` 在两种页面尺寸下采集同一份启用 ReGIS 的 XTerm 的设备属性和图形查询回复。`suite=regis-window` 还包含真实窗口先查询、再据返回尺寸绘图以及重绘的验收。见[查询和历史画面差异](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-discovery.md)。

## 交互矩阵

每组使用独立 Windows 2025 runner，最多同时运行五组；组内顺序执行并保留各自失败，不因另一组失败取消测试。`scripts/interaction_acceptance.py run` 拒绝本机及 self-hosted runner；`plan` 和 `prepare` 只处理清单和文件。

| 组 | 用例数 | 覆盖 |
| --- | ---: | --- |
| input | 2 | byte/ReadConsoleW、中文/emoji、IMM、模拟 DPI 与组合窗位置 |
| selection | 6 | 默认/自定义 bindings，GDI/DX 分别在默认 profile 字体和 Sarasa 上检查矩形与 Shift 选择，右键仅复制与复制后粘贴；跨行复制粘贴区分自动折行、右边缘宽字和硬换行 |
| clipboard | 2 | GDI/DX 文件/目录拖放，路径引用、应用接管与文本/图片优先级 |
| agents-grid | 10 | 三种真实客户端分别在 GDI、DirectX 用默认尺寸启动，不传行列覆盖。断言实际 160×48，用系统输入完成选择和回贴，记录发现窗口至提交阶段约每 100 ms 的前端内存。Claude Code 还在显式关闭终端双向重排的配置中重复，默认配置仍独立计分。两项嵌套场景从 pwsh 启动 Claude，并核对启动前后 shell 原文与客户端的字序标记。[原始回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/claude-writer-order.md)。 |
| agents | 30 | 真实 Codex、OpenCode 分别用窗口接口及 Windows 系统按键粘贴图片；Codex 首次画出输入和报告就绪后分别检查，两项独立计分；在实际 GDI / DirectX 标签页用系统鼠标和键盘 Shift 拖选、Ctrl+Shift+C/V 与两种右键策略，核对高亮、剪贴板、接收端实际文本及退出。OpenCode 必须主动请求接管鼠标；Codex 记录当时实际请求。Claude Code 的组合重音分别核对剪贴板原文、原生子程序输入字节和两种独立 PTY 的 Messages 回执。另以不会被规范化的组合字符验证快捷键及两种右键模式端到端逐字一致。其中三种客户端、两种渲染器、两种右键策略共十二例；汇总报告核对 Shift 和左键的松开顺序、右键后是否另按粘贴、两端未选中字格及服务端实际收到的文本摘要。用例入表不代表已经通过。 |
| rendering | 3 | 实际 GDI 客户区捕获、三种渲染器、字号缩放/恢复 |
| mouse | 2 | 鼠标协议字节、按键、滚轮和坐标；另对照 XTerm 的 31 组指针颜色回复、Windows 实际光标像素、恢复系统指针和隐藏标签隔离 |
| tabs | 9 | 四侧标签栏/预览与缩放、会话回收，以及切换标签时的选区、剪贴板和输入归属 |
| settings | 2 | 独立窗口和标签宿主的 profile CRUD、设置保存/重载 |
| shells | 1 | pwsh、Windows PowerShell、BusyBox ash、Git Bash、WSL Bash、cmd |
| bell | 2 | 声音 API、视觉响铃/恢复及关闭模式 |
| memory-gdi | 6 | 完整 160×48 Sarasa 网格：文本、PNG、GIF、Kitty、压缩 Kitty、Unicode 图片的内存/像素/关闭回收 |
| memory-directx | 6 | 相同六类负载，要求实际使用 DirectX，拒绝静默回退 |

Sarasa Light 从固定 v2.3.1 压缩包安装，校验下载及实际字体名称，禁止静默换成替代字体。BusyBox 从固定源码提交交叉编译，记录成品 SHA-256 并附源码和许可证；Codex/OpenCode 使用 npm lock 文件固定实际原生客户端，保存客户端 EXE 哈希。WSL 在需要的组内安装 Ubuntu 24.04/WSL 1。shell 组要求六种 shell 全部检测成功并实际启动，不把“未安装”当通过。

当前前端私有工作集门槛按实际渲染器判定：GDI 严格低于 20,000,000 字节，DirectX 不超过 30,000,000 字节；OpenGL 保留例外。用户于 2026-11-18 调整了 DX 上限，旧 25 MB 失败不改写。同一已测 EXE 的六项新门槛回放和原始证据见 [DirectX 30 MB 记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/directx-30mb.md)。

`d817161` 的[实际回放记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-d817161.md)列出六种负载在 GDI / DirectX 上的三个内存指标。[真实 Codex 选区与粘贴](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/agent-selection-roundtrip.md)记录默认快捷键的连续操作、右键两种模式，以及同一 EXE 上保留的首次失败和修正后回放。

双客户端、双渲染器回放与内存口径见[真实客户端记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/agent-native-roundtrip.md)。

客户端 fixture 使用临时 HOME/配置、权限拒绝、关闭工具/插件/更新及固定回环响应服务；不使用个人账号、历史会话或真实模型调用。图片验证使用生成的 32×16 棋盘图，核对请求中的图片像素。

## 证据与判定

每组总会尝试上传 `interaction-<group>-<run>-<attempt>`，内容包括：

- `SOURCE-HOST.json`：待测 EXE 来源与哈希。
- `environment.json`：runner 镜像、字体和下载依赖的身份。
- `identity.json`、`plan.json`、`results.json`：脚本提交、客户端/文件哈希、用例及状态。
- 每次尝试的 `output.log`、`research/`、`build/`：截图、输入回执、像素/资源数据和失败证据。

超时、断言失败或强制回收遗留进程均判失败。重跑创建新的 run/attempt，不覆盖旧失败。内存目标沿用既有 GDI 与可选 GPU 模式约定，不为了 runner 通过而放宽。

`memory-*` 组只在托管 Runner 上选择其显卡驱动列出的较大显示模式，使用实际 100% DPI、固定 Sarasa Light 和显式 `--require-grid`。初始终端必须确实为 160×48 字符；被屏幕裁小就失败。记录实际工作区、字体、渲染器、网格和三项内存指标；先采样内存，再执行截图/注入检查，并在结束后恢复显示模式。可用 `-f 'groups=["memory-gdi","memory-directx"]'` 单独回放。原有 Consolas 小网格回归仍保留，不能替代这些完整网格负载。

真实 Windows DPI 的 100/125/150/175/200% 冷启动和动态切换由独立 [DPI 工作流](DPI-CI.md) 覆盖；交互组的模拟 DPI 不替代它。

语言设置窗口的本地化标题在 `WM_INITDIALOG` 中填写。自动化须等该进程的设置对话框可见且分类树已创建，再独立核对实际标题。原 [44220302070](https://github.com/xiongnemo/nemoterm/actions/runs/44220302070) 在读到模板标题 `PuTTY Configuration` 后失败；同一 EXE（SHA-256 `0f660d027df3523b6d4423400d98d83f9a6c7a4a10caaeaa095438a9335f8950`）的[独立回放](https://github.com/xiongnemo/nemoterm/actions/runs/44223202777)通过 24 个真实缩放场景和 8 项语言交互。两次的[原始标题及回放测量记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/i18n-settings-ready-evidence.zip)保留了各自的产品与测试提交身份。

自动测试可以验证系统声音 API，但不能证明用户听到声音；注入输入不能证明某款物理鼠标、真实第三方输入法候选窗或多显示器驱动表现。报告如实记录这些边界与 runner 上可用的 IME，不自动签署人工验收。它们不构成本机测试前置条件。

## 历史证据

迁移前的内存、桌面中断和输入法问题保留在 [历史本机记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/d3d11-local-f3b5b65.md) 及 `research/interaction-input-dpi-f3b5b65.zip`。旧版的通过记录不能套用到新 EXE；本轮迁移结果见 [远程迁移记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/remote-test-migration.md)。

单独复核应用设置鼠标颜色时，可用 `font-zoom-replay.yml` 的 `suite=pointer-colour` 指定确切的 `source_run` 和 `source_commit`；完整交互的 `mouse` 组使用同一套输入和像素检查。独立 XTerm 原始捕获入口为 `protocol-reference.yml` 的 `family=pointer-colour`，Win32/GDI 资源对照为 `family=pointer-resources`。见[原始回复、光标截图和资源记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/pointer-colours.md)。

打字时鼠标指针是否隐藏（XTSMPOINTER）：在 `protocol-reference.yml` 选 `family=pointer-hiding` 采集 XTerm；在 `font-zoom-replay.yml` 选 `suite=pointer-hiding`，指定 `source_run`、`source_commit` 回放同一份 Windows EXE。测试分别记录按键前、键入后、再次移动后的系统指针，以及子程序实际收到的字节。 该 Windows 回放也在 GDI、DirectX 上分别检查：应用开启鼠标跟踪、打字隐藏指针后，在同一位置按下 Shift 和左键拖选「中文」。保留拖选前和按住时的截图，并核对四个高亮格、系统剪贴板以及两次按键之间的完整子程序输入。

`selection` 组覆盖越界拖选：一次移动后保持左键，在两端从滚动缓冲区复制有编号的中文和组合字符，并检查选区像素。另一个用例在独立的托管 Windows 桌面上使用系统鼠标键盘输入，检查应用接管、重新移入、松键、取消捕获及粘贴给子进程的字节。

先按鼠标、在越过边沿时才按 Shift 的情形另行核对应用收到的按下和松开。见[拖选版本对照及原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-history.md)。

要重放 MinGW 独立窗口在会话多次重启后的关闭，请使用 `tabs-close-replay.yml` 的 `fixture=restart-mingw`，指定失败的 `source_run`、`source_commit` 和原 EXE 的 `executable_sha256`。`repetitions=3` 会运行六个独立进程：三个覆盖过期粘贴隔离，三个操作真实断开提示，保留每次正常退出或超时及进程回收情况。

Sixel 共享调色板：可对照[新绘制色块、强制重绘和原始 XTerm 像素](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-register-terminator.md)。`9ece5e0` 的 Windows 原生检查为 64 项图形与 12 项历史缓冲检查；历史 131 帧仍有 6 帧不一致。

远程交互回放现在会生成 `interaction-report-<run>-<attempt>`。它按所选组核对用例名单、终端 EXE 的 SHA-256、子进程正常退出及满屏内存记录。单独重跑 `agents` 只算该组；缺组、混用 EXE、重复用例或强制终止都不能得到整套通过。原始截图与日志仍在各组产物。真实 OpenCode 的默认右键和“复制并粘贴”验收见[四个实际窗口与 HTTP 回执](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/opencode-right-click.md)。

Codex 首次输入会同时触发颜色查询。托管 Windows 控制台用相同绘图数据回放，分别检查颜色回复的内容、顺序和抵达时间；结果与真实桌面选区、剪贴板及 HTTP 提交分开验收。见[原始失败及同输入对照](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/codex-startup-colours.md)。

`unicode-boundary` 使用固定 Claude 客户端、两种独立 Windows PTY 和接收原始输入的原生程序，区分剪贴板、终端输入和客户端规范化。复现、原始证据和图片粘贴的已知失败见[真实客户端边界记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/agent-unicode-boundary.md)。

`selection` 还会分别设置按下、移动和松开的位置。在应用接管鼠标时，普通和矩形选区都应以实际松开的字符格为准；反向拖选即使没有中间移动消息也应能复制，同一格按下和松开则仍是单击。检查高亮、系统剪贴板和子程序实际收到的输入，见[原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-release-cell.md)。

`selection` 还检查在终端内右键复制、在别的窗口松开后，下一次交给应用的右键能成对抵达。GDI 和 DirectX 逐字节核对应用收到的按下与松开，见[修复前后的原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/right-button-release.md)。

同一 EXE 可用 `font-zoom-replay.yml` 的 `suite=image-timing` 分别重放 Codex 首次显示输入与报告就绪后的两种贴图快捷键；`suite=picture-keys` 则用同一批启动输出核对原生 Windows 键盘记录。见[启动时序、实际图片与原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/agent-unicode-boundary.md#codex-image-paste-during-startup)。

隔离单文件的两个 Codex 场景使用不同进程。`codex-image-paste` 保留首次看到提示就贴图的严格检查；`codex-image-paste-after-ready` 等到应用报告 idle 并重新画出输入标记才按键，分别核对 Ctrl+V 和 Ctrl+Shift+V。两项各自计分，失败都保留。后者使用 SarasaTermSC Nerd Light，原始回执在 `research/codex-ready/`。短回放 `suite=image-timing` 把同一份 EXE 复制到独占的空目录，并记录交互后唯一文件的 SHA-256；它不重复其余单文件原生回归。

`agents` 的六个普通位图用例区分首次出现输入文字、等待 Codex 就绪、Windows 实按和窗口接口。每个用例都在独立会话验证 Ctrl+V 与 Ctrl+Shift+V。必须在带有本次输入标记的第一条聊天请求里恰好收到一张 32×16 图片，逐像素符合预期；后续请求不能再带图片。OpenCode 给会话生成标题时可能另外发送同一张图；单独计数，不能替聊天请求证明贴图成功。启动草稿的未通过项仍计入总数。首次显示文字只标记发键时机，不能证明能接收图片的编辑器已经就绪；这里的失败本身不表明终端丢键。见[系统 ConPTY、WinPTY 与同稿重试的实测对照](../research/codex-bitmap-requests.md)。 两个 Codex 启动用例若未在 20 秒内看到附件，会保留原失败并将同一草稿按一次回车提交到本地回环服务。汇总单列这次提交是否为纯文字、带一张正确图片，或没有取得目标请求。不会重复粘贴，也不据此补分；旧测试超时后未按回车的记录不能当作纯文字提交。

`suite=image-mixed` tests a real Codex editor after its idle redraw with a generated bitmap and an empty `CF_UNICODETEXT` alternative present together. Both shortcuts are delivered via API and physical keyboard; success requires one exact image in the submitted request. On the API runner, ten native child-input cases compare the same Paste action with DIB only, empty or nonempty Unicode/ANSI alternatives, reversed format order, whitespace and empty text alone. `suite=image-mixed-opencode` repeats the two real input paths in the pinned OpenCode client after its composer paints the typed marker; it does not use the Codex idle signal. The default and title-disabled OpenCode configurations retain the same one-image-in-one-request assertion; each request records whether it carries the pinned title instruction. The normal `picture-keys` suite also runs the child-input cases. This does not replace the startup-only or delayed bitmap checks.

`suite=image-reads` 使用相同的产物和固定 Codex，独立诊断启动与就绪阶段。剪贴板由隐藏窗口按需提供同一张 32×16 位图；先做格式可用性查询和两次读回原始像素的对照，再分别记录两种快捷键、Windows 第一次索取像素的时点、应用附件和服务端像素校验。`bitmap-gestures.json` 和 `bitmap-requests.json` 共用单调时钟。Windows 会缓存已提供的像素，本记录不能计数后续读取或单凭窗口句柄认定读取者。这个实验不替代普通剪贴板验收，后续手动重试成功也不改变第一次的结果。


`suite=image-files` 另外以只含 Windows 文件列表（`CF_HDROP`）的剪贴板交给同一产品，PNG 路径含空格和中文。首次绘出已输入文字和 idle 后分别在窗口接口、系统按键下测试两种快捷键；必须出现图片附件、服务端收到且只收到一张像素正确的图片。它不计入位图启动检查，也不以粘入了路径文字为通过。

同组的 `system / caption` 在测试项目名 `work` 出现在前台原生窗口标题后立刻实按一次快捷键，不等待客户端空闲、日志或额外重绘。它保留标题截图、按键记录和回环服务收到的图片；该观测只适用于这个客户端配置，独立于启动期与空闲期的原有验收。

`suite=image-reference` 在系统 ConPTY 与 WinPTY 上直接启动同一版 Codex，向其专用控制台写入原生接收端实测的四个按键事件，并核对送达本地服务的图片。此组不启动 Nemoterm，不计入产品通过数。

### pterm-memory

在同一台托管 Windows 上比较官方 pterm，以及 Nemoterm 的单标签和独立窗口分别使用 GDI、DirectX 运行同一 Codex 的内存。只复用指定构建，正序、倒序各一次。此组的稳定读数与产品压力测试的峰值分别报告。示例针对已归档的 `ba91594`：

```powershell
gh workflow run font-zoom-replay.yml --ref fix/legacy-key-modifiers-20261116 -f suite=pterm-memory -f source_run=44277391833 -f source_commit=ba91594a16628870d0a1ca116395475bba3640c5
```

[六次运行的数字和截图](../research/pterm-findings.md#同一台-runner-上的真实-codex-对照)。 当前预览另有[十次正反序对照](../research/pterm-findings.md#f564927-普通-codex-会话实际驻留了什么)。每次在启动 Codex 前、收到固定回复后，分别将前端的驻留页按自身 EXE、其他映像、私有分配和映射段分类，保留每类的私有页与可共享页数。后一次清单在普通工作集计数结束、窗口截图开始之前采集。

下载 `interaction-agents-<run>-<attempt>` 原始制品后，可用 `python scripts/review-codex-paste-receipts.py <archive.zip> --expect-commit <完整哈希> --output first-paste.json` 离线复核首次贴图。它分别检查刚能看到输入文字、已经收到 idle 并重绘两种时机，列出两个快捷键、两种输入途径的首个带标记请求和后续各请求的图片数。首次缺图仍返回非零；即使后续请求有图也不会追认首次成功。报告 v0 产品验收时分别列出两组：编辑器就绪后，首次提交必须恰好带上一张像素正确的图片；首次可见文字时的结果用来观察启动时序，不要求终端缓存或补发此次手势。

显式触发 `ci.yml` 的 `scope=full` 时，`agent-session-memory` 作业会等待本次单文件构建成功，再用这一份 EXE 执行多轮会话。需要单独复核历史制品时，仍可用 `font-zoom-replay.yml` 的 `suite=agent-session-memory` 和原始 `source_run`、`source_commit`。pterm、Nemoterm GDI 单标签和 DirectX 单标签各只开一次，先收到初始回复，再在该窗口连续提交 24 条不同的提示。每轮用 Windows 键盘输入数字，回环服务检查最新一条用户消息；确认子进程可见屏幕中出现本轮回复末行和独有的结束标记后，继续采样至少 5 秒。记录各轮前端的私有工作集、总工作集和私有提交量；GDI <20,000,000 字节、DirectX ≤30,000,000 字节按整段采样峰值验收。与上面的短会话是两个独立的工作负载，不替换已有记录。

在 `agents-grid` 的六个真实客户端／渲染器组合中，系统鼠标另从「中」的右半格拖到「文」的左半格；要求四格全部高亮、紧邻两格不变、Ctrl+Shift+C 复制为「中文」。然后仍须完成原有整条回复的选择、复制、粘贴与 HTTP 核对。该检查覆盖 160×48 并使用固定 Sarasa Light 字体。每次结果只对回放的那份 EXE 有效。

The six default-grid agent cases also exercise the live close-tab shortcut after copying a reply. The hosted controller clicks the native Cancel button, observes that keyboard focus returns to the same terminal child, physically types the submission prefix, pastes, and submits. No terminal click or focus repair is allowed after Cancel. Each receipt includes the button's pressed/capture state, restored foreground and focus handles, and the provider's digest of the complete prompt. The default-grid cases also type two extra `x` characters, erase them one at a time, verify that the clipboard still contains the selection, paste, and check the complete submitted prompt. Before pressing the next key, capture the owned visible renderer and require two equal glyphs, then the same first glyph and a blank, then two blanks. The three original screenshots and both glyph masks per frame are retained as PNGs and mask digests. To review the original PNG pixels and provider receipts again, run `font-zoom-replay.yml` with `suite=agent-pixels`, the product `source_run` / `source_commit`, and the `receipt_run` that exercised `agents-grid`. The review also produces two contact sheets, without launching a client.

The `picture-keys` replay also checks a generated bitmap-only clipboard under desktop VT keyboard negotiation. An actual ConPTY child compares all bytes from one default paste action, including requested key releases, between two input barriers. It covers classic Ctrl+V, kitty disambiguation/events/all, stack pop, xterm modifyOtherKeys levels 0–2, both xterm formats and kitty push/pop over an active xterm mode. Encoded cases must also match an ordinary unbound Ctrl+V down/up pair through the frontend. The independent native Windows key-event receiver still checks the real client output replay; the Codex image timing suite separately checks the HTTP image payload. All three workflows use the Windows family name identified when registering the pinned Sarasa Light font.

Use `suite=profile-sequence` on the exact EXE to replay the aggregate profile workflow: command-line profiles, environment, startup sizing, settings in both host modes, Cancel/keyboard recovery, and dialog checks. `suite=close-cancel` isolates the Cancel test. Native click receipts record changes in foreground, GUI-thread focus/capture, pointer hit and button state. The first unsuccessful click still fails; neither path repairs focus after a dismissal.

`protocol-reference.yml` with `family=font-ops` captures XTerm OSC 50 replies and actual cell geometry on a hosted X server. `font-zoom-replay.yml` with `suite=font-ops`, `source_run` and `source_commit` compares an exact Windows EXE on GDI and DirectX, using separate cold Sarasa Light and Consolas windows as glyph controls. The local `dist` folder is not a test environment.

`selection` 还覆盖 Ctrl+Shift 框选跨越普通行和 DEC 双倍宽度、双倍高度行；同一可见范围必须高亮并复制相应的整字，程序不应收到鼠标事件。参见[修复前后的检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-scaled-rows.md)。

`agents-grid` 的测试回复包含普通顺序和左右混排的内容。同一行还显示三个隔离的希伯来字形作为原生像素对照。先从系统鼠标拖选中核对两个被高亮的屏幕字符、两侧保护格及剪贴板的组合附标，再验证原有的中文宽字、整段复制、关闭取消和回贴提交。

`picture-keys` 的原生接收器分别对 Ctrl+V、Ctrl+Shift+V 核对整条 Windows 按键记录（顺序、扫描码、字符、修饰、重复数）。800 ms 后可重试读取测试进程发布的快照，但不能补发按键，迟到或多余的按键均使测试失败。VT 协商字节另行运行。`agents-grid` 在整段回复提交后，还会反向拖选新回复中的两个混排字符，把剪贴板换成只有图片的哨兵，再用 Ctrl+Shift+C/V 复制、粘贴。服务端必须收到含这两个字符的独立用户消息，不能混入邻格或丢失组合附标。

选区必须在应用只移动光标时保持可复制；应用实际改写选中字形时才取消。`suite=interaction` 的 `selection` 组在 Sarasa 和默认字体、GDI 和 DirectX 四个窗口中检查高亮、右键归属和原始应用输入。见[光标更新和选择记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-cursor-traffic.md)。

`suite=colour-input` 同时在 Ubuntu 24.04 的 `linux` terminfo 上实际运行 `tput initc` 和 `tput oc`，保存 16 种颜色和复原命令的原始字节及 `infocmp` 输出。Windows 的 GDI、DirectX 分别用一次或逐字节的 `WriteFile` 送入同一 EXE，每条命令紧跟可打印的 `@`，另以 OSC 4 设置和 OSC 104 复原作对照。检查子程序的原始回复、已绘制的一排色块、紧跟的文字以及鼠标接管时的 Shift 选区和显式复制。原始参考是 Linux 客户端输出，不代表 XTerm 支持 Linux 控制台的专用语法。

判断内置控制台是否同步时，使用子程序自己的 `ReadConsoleOutputW` 读取同一行、`GetConsoleScreenBufferInfoEx` 读取 16 项颜色；屏幕截图和 OSC 4 回复均不能代替这两次读取。分别保存初始 Win32 调色板和前端 profile 颜色，按各自的初始值验证复原。独立的语法回归还包含大写十六进制、无效颜色数字后的下一个字符，以及正常 OSC 2 标题内的 `R P1123456` 原文（由 `GetConsoleTitleW` 读回）。

`suite=palette-exit` 对同一 EXE 重放 DirectX 调色板栈单文件用例（Consolas，与原失败一致）。两台 runner 分别用进程内取帧和窗口外截图，每台独立启动三次。保留 101 组参考回复、像素核对、1,000 次保存/恢复、子程序见到结束请求和恢复控制台的时间；原始 10 秒退出期限不变。若超时，先记失败再采集该作业所属进程的诊断。

`suite=colour-input` 还重放 `22ed829` 记录中 Codex 输入乱序现场在颜色查询前实际发出的 VT。原生 `ReadConsoleInputW` 接收器与真实客户端分开：同一 EXE 分别在 GDI、DirectX 下向它粘贴完整标记；无查询的对照以及查询前、并发启动和查询回复后三种顺序都保留原始按键记录。完整状态回复将输入定界；只移除明确的回复后，用户字节须与基准逐字相同。

`suite=draft-product` 与 `suite=draft-reference` 分别在受测 EXE（GDI、DirectX）和独立系统 ConPTY、WinPTY 上运行固定版本的真实 Codex。每种窗口、每个时点各开三个新会话，区分首次可见输入框与一个完整回复后。独立宿主一次写入整段原生按键记录；产品使用发现接口粘贴和实按 Ctrl+Shift+V。输入按原样只提交一次，不因字符串出错而重试，保存屏幕、原始输出和本地服务的回执。[原始证据与输入边界](../research/codex-file-draft-order.md)。

`suite=paste-order` 用指定 EXE 在 Windows 原生接收端连续粘贴 4096 行和第二段 Unicode 文本；GDI、DirectX 各开关一次 bracketed paste。按原始 UTF-16 比较全部文字、回车、顺序和两段边界；失败也保留期望值和实收值。同套检查也在托管桌面实按两次 Ctrl+Shift+V。原生接收端确认已收到第一段的开头，才替换剪贴板并实按第二次；报告单列第二次按键前的接收字节数。 [修复前后的原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/consecutive-paste.md)。

`selection` 分组还检查 Shift 按下与第一次拖动之间的滚屏。先确认原行七个字格的像素移到了目标行，再松开并核对终端实际高亮、系统剪贴板、子进程原始输入。普通和矩形选区、向上和向下、GDI 和 DirectX、Sarasa 字体和空 profile 都单独记录。[实际窗口、剪贴板与精确镜像回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-during-scroll.md)。

`protocol-reference.yml` 的 `family=regis-first-expose` 为每个输入终点启动独立上游 XTerm，只在最后做一次完整重绘，先核对原始序列、回复与首帧再比较重绘。见[七个历史差异的逐帧核验](../research/regis-first-expose.md)。

`suite=regis-frame-pair` 用同一份 EXE、Sarasa Light 和实际 GDI 窗口回放这些终点。每个终点一个新的 Windows 进程；使用固定 6×13 像素的字符格、原序列及状态应答，保留重绘前后 160×120 区域的实际像素、固定观察期内各次采样的哈希及差异数。这个回放只测整段写入；文字对照检查字形可见和重绘不变，保留两套字体的像素差异。历史像素不相等仍返回失败。
`protocol-reference.yml` 的 `family=regis-bank-start` 独立收集初次共享、私有、RIS、DECSTR、ReGIS 先用、私有 ReGIS 先用及显式赋色七个场景，两种传输均保留。`suite=regis-bank-start` 在实际 GDI 窗口复用同一输入，以原版画面核对完整区域及四个色号的色块。



`selection` 组还检查放大行跨行复制：先让 80 列窗口显示 `WXYZOFFSCREEN`，再由应用把这一行改为倍宽。用另一条从未写入 `OFFSCREEN` 的放大行做逐格截图对照。Shift 从可见的 `WXYZ` 拖到下一行的 `END` 后，检查整段高亮、系统剪贴板文字和应用实际收到的字节。普通宽度保留标记；倍宽、双高的上半行和下半行都只能复制可见文字。GDI 和 DirectX 均执行，带标签的窗口还用 Windows 系统输入重复倍宽用例。复跑：`suite=interaction`、`groups=["selection"]`。原试用版的[失败记录](https://github.com/xiongnemo/nemoterm/actions/runs/44672824926/artifacts/14601013448)保留用于前后对照。见[两版系统剪贴板和逐格截图结果](../research/selection-scaled-copy.md)。

同一组还分开测试“先按住鼠标，再改变行宽”。例如在普通行的 `E` 上按下 Shift+Ctrl+左键，应用随即把行改为倍宽，松手位置是放大后的 `G`；窗口高亮、右键和 Ctrl+Shift+C 都应得到 `EFG`。如果按下的字符已完全移出屏幕，后续拖动和松手不应发送给应用，下一次独立右键则应交回应用。用例同时覆盖缩回普通宽度、倍宽行改为相同宽度的双高下半行、只改另一行，以及启用左右边距导致的行宽复原。`tests/selection_rendition_press.py` 保留松手前后的截图、剪贴板文本和原始鼠标字节；复跑入口与上一段相同。[原试用版 `f073c8d1` 的同组原始失败](https://github.com/xiongnemo/nemoterm/actions/runs/44676272043/artifacts/14601714654)为 12/34：倍宽矩形在 `E` 按下、`G` 松手会错误复制 `CDEFG`，复原普通宽度会复制 `GHIJ`；已不可见的起点也可能选中不相关的一段。

CI 在 `selection` 组单独读取这 34 项的原始 PNG 和剪贴板/鼠标回执。它核对每份文件的 SHA-256、变化的实际屏幕格、选区外没有变化、两种复制手段和下一次右键的接收方。下载原始 `interaction-selection-…` 制品后，也可以用 `python scripts/review-rendition-selection.py <archive.zip>`（Pillow）离线复核。逐项结果写入 CI 制品的 `interaction/rendition-review.json`。 [`f2f553b9` 的 34/34 结果、前后截图和原始回执](../research/selection-rendition-press.md)。

`selection` 另覆盖滚动分栏穿过双向文字的场景：先在原图与滚动后截图中用字格底色定位同一字，再检查系统剪贴板和应用实际收到的字节。分开记录窗口消息和 Windows 实按 Shift、鼠标、Ctrl+Shift+C。[分栏选区前后对比](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-split-scroll.md)。如果按下的字被整个滚出或被栏边截断，要同时检查松手后无高亮、右键归应用、后续新选区仍可复制。[原始失败与检验步骤](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-discarded-scroll.md)。

`protocol-reference.yml` with `family=column-press` captures 26 logical cells on each of 28 rows after ICH, DCH, SL, SR, DECIC and DECDC or the corresponding unedited control. `font-zoom-replay.yml` with `suite=column-cells` compares an exact executable with the original XTerm replies, retaining each different column. `suite=interaction`, `groups=["selection"]` separately checks the rendered highlight, copied text and raw mouse input during a held Shift gesture. The upstream cell checks do not prescribe Windows mouse bindings. The full workflow also runs the two column checks on its exact product. The 72-row edge audit records all 1,872 replies and independently checks that all surviving source glyphs remain whole; the separate 28-row literal XTerm comparison still fails on any difference. See [wide glyphs at a delete margin](../research/column-edge-integrity.md).

The same `suite=column-cells` replay checks horizontal edits through two independent interfaces on GDI and DirectX. A child queries all 26 cells of a row using VT checksums and reads the same row using `ReadConsoleOutputW`, including the wide-character lead/trailer flags. The 120 cases per renderer include insertion and deletion at the cursor, pane-wide scrolling, split glyphs, an oversized count and no-op controls outside the pane. Both raw rows are kept even when the strict XTerm comparison fails. The `selection` replay separately holds Shift and the mouse as `中U` moves to the right margin, then checks the visible glyphs, both copy bindings and the child's input.

The same replay runs `tests/column_rectangle_paste.py` on GDI and DirectX even if the literal XTerm cell comparison failed. It holds physical Ctrl+Shift and the left button on the second cell of U+20000, deletes three columns across both rows, and drags onto a decomposed accent. Compare both edited rows with literal reference text, the row-specific highlights with the cell bounds, the two Windows clipboard gestures with exact UTF-16 text, and the bracketed paste against the UTF-8 bytes read by the child. Raw evidence is under `research/column-rectangle-{gdi,directx}` in the artifact.

For a block that was already released before the edit, the same job runs `tests/selection_block_row_edit.py --pane gdi` and `--pane directx`. The coloured marker must reach the destination before sampling. The fixture checks each row of the highlight, the Windows clipboard sequence and content, and the raw child input after a fresh key. Each renderer covers the default right button (11 cases), explicit Copy (8) and optional copy-and-paste (11), including a partial-height edit and a split wide character. See `research/column-pane-*.json` and the captured `*-edited.png` files in the Actions artifact.

`suite=interaction`、`groups=["selection"]` 还验证鼠标按住以后，应用用 `DECFRA` 填充矩形或用 `DECCRA` 复制矩形的情况。复制源区后，原字仍可选；目标处的宽字、组合重音或普通字被替换时，这次拖选应取消，下一次右键交给应用。覆盖 GDI 和 DirectX 各两种字体/窗口配置，共 48 个窗口消息手势；两个 Sarasa 标签窗口另有 8 个系统手势。用 `python scripts/review-rectangle-press.py <interaction-selection.zip>` 可只读复核每个实际截图中的高亮列、两种复制方式以及子进程接收的完整字节；结果不并入此前的候选版分数。[修复前后 20/56 与 56/56 的原始窗口对照](../research/selection-rectangle-redraw.md)。

`suite=regis-erase` 用同一个 Windows 单文件分别打开 GDI 和 DirectX 窗口。在备用屏画一条 101 像素长的红线，在主屏画绿线；先往返切屏确认两幅图保留，再用逐行擦除和滚屏清完整张高 8192 像素的图。两端检查状态回复，并核对再次切回和强制重绘后红线的每个像素。传 `source_run` 和完整 `source_commit` 即可重放指定 EXE；`ci.yml scope=full` 也会运行此项。[两版窗口截图、组件分配记录和原始失败](../research/regis-sparse-erase.md)。

`suite=scrollback-modes` 也会检查应用发送 ED 3 或 DECSED 3 清空历史时的本地选择。分别在按下、拖动、松开后发出请求，并用禁止远程清历史的 profile 作对照。拖选中收到的应用输出会排队：先确认子程序已写出清屏请求和 DSR、旧画面仍有高亮且尚无回复；实按松手后才应清历史并收到一次回复。另两例在鼠标仍按住时直接分派本地 Clear Scrollback 菜单命令，分别检查被删的历史行和保留的当前行；该命令不受远程清历史权限限制。两种渲染器都会记录滚动条、屏幕上的行号色标、选区像素、系统剪贴板、子程序实际收到的按键与按钮，以及下一次新拖选是否正常。

`suite=regis-window` 还会在默认标签窗口用实际键鼠验证图形旁的 Shift 拖选：TUI 开启鼠标上报，左键按住 `A中Z` 时插入字符，或在 Ctrl 矩形选择时把文字向左滚动。GDI、DirectX 分别采集按下前、文字移动后和松手后画面。除了复制文字，还检查同行两段红线、四格高亮、子程序收到的字节、默认右键仅复制和正常退出。[这四个实际窗口的运行记录](https://github.com/xiongnemo/nemoterm/actions/runs/44694679112)。

`protocol-reference.yml` 的 `family=regis-text-motion` 用 XTerm 412 对照八种横向文字编辑和一个空操作。两种传输方式均读取两行共 14 个字符的校验值，并保留编辑前、编辑后、强制重绘后的原始截图。`font-zoom-replay.yml` 的 `suite=regis-text-motion` 用指定的 `source_run`、`source_commit` 在 GDI 和 DirectX 上逐项核对同一输入、应答和画面。首次采集因未开放 GetChecksum 而失败（运行 `44691360396`）；[完整的参考记录](https://github.com/xiongnemo/nemoterm/actions/runs/44691719953)和该失败记录分别保留。

`suite=regis-presented-matrix` 对同一份 EXE 分别用 GDI、DirectX 回放 10 个终点，每种渲染器各跑整段写入和逐字节写入。采集目标是测试自己的终端客户区；DirectX 取实际子窗口，记录最初的尺寸同步。用红绿格交换验证画面会更新。写入次数、字节哈希、终端应答、重绘前后图像、原版像素差异及采集失败分别保留。[远程结果与制品](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-presented-matrix.md)。

The `selection` group holds Shift and the left button while the application erases text using ECH, EL, ED, DECSEL, DECERA and DECSERA. Clipboard changes, highlighted cells and subsequent right-button delivery are checked independently, including the protected, already-blank and wide-character cases. [Exact images and regression evidence](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-erase.md).

中途切换标签的场景另见[跨标签松开 Shift 拖选](https://github.com/xiongnemo/nemoterm/blob/ebbd444665d223d09e88895f93a7496b2d46e0cc/research/tab-drag-release.md)。`tab-clipboard-ownership` 用两个新窗口分别交换 GDI 与 DirectX 作为目标，检查目标原选区、来源未完成选区、窗口捕获以及双方的输入字节。这里的两个窗口分开运行，每次只有一对标签。

`selection` 组的 `bindings` 用例还验证右键粘贴后紧接回车的顺序。子程序开启鼠标上报和括号粘贴，显示 `!RUN!`。在“右键复制并粘贴”配置下，对 `RUN` 做 Shift 左键拖选，然后把右键按下、松开和 Enter 的按下、松开发给同一个终端窗口，中间不给顶层回调运行机会。检查系统剪贴板恰为 `RUN`，并在两次终端状态回复之间检查子程序依次收到 `ESC [ 200 ~`、`RUN`、`ESC [ 201 ~` 和一个 CR；最后一项不能跑到选区之前。`right-click-then-return.json` 同时保存 EXE 身份、预期和实收字节。这是可重复的消息顺序，不是对用户手速的测量。

同一 `selection` 回放还在应用开启鼠标跟踪时按住行尾的 `V` 或 `界` 的后半格，让应用左移该行后反向拖选。分别比对移动前后的整段字形、腾出的空格、分栏边界外的 `W`、松手后的高亮、Ctrl+Shift+C 和右键取得的 `中V` 或 `中界`，并核对手势没有漏送给子进程。原有 XTerm 412 逐格比对仍独立报告。[该 EXE 的 20 项实测与两幅高亮截图](../research/column-edge-integrity.md)。

`suite=unicode-boundary` 的 WinPTY 对照保留两种读屏结果：原始行读取和完整 `CHAR_INFO` 矩形读取；另行记录原始终端输出。普通视图的截止时间不变，之后重绘或切换 transcript 不能补算通过。[同一 EXE 的 5 项回放](https://github.com/xiongnemo/nemoterm/actions/runs/44550320946)及[原始制品](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/winpty-wide-claude-b3274ed.zip)：GDI 和 DirectX 的原生接收端逐字节收到相同的括号粘贴（含中文、分解重音及两个 Nerd Font 字符）。独立系统 ConPTY、WinPTY 和串行 WinPTY 中的真实 Claude 都提交了 NFC 文本。普通 WinPTY 此次在截止前通过逐格画面确认回复：当时没有可用的旧行快照，原始输出也未出现完整回复标记。串行 WinPTY 则先从终端输出确认。两者的活动缓冲区都记录了回复，旧读法均未记录到标记。这里的可见格只用于确认 ASCII 回复标记；输入字序另以原始字节和请求为准。

`suite=scrollback-modes` 在同一份 Windows EXE 上分别启动 GDI 和 DirectX，每种渲染器单独覆盖四种 `ScrollOnDisp` / `ScrollOnKey` 启动组合。先逐字节比较固定 XTerm 412 的 72 段模式应答，再滚到历史顶部，交替让应用写出一个字符或从 runner 的 Windows 桌面输入一个数字。用原生滚动条位置判断窗口是否回到底部，并核对子程序收到的数字。附加交互在子程序接管鼠标时按住 Shift 和左键，等待新行写入，再选择和复制历史中的 `HISTORY 03 中`，随后键入 `7`。记录独立区分复制留在历史、新输出留在历史和实际键入后跟随到底部。独立参考可用 `protocol-reference.yml` 的 `family=scrollback-modes` 重取。

同一回放还检查历史已满时的矩形选区：让应用接管鼠标，在最老三行用 Ctrl+Shift+左键框选五列，取一次剪贴板，再连续追加四行。每一步比对 GDI / DirectX 自身窗口的像素、独立标记的行号、滚动条位置和原有剪贴板，确认只删除已经滚出历史的高亮行。见[原始画面和逐行对照](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/scrollback-modes.md#滚动历史已满时的矩形高亮)。

### 多行剪贴板换行与括号粘贴

固定 XTerm 412 参考：`protocol-reference.yml`，`family=paste-lines`。托管 X11 的 `UTF8_STRING` 剪贴板经 XTerm 自己的 `insert-selection(CLIPBOARD)` 送入原始 PTY。17 个连续阶段的输入、两份模式回复和实际粘贴内容保存在[原始制品](../testdata/upstream/xterm412-paste-lines.zip)。

单 EXE 回放：`font-zoom-replay.yml` 的 `suite=paste-lines`，指定 `source_run` 与完整的 `source_commit`。`ci.yml scope=full` 也运行同一个检查。GDI 与 DirectX 分别对 CRLF、独立 LF 的 `CF_UNICODETEXT` 实按 Ctrl+Shift+V。子进程通过 `ReadConsoleW` 读取，记录重新编码为 UTF-8 的完整输入；用独立按下的 Enter 和 `7` 验证粘贴的边界。收集全部阶段后分别比较模式和输入。此测试覆盖文本粘贴，不使用图片剪贴板或 Codex。

### TUI 局部滚屏时的矩形选区

`font-zoom-replay.yml` 的 `suite=scrollback-modes` 和完整 CI 都在同一 EXE 上运行 `tests/selection_scroll_region.py`。让应用接管鼠标，只滚动中间四行，在固定和移动的行上实按 Ctrl+Shift+左键框选。用选区外每行不同的色块确认输出已经画到窗口，用背景像素逐格读出高亮，再比较原文、系统剪贴板和子进程输入。覆盖正反方向、整段替换、选区丢失和出现空隙的情况。

`--right-click` 分开启动默认“仅复制”、可选“复制并粘贴”和快捷键复制的窗口。检查裁剪后显式复制的文本与新高亮相符；若选区消失，未加修饰的右键应重新由应用接管，子进程能读到完整的 SGR 鼠标按下和松开。每次交互后以独立实按的字符标记结束，不用剪贴板已有的值单独证明操作成功。

同一套回放还用 `tests/selection_block_row_edit.py` 测应用在选区旁插入（ICH）或删除字符（DCH）。让应用接管鼠标，框选三行，从「中」的右半格拖到「文」的左半格，先复制，再只改其中一行。选区旁的色块移动后才取截图：如果选中的字没有动，高亮和右键复制都应保留；如果字被切开、单独移位或双向文字重排使框内换了字，高亮应取消，右键按下和松开都应传给应用。GDI 和 DirectX 各跑 14 例，含普通行、希伯来文和 DEC 双倍宽度行。`scrollback-block-edit-<renderer>.json` 记录逐格高亮、剪贴板和子进程收到的字节，每例保留编辑前、拖选中和编辑后三张原图。[旧版的原始失败记录](https://github.com/xiongnemo/nemoterm/actions/runs/44714350665)显示两种渲染器都误清了 8 次。

同一作业的 `--bindings` 在独立窗口中验证编辑后的两项操作：四次 `Ctrl+Shift+C` 只写入系统剪贴板；启用“右键复制并粘贴”后的六次右键，分别要求应用收到一次完整文本或一对鼠标事件。用实际按键作为接收结束标记，并比较子程序读取的完整 UTF-8 字节，包括行分隔。

### 逐字节粘贴（XTerm 私有模式 2005）

`protocol-reference.yml` 的 `family=paste-quote` 在固定的 XTerm 412 中直接读取 PTY 字节。默认 tty 的 literal-next 是 `16`（十六进制），另一轮将它改成 `1d`。每轮的 19 个阶段都包含中文、emoji、制表、两个连续换行和末尾界标；原件在 [testdata](../testdata/upstream/xterm412-paste-quote.zip)。例如 `中` 的 UTF-8 是 `e4 b8 ad`，打开 `?2005` 时默认 tty 收到 `16 e4 16 b8 16 ad`。包围粘贴的起止序列本身不加前缀。

Windows 用 `font-zoom-replay.yml` 的 `suite=paste-quote` 对指定 EXE 重放默认 tty 的记录。实按 Ctrl+Shift+V 后再单独按 Enter 和 `7`；一份记录保留终端实际写入输入管道的字节，另一份记录保留 `ReadConsoleW` 子进程读到的文字。逐字节加前缀后的中文不构成合法 UTF-8，不能从宽字符返回值还原原始字节。严格的管道对照涵盖全部样例；宽字符对照对可表示的样例同样严格，其他样例保留两种观察，不计作 Unicode 等价。此专项含只读管道观察器，不用于内存验收。

[第一次同图 Windows 记录](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-quote-before-42232a2d.zip)中，旧实现对 `?2005` 的查询全部回答“不识别”。另有 ConPTY 在滚屏重置时发出的带编号的内部光标查询，其回复会和粘贴同走一条管道。比较器保留未经处理的字节，并单独记录读取方向实际出现的查询与写入方向同编号的回复；只有一对一且未送到子程序的回复才从应用粘贴对照中扣除。未配对的输入不会被忽略。

[同一 EXE、同样按键的第二次回放](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-quote-pipe-42232a2d.zip)在四组中分别配对了七次查询。每组 19 个阶段的模式查询都不同（`?2005` 未识别）；在 8 个未启用引用的阶段粘贴字节完全一致，另 11 个缺少 literal-next。原始管道对照仍各只有 5/19 相同，未经改写；`ReadConsoleW` 对照各为 8/19。此处是旧产品的失败基线。

后续候选还须单独验证 Windows 应用实际收到的中文与 emoji。对不能由 `ReadConsoleW` 表示的原始 PTY 序列，游标控制和括号边界不变，要求子进程在每个 Unicode 字符前读到一次 literal-next，并读到完整字符；发送管道仍须逐字节符合 XTerm。不能用“前端发送正确”掩盖子进程收到替换字符或丢字。两项各自记录，后者是 Windows 可用性要求，不是声称 XTerm 的 PTY 返回 UTF-16。

`49f11579` 的[四组原始回放](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-quote-frontend-49f11579.zip)在应用粘贴管道上各为 19/19，真实 Windows 子进程却只有 8/19：`中` 被读成三个 `U+FFFD`，emoji 被读成四个。后续回放同时检查默认 `^V` 和 profile 指定的 `^]`，包括正式的模式查询、括号边界、CRLF/LF 和紧随粘贴的实按 Enter。在任一端比较失败都不算通过。

`font-zoom-replay.yml` 的 `suite=wsl-paste-quote` 将同一 EXE 放在托管 Windows 的 Ubuntu 24.04 中对照：原始 TTY 逐字节比对 XTerm 412 的剪贴板记录；启用 Linux 行编辑后，分别检查含中文、表情、Tab 和内嵌换行的完整一行及下一行哨兵。两种 renderer 和两个实际 `VLNEXT` 值分开记录。该检查也属于 `ci.yml scope=full`。

候选 `9b5e1111` 的[原生 Windows 回执](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-quote-native-9b5e1111.zip)覆盖两种渲染器 × 三组剪贴板（默认 `^V` 的 CRLF 和 LF、自定义 `^]` 的 LF）× 19 个阶段，**114/114**。逐项比对了模式回复、输入管道中的真实字节、`ReadConsoleW` 接收的数据和自然退出。比如粘贴 `中` 时，管道有三次前缀，宽字符应用只收到一个前缀和一个完好的 `中`。同一归档内附 REA 对该 EXE 的 PE 导入表，未发现 WebView 导入。

[同一 EXE 在托管 WSL1 的第一轮](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-quote-wsl-9b5e1111.zip)显示，这个结论不能直接推广到 Linux：Ubuntu 24.04 的 `/dev/tty1` 在四种组合里都给出正确的模式回复，普通粘贴正确；启用 `?2005` 后，原始读取在 `中` 前只有一次前缀，三个 UTF-8 字节之间没有前缀。按行读取拼接后的文字正确，但应用收到五次读取（按三个内嵌 LF 和两次手动提交分割），而非所需的两次。Linux 测试程序四次均正常完成；Windows 作业各留下两个进程，需要强制清理。上述差异分别保留。`wsl-paste-quote` 另在原生 Linux 和 WSL 的私有 `/dev/pts` 中直接写入同一份字节，并记录控制台要求的数据类型，供分层对照。

**哪一层改变了字节？** [同一测试脚本在原生 Linux 和 WSL1 的私有 PTY 及实际窗口中的记录](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-quote-hosts-9b5e1111.zip)把原版 XTerm 字节直接写进新建的 PTY，不经过 Windows 窗口。原生 Ubuntu runner 的八种对照均通过；WSL1 的同样八种只有四种通过。两种前缀的原始读取都能保留每个字节；但在 WSL1 中，即使直接写入正确的引用序列，内嵌 LF 仍会提前结束一次按行读取。Windows 端则是另一层：绑定到四个内置宿主的 ETW 记录共观察到 402 次 `API_GetConsoleInput`，`Unicode=1`，没有观察到 `API_ReadConsole`；这些是宿主记录的请求，不是字节读取。新诊断单独检查重定向的 `wsl.exe` 管道与 Linux 私有 PTY 能否双向保留任意八位数据；它不改变产品启动方式。启用跟踪的窗口回放保留了一次超时，其余三次自然退出，不能替第一次的强制清理改分。

重定向管道的[托管 WSL1 实验](../research/wsl-byte-transport-9b5e1111.zip)已完成：不启动 Nemoterm，Windows 通过 `wsl.exe` 的匿名管道向真实 `/dev/pts` 送入四组 XTerm 原始粘贴数据，以及一次从 `00` 到 `ff` 的全部 256 个字节。五次都从 slave 读到原字节，反向写回到 Windows 也完整，查询尺寸均为 160×48。仅重放此探针可选 `font-zoom-replay.yml` 的 `suite=wsl-byte-path`。它证明生字节有可行路径；产品中的默认 WSL 后端仍使用控制台。WSL1 自身的规范行编辑差异也不因更换传输而消失。

### 从资源管理器拖入 WSL，以及更改默认 shell 后再拖放

用 `font-zoom-replay.yml` 的 `suite=wsl-drop`、`source_run`、完整 `source_commit` 回放同一 EXE；`ci.yml scope=full` 运行相同的检查。GitHub 托管的 Windows runner 在 Ubuntu 中生成文件和目录，把 Windows 文件列表拖放或粘贴到真实窗口。检查原始 PTY 输入、Bash 能否用收到的路径读到两份原始内容，以及混入另一发行版时是否整批拒绝。显式指定发行版与默认发行版各有覆盖。另开实际 Windows PowerShell，在 Profile Settings 中保存 cmd 为默认 shell；当前 PowerShell 和随后打开的 cmd 必须用同一 profile 分别读到对应文件的随机内容。两组都保留 GDI 和 DirectX 结果。`tests/drop_profile_shell.py` 在发现窗口后立即发送一次命令，不重发；另一次 `--after-prompt` 启动独立 profile，等实际 PowerShell 或 cmd 提示符出现，再分别在改设置前、改设置后和重开时拖入文件及目录。成功条件是读到文件内随机内容、列出目录中随机文件名。两次分别留档，不用后者覆盖冷启动失败。原始失败：[资源管理器路径的旧版对照](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/wsl-share-drop-before-9b5e1111.zip)。

### 原版 pterm 的真实窗口与图片粘贴

`font-zoom-replay.yml` 的 `suite=pterm-images` 在同一台托管 Windows runner 上比较官方 pterm 0.85 窗口和指定 `source_run`、`source_commit` 的 Nemoterm GDI 窗口。二者使用独立 profile、相同字体与网格、同一版真实 Codex 及本地测试服务。每个快捷键与时点都从新进程开始；实际按一次 Ctrl+V 或 Ctrl+Shift+V，分别记录窗口附件、服务端收到的图片数及其像素、剪贴板与进程退出。首次可见输入只定义收集时点。完成一轮的 Ctrl+V 是两端的阳性对照。此可选对照不改变产品交互报告的通过数。

### 微软 Windows Terminal 的真实窗口与图片粘贴

用 `font-zoom-replay.yml` 的 `suite=wt-images`，并指定保留了单文件制品的 `source_run` 和完整 `source_commit`。同一台托管 Windows 上启动十个独立会话：微软原版 Windows Terminal 的默认绑定与 Nemoterm GDI 各测两个时点、两个快捷键；另外两个会话只取消 Windows Terminal 对 Ctrl+V 的绑定，让应用接收这个键。两个时点分别为输入框首次回显测试文字，以及上一轮回复已经显示。

从 `windows-terminal-images-<run>-<attempt>` 下载 `wt-images/summary.json` 和各窗口提交前的截图。每例只按一次贴图键、只提交一次目标草稿；以请求所带图片数和像素判断结果。没有发出目标请求的窗口不能计为「收到 0 张图」。在默认绑定下没有附件与在按键转交给应用后没有附件是两个独立结果。微软窗口的缓冲区读到附件时另外保留约 250 和 1000 毫秒后的两帧；实际采集时刻记录在 `capture.frames`，中间不补发按键。这个对照不改变产品的 81 项交互验收。[两轮结果、画面与原始制品](../research/codex-bitmap-requests.md#微软-windows-terminal-的真实窗口)。

核对真实全屏客户端对宽字符的选择，可下载同一运行的 `interaction-receipt-agents-grid` 与 `interaction-agents-grid` 两份 ZIP，再执行 `python scripts/review-agent-wide-selection.py <receipt.zip> <surfaces.zip> --output <新目录>`。这条命令只读现有制品；它核对两个 ZIP 的产品与夹具身份、子应用接管鼠标的原始输出、十次系统键鼠选择的剪贴板，以及「中文」四格和两侧背景的原图，再导出对比图。

The tabbed `selection` cases also change the top-level window height while the application owns mouse reporting. Real Shift/left-button and Ctrl+Shift/left-button gestures cover an unchanged main row, main rows pushed toward history, a surviving alternate-screen rectangle and an alternate-screen press on a discarded row. `height_selection` records the client geometry, selected pixels, explicit keyboard copy, right-button clipboard/child bytes and full gesture input. `width_selection` additionally checks a released stream when widening the alternate grid, a held rectangular selection when narrowing it, and a press on a column that actually disappears. Each resize uses the new client width for pixel comparisons. The separate `reflow_selection` cases start with `|ABCDEFGH|` near the right edge of the main screen and an untouched reference copy at the left. They physically select, resize from 80 to 74 columns, then back to 80. The released stream and reverse held press must track `CDEFG` across a soft wrap; a block entirely to the right of the break must track `EFG`, and a block split into incompatible columns must stay cancelled on widening. Check the narrow and wide screenshots separately, along with mode replies, shortcut and right-click copy, and the child’s raw mouse input.

[Before/after height-selection evidence](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/selection-height.md).

For an exact-image Windows quoted-paste exit diagnostic, run `font-zoom-replay.yml` with `suite=paste-quote-exit`, `source_run` and `source_commit`. Each renderer opens six independent windows for the same three inputs, with and without the pipe observer. Both arms require mode and wide receiver bytes, native input and natural exit within the original ten seconds; only the instrumented arm also measures the frontend pipe. A missed deadline remains a failure even if the process subsequently exits. The diagnostic additionally captures an owned-process minidump only on such a miss. [Product and fixture identities, observed windows, raw receipts and limits](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/acceptance-6072ebc9.md).


`suite=taskbar-progress` 在 GDI 和 DirectX 各启动真正的 Windows 子程序，交替以 BEL 和 ST 结束 OSC 9;4。它逐步比较实际标签栏的进度长度、颜色及未知进度条纹，包括重置和非法输入。旧版 `6072ebc9` [首次对照](https://github.com/xiongnemo/nemoterm/actions/runs/44602298022) 每种后端均仅通过 5/16 项（都是应为空白的对照），11 个应有标记的步骤实际上也全空白。独立桌面检查记录 Explorer 的 TaskbarButtonCreated 通知，以及独立窗口、同窗前后台标签和关闭后台标签后 ITaskbarList3 调用的返回值。没有真实 Shell 回执将使此项不通过；回执也不等同于截图看到了 Explorer 图标。

`suite=taskbar-memory` 在相同单文件 EXE 上保留两标签任务栏进度（正常 60%、暂停 25%），执行 160×48 的 Kitty Unicode、Sixel、历史和窗口大小压力场景。在采样前后分别核对真实 Shell 的状态。原有六种工作负载及 GDI 和 DirectX 的内存门限保持不变。

[第一次启用进度的内存回放](https://github.com/xiongnemo/nemoterm/actions/runs/44604429748)因托管桌面过小，在采样之前退出：GDI 为 123×32，DirectX 为 99×33。没有从这次失败推断内存。后续回放与原满屏验收相同，先选择远程显示器报告支持的模式，保持 160×48 断言，最后恢复并记录原显示配置。

`font-zoom-replay.yml` 的 `suite=wsl-relay-paste` 在托管 Linux 上编译独立的 x86-64 PTY 转接器，校验同一份制品在 Ubuntu、WSL1 上的字节与进程行为，再用指定的 Nemoterm EXE 在 WSL1 的真实窗口实按 Ctrl+Shift+V。Linux 接收器记录 PTY 名称与其直接父进程的二进制散列，区分实际走转接器与意外回到系统控制台。GDI、DirectX 均保留原始模式回复、逐字节输入和按行读取结果；原 `wsl-paste-quote` 使用默认 ConPTY 的测试独立保留。两者均纳入 `ci.yml scope=full`。

该回放的退出检查以 2 秒为限。超时后保留同一批进程句柄再观察 16 秒，记录它们是否自行退出。`result.json` 的 `job_at_ready`、`job_after_exit` 记录所属进程的名称、创建时间和可取得的完整路径；`cleanup` 保留实际超时和是否兜底终止。`wsl-paste-exit-controls.json` 在同一 runner 上分别直接启动 WSL，以及启动 WSL 加转接器；两者都没有 Nemoterm 窗口。检查退出时请与原始粘贴字节、每次按行读取的边界分别计分。

使用 `builtin` 的窗口还会分别核对 PE 释放到带空格的会话临时目录的文件、Linux 父进程和同次 Linux 构建的 SHA-256，并在正常关闭后确认临时 ELF 已删除。

[WSL1 原始字节、按行边界与关闭测试的逐项结果](../research/wsl-relay-window.md)。

`suite=wsl-relay-vim` 使用同一份单 EXE 的内嵌 WSL PTY，在真实 Vim 与 tmux 内的 Vim 中分别重放鼠标、Shift 强制选区、矩形复制、粘贴及窗口缩放。验证 guest 的 PTY、父进程与临时文件的实际散列，以及退出后临时文件的清理。

`suite=paste-lines` 还会在托管 GDI 和 DirectX 窗口中用延迟提供 `CF_UNICODETEXT` 的所有者检查连续粘贴、回车和后续按键的真实顺序，以及超时放行与忽略迟到的结果。见[修复前后的按键、内容与时序](https://github.com/xiongnemo/nemoterm/blob/408a251dca608961d936f0200001cdd2f649079b/research/paste-key-order.md)。

在支持配置方案选择 WSL PTY 的构建上，`suite=wsl-relay-vim` 还会从普通命名 WSL Bash 配置启动，实际点击 Profile → Shell 复选框并保存。在原 shell 保持运行时实按 Ctrl+Shift+T，核对新标签的 Bash、TTY 和父进程文件散列，并检查关标签后原 shell 仍在。重新打开配置、关闭选项以及临时改用 Windows PowerShell 都独立检查。产品进程不继承 `NEMOTERM_WSL_PTY_RELAY`；`research/wsl-transport-profile/result.json` 记录每一次切换及自然退出。测试是否通过以对应 EXE 的回执为准。

`suite=backarrow` replays the Backspace mode query, the `kbs` capability and physical Backspace, Ctrl+Backspace, Shift+Backspace and Delete on the exact Windows executable. Four fresh profiles use the 64 observed steps from XTerm 412 (`protocol-reference.yml`, `family=backarrow`, run `44737657869`). The child records query replies and key bytes separately; a physical `z` delimits input before the final status request. The original literal comparison stays in the report. Use `suite=backarrow-review` with the originating full CI run and product commit to recheck existing Windows input without starting the terminal again. `family=backarrow-pinned` repeats the same gestures using the ncurses source embedded in Nemoterm. `scripts/review-backarrow.py` reads the two raw XTerm captures and the unchanged Windows child streams and scores the mode, decoded `kbs`, key and literal wire individually; it requires all 64 matched-database interactions. The distribution and pinned XTerm runs differ on all 32 Terminfo-keyboard query replies, but agree on the 32 default-keyboard interactions. The same replay also checks one native cooked reader before and after a VT-aware application: both `ReadFile` and `ReadConsoleW` read each backarrow mode, and native line editing must remove a typo both times.

The same job exercises Win32 character messages independently of physical key-downs. `tests/character_repeat_window.py` sends `WM_CHAR`, `WM_SYSCHAR`, `WM_IME_CHAR` and `WM_UNICHAR` to the owned Unicode window with an explicit repeat count. Classic UTF-8 and Kitty text events are compared between ordered status replies from a real `ReadFile` or `ReadConsoleW` child; `backarrow-character-repeat.json` retains both streams. `agents-grid` also observes a single `WM_CHAR` with `中` and count two in the actual composers. It saves the presented double-width glyphs before and after each physical Backspace. This checks message handling, not the choice of Windows input method or how often Windows coalesces a held key.


`suite=column-modes`（`font-zoom-replay.yml`）在能完整容纳 132 列 Sarasa 的托管桌面上逐项比较 `TERM` 应答、Win32 窗口尺寸和子程序查询到的控制台宽度。它对照 `protocol-reference.yml` 的 `family=column-modes`：六种新会话，每种 22 个阶段；本地不准改尺寸以及 `-132` / `+132` 覆盖 profile 各自单独计分。见[上游、旧版和实测差异](../research/column-modes.md)。 程序可见的文字另用 `ReadConsoleOutputW` 核对：同一子程序同时读四个普通 ASCII 格、原生光标、窗口尺寸和前端协议回复。另有 Save and Apply 后在同一会话禁用／重新允许的检查。

`tests/inband_resize_window.py` runs in the same suite. Each renderer opens a standalone window and a tabbed window. The child subscribes with `CSI ? 2048 h`, then reads reports after a real window resize and font zoom. Compare row/column counts with the native child console and pixel dimensions with the measured terminal client area. The child also records the Win32 grid immediately after each input read: the chunk that completes the final size report must already see the reported grid. The final physical `9` keystroke bounds each observation, including checks for silence after unsubscribe or reset. Results are in `column-mode-inband-*-result.json`.

`tests/page_size_selection.py` 在同一工作流中检查程序请求的行列数相同、改变或被 profile 拒绝时，Shift 选区与右键复制是否仍然有效。GDI 与 DirectX 各 14 个实际窗口；[原始截图、剪贴板、子进程回执及 XTerm 412 的尺寸策略](../research/selection-page-size.md)。

同一工作流用 `tests/column_mode_native_readback.py --saved` 检查应用临时改变列宽、改宽权限或是否清屏，再恢复先前状态的行为。每种渲染器有三组 17 项与[原版 XTerm 412 的逐字节回复](../testdata/upstream/xterm412-saved-column-modes.zip)比较，另有 17 项检查本地禁止改宽。每一项还从 Windows 子程序读回同一行文字和光标。`tests/column_mode_selection.py` 在应用启用鼠标报告时实际按 Shift 拖选 `A中Z`，分别验证普通改宽、恢复列宽及清屏后显示的选区；保留时还会实际按 Ctrl+Shift+C 核对剪贴板。


如单文件任务在 `close-host` 超时并生成小型转储，`font-zoom-replay.yml` 的 `suite=profile-dump-single` 在远程只读解析原始文件；`tabs-close-replay.yml` 的 `fixture=profiles-single-pair` 在原始源码和 EXE 上交替运行 Frida 观察和不注入的窗口接口观察，`repetitions` 指每种方式分别执行几次。见[一次超时与成对复测](../research/profile-close-dc8b6913.md)。

`font-zoom-replay.yml`, `suite=tab-hover`, runs real pointer and keyboard input on a GitHub-hosted Windows desktop against the isolated source-built single EXE. Pass the source run and commit as above. To replay the same four sides on a failed MSVC renderer package alongside it, also pass its full `diagnostic_sha256`. Each side captures the visible popup before/after a hidden update, records both children’s ordered input and the copied selection, and reports the active renderer. For keys typed while hovering and after switching tabs, require the intended child to report the exact new bytes before asking either child for the next DSR. Both children must still match the complete ordered byte stream after that DSR. The [earlier right-side failure](https://github.com/xiongnemo/nemoterm/actions/runs/44680462961/artifacts/14603279842) retained the `8` in the intended child but after the independently requested DSR reply. The [same-executable replay](https://github.com/xiongnemo/nemoterm/actions/runs/44681759148/artifacts/14604248146) then passed on all four sides. Each preview changed from red to blue while the other tab kept keyboard focus; switching tabs delivered `8` to the new foreground child. Both children’s complete byte streams and the copied `Copy7` matched in every placement. [Both original CI archives](../research/tab-hover-6a8986d5.zip) include the PNGs and input receipts. All four replay windows used GDI fallback. GDI fallback is evidence for that fallback only; it does not validate hardware OpenGL. `ci.yml` also runs the product lane after building the source host.

The same job runs `tests/tab_right_click_chain.py` using physical Windows input on a right-side DirectX host and the pinned Sarasa Light font. Within the system double-click interval, compare a real double-click (`ABCDE`) with a fresh two-cell Shift drag after right-click copy (`BC`). A mode query must reach the child while the independent second press remains stationary; a held word selection defers that reply until release. The original failure on `355c73f8` and both timings are in [the Windows artifact](https://github.com/xiongnemo/nemoterm/actions/runs/44793137815/artifacts/14657368194). It also runs `tests/tab_rapid_wide_paste.py` with GDI and DirectX, once with the default right-click binding and once with copy-and-paste. On the alternate screen with mouse tracking and bracketed paste enabled, it checks both edges of the five-cell second highlight and the exact child's input stream, including the number of pastes and an ordered keyboard sentinel.

`suite=tab-hover` 还在隔离的单文件上运行 `tests/osc7_tab_directory.py`。打开「继承当前目录」，由子进程写入 OSC 7 并等到终端应答后，实按 Ctrl+Shift+T；记录原窗口复制的目录 URI 及新子进程自己的 `getcwd()`。GDI、DirectX 使用不同进程。每项先设置另一个有效目录，避免无效输入被忽略时碰巧得到预期值。控制项包括远程主机、相对路径和解码后含 NUL 的路径。原始记录见 `tab-hover-single-*/research/osc7-tab-directory.json`。

The same hosted run also tests tab middle-button gestures in fresh processes for all four sides. Releasing on another tab, pressing the add button with the middle button, cancelling capture, and removing the pressed tab before release must leave the surviving sessions and their keyboard focus intact. A genuine middle click on an inactive tab must close exactly that tab. The receipt records both HWND identities, the focused child’s input, and the process exit.

For Shift selection during synchronized output (`CSI ? 2026 h`), dispatch
`font-zoom-replay.yml` with `suite=sync-selection`, `source_run` and the full
`source_commit`. Each hosted Windows runner opens a tab with the pinned Sarasa
Light face. Inspect `sync-select-*.json` and the before/gesture/after PNGs:
the two live controls select `中文` and `明月`; the other cases change `中文`
to `明月` behind a frozen frame before a new Shift drag, shortcut copy of an
existing highlight, or default right click. The RGB chip outside the highlight
identifies the displayed frame. The clipboard must change, the child must
receive no gesture bytes. The first highlight must appear within the original
one-second presentation deadline. In the slow-drag case, keep the button down
past that deadline and verify the same old glyph outlines and exactly four
highlighted cells until release. Record the private working set while held. The raw mode query is retained after each
gesture for diagnosis.
The runner also checks replacing the private primary selection via permitted
OSC 52 while the highlight is still visible. The opt-in right-click paste must
deliver the same UTF-8 text as the system clipboard; after the new frame is
released, an unselected right click must reach the tracking application again.
The [first exact-image failures](../research/sync-selection-3308de91.md) are retained.

The two adjacent-edit cases change only a colour chip on the selected row. After the new frame appears, stream and rectangular selections must still highlight the four original cells. A new clipboard sentinel must be replaced by the next default right click, with no button report to the application. The replacement control requires the opposite result. The `review` job downloads both original Windows archives by artifact name and SHA-256 on a separate Linux runner, compares the PNGs, clipboard and child input for the same EXE, and uploads `sync-selection-review-<run>-<attempt>` with the results. The original Windows observations are retained even when the checks fail.
When replaying `suite=sync-selection`, the Windows observers also exercise the
first line in fullscreen. `tests/fullscreen_corner_selection.py` records real
Shift/left, mouse capture or system-menu ownership, the visible selection of
`A中Z`, a fresh Ctrl+Shift+C clipboard read, and the child’s bracketed-paste
bytes after Ctrl+Shift+V. Both renderers check standalone and tab strips on
all four sides. For top/left tabs the gesture starts at the first pixel of
the terminal pane; for bottom/right tabs and standalone it starts at the
monitor corner. A nearby unmodified click must reach the mouse-aware child.
A separate standalone control checks that an unmodified corner click still
opens the system menu. Each placement retains its own PNGs and result JSON.

`font-zoom-replay.yml` 的 `suite=tab-selection` 使用源制品的独立 EXE 和原始 profile 字体，在右侧标签栏、GDI 下重跑整个选区脚本。若终端状态回复超时，制品保留等待期间的采样、松开鼠标前的最后读数及清理时的读数；之后到达的回复不改变测试失败结果。

同一专项还保留 `repeat-cell-stream` 和 `repeat-cell-block` 的三张原始画面：按下前、字符被应用移动后、拖选并复制后。`scripts/review-stationary-selection.py` 从 PNG 单独核对 `KLM` 是否平移两格、选中行及上下邻行中是否仅三个目标格发生高亮变化，同时核对应用收到的原始字节和两种复制结果。这两个重复坐标的用例通过窗口消息触发。已有的系统实按用例仍单独列在 `horizontal_press_system` 中。

`suite=agent-pixels` also runs `scripts/review-character-repeat.py` on the original agent archives. A hosted Linux runner authenticates the source EXE and both archives; the reviewer checks per-frame digests, measures ink separately in the four displayed half-glyph cells and verifies that the surviving glyph is identical, both erased cells contain no ink beyond the caret background, and the real client submitted exactly the expected prompt. All ten windows must supply all three stages. Incomplete attempts retain their available frames and fail; a historical fixture without this probe supplies no proof of character repeats. `character-repeat.json` keeps that count separate from other pixel and binding checks. [Original controls and outcomes](../research/character-repeat.md#此-exe-的完整交互成绩).

`suite=agent-bindings` 在单独的 Linux Runner 上读取 `agents` 分组已经上传的两份制品，并与指定 `source_run` 的 EXE 和构建清单核对身份。它分别复核 Codex、Claude Code、OpenCode 在 GDI 和 DirectX 下的 18 种系统输入交互：检查客户端开启鼠标跟踪的原始输出、按键和鼠标事件的顺序、Shift 选区原图中每格高亮及两侧边界、剪贴板和本地服务实际收到的完整 Unicode 提交。默认右键后必须另按粘贴键；可选复制并粘贴不需要补按。此项不启动客户端或替代整套交互验收。参数与 `suite=agent-pixels` 相同，`receipt_run` 指含 `agents` 分组的那一轮。

`suite=frontend-memory-review` 在 Ubuntu 托管 Runner 上复核同一个 `scope=full` 构建的四份原始制品。不重开终端：先校验 EXE 和制品哈希，再从 pterm/GDI/DirectX 各 24 轮 Codex 对话，以及 GDI/DirectX 各六种 160×48 满屏负载的逐笔采样重算私有工作集、总工作集和私有提交峰值。GDI 私有工作集须小于 20,000,000 字节，DirectX 须不超过 30,000,000。报告保留原始制品编号和哈希；缺样本、身份不符或超限均不通过。
