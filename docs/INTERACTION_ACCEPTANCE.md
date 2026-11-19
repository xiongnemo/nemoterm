# 远程测试与交互验收

所有自动测试在 GitHub-hosted runner 上执行。开发电脑只编辑源码、提交、调度 Actions 和下载证据；不需要启动测试终端、接管焦点或修改本机剪贴板。

这里的 xterm 兼容性指应用在 `TERM=xterm` 或 `xterm-256color` 下能够正确交互。Nemoterm 的 Windows 启动代码设置 `TERM=xterm-256color`、`COLORTERM=truecolor` 和 `TERM_PROGRAM=nemoterm`。新构建通过进程内的 `WSLENV` 列表将这些变量传给 Linux 子程序；保留调用方已有的其他条目及显式方向。`shells` 组在实际 WSL Bash 中读取继承的 `TERM`，再用系统 `tput` 分别按默认条目和显式 `TERM=xterm` 移动光标，以终端返回的位置验收。这个检查覆盖名称、颜色能力查询和光标寻址；它不是所有 terminfo 能力的认证。 同一 shell 组还会在两个条目下启动真实 `less`：方向键下滚一行、Page Down 翻页、搜索到指定文本、退出后恢复先前的屏幕。逐步保存窗口文字和截图。原版 XTerm 的特定 ReGIS 逐帧对照单独报告，不代表普通 TUI 的兼容性；原失败记录仍保留。

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

`suite=font-ops` 在同一个 EXE 上分别验证 GDI 和 DirectX。先用独立启动的 Sarasa、Consolas 窗口核对实际字形和字符格，再验证标签间字体互不影响，以及从“窗口 → 外观 → 字体访问”保存配置和撤销权限。原始数据和首次失败见 [OSC 50 实测](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/osc-font-operations.md)。

`suite=rendering-settings` 在远程显示器实际支持的缩放比例下打开英文、简体中文“渲染”页，记录两个复选框的文字边界、与底部按钮的间距和窗口截图。分别检查标签窗口、独立窗口和运行中改变 DPI 的情况。

`suite=wsl-tui` 在单独的 Windows runner 上只安装所需 WSL 环境，记录直接运行的 `less` 与 `script` 记录器运行的 `less`，并区分窗口 API 和系统导航键。记录器的成功不能替代直接运行。

`suite=wsl-sixel` 用 Ubuntu 的 `img2sixel` 经 WSL 终端输出一张彩色 PNG，保存实际 Sixel 字节并用 `sixel2png` 独立解码。分别核验真实 GDI、DirectX 对应位置的每个像素、四边一像素范围、重绘及清除后的结果，同时保留工具版本、文件摘要和原始截图。工具只安装在 runner 上。

`suite=wsl-colour` 使用 Ubuntu 自带的 `tput` 和 `ncurses-term` 的三个条目画色块。分别记录真实 `setaf`/`setab` 字节，再检查 GDI 和 DirectX 的每一个色块像素、相邻空白、重绘和退出备用屏幕后的背景。`xterm-direct` 使用仅蓝色分量相差 1 的两个 RGB 值，能检出调色板量化。

`suite=wsl-vim` 在两个 TERM 条目和实际 GDI、DirectX 下启动 Vim。普通鼠标点击须改变 Vim 自己报告的光标，Shift 拖选须复制完整中文字且不移动 Vim 光标；窗口两次改尺寸后 Vim 与前端应报告同一网格；最后用快捷键粘贴，验证保存文件的 UTF-8 字节和退出后的画面。

`tabs` 分组的 `tab-clipboard-ownership` 在同一原生窗口打开两个 profile：GDI 标签使用默认右键仅复制，DirectX 标签显式设置右键复制并粘贴。两个子进程都打开应用鼠标报告和带边界的粘贴。用系统按键切换标签后，分别检查双方收到的完整字节、选区像素和系统剪贴板，区分当前输入与后台误收。

`suite=wsl-tmux-vim` 仅在 GitHub 托管 Windows runner 上运行，并记录 `wsl --list --verbose` 确认 Ubuntu-24.04 使用 WSL1。相同四组输入通过 tmux 到达 Vim；检查外层 `xterm` / `xterm-256color`、内层 `tmux-256color`、两次实际缩放，以及 Shift 拖选和矩形选择后 tmux 没进入复制模式。每次检查通过该次回放独占的 tmux socket 读取状态，不占用 Vim 的键盘输入。这项测试不使用开发电脑的 WSL，也不证明 WSL2 的行为。

`suite=profile-env` 可让 `--profile 名称` 和 Windows 跳转列表所用的 `@名称` 分别在父环境未设、设置了不同 `TERM`、已有全部 WSL 转发规则时启动子进程，读取其真实 `TERM`、`COLORTERM`、`TERM_PROGRAM`。

`f628d89` 单文件预览的[完整回放和内存数据](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/right-button-release.md#complete-interaction-replay)为 74/74。另一个 MinGW 便携构建出现[混合 profile 关闭超时](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/mixed-profile-close-f628d89.md)；`tabs-close-replay.yml` 的 `profiles-mingw` 和 `profiles-api-mingw` 使用原失败产物，分别回放带探针和内置自动化的操作。

`interaction` 可额外传 `-f 'groups=["shells","clipboard"]'` 只重跑指定组；留空执行全部。

`suite` 还可选 `single`、`dpi`、`font-bell`、`ui-regression`、`shell-lifetime`、`tcap`、`unicode-boundary`。回放允许源 run 的其他测试失败，但要求 source-host 构建成功；生产代码或构建配方与该产物不一致就拒绝回放。`tcap` 对同一单 EXE 检查数据库键盘的 1,293 条原生输入流及四种独立 SetTcap/GetTcap 权限组合；45 个 F35 用例缺少 Windows 物理映射，40 个 Shift+PageUp/PageDown 用例保留本地滚动绑定，均明确列出并由核心测试覆盖。查看结果用 `gh run view <run-id>`；下载证据用 `gh run download <run-id> --dir <new-directory>`。

`shell-lifetime` 在同一个准确 EXE 上交替执行 12 次普通 Git Bash 复制/关闭和 12 次带进程观察的复制/关闭，随后执行 2 次正常连接对照和 4 次受控的延迟客户端检查。完整 CI 也会自动调用此工作流。每次保留独立结果；原先的 3 秒回收门槛不变。失败后额外观察 12 秒并采集遗留进程的命令行、线程和转储，只用于诊断，不能把失败改成通过。已发现的关闭残留及修复验证见 [Git Bash 关闭调查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/git-bash-close-race.md) 和 [关闭后连接检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/closed-console-connections.md)。

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

`agents` 的六个普通位图用例区分首次出现输入文字、等待 Codex 就绪、Windows 实按和窗口接口。每个用例都在独立会话验证 Ctrl+V 与 Ctrl+Shift+V。必须在带有本次输入标记的第一条聊天请求里恰好收到一张 32×16 图片，逐像素符合预期；后续请求不能再带图片。OpenCode 给会话生成标题时可能另外发送同一张图；单独计数，不能替聊天请求证明贴图成功。启动草稿的未通过项仍计入总数。

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

`suite=agent-session-memory` 另用同一 EXE 执行多轮会话。pterm、Nemoterm GDI 单标签和 DirectX 单标签各只开一次，先收到初始回复，再在该窗口连续提交 24 条不同的提示。每轮用 Windows 键盘输入数字，回环服务检查最新一条用户消息；确认子进程可见屏幕中出现本轮回复末行和独有的结束标记后，继续采样至少 5 秒。记录各轮前端的私有工作集、总工作集和私有提交量；GDI <20,000,000 字节、DirectX ≤30,000,000 字节按整段采样峰值验收。与上面的短会话是两个独立的工作负载，不替换已有记录。

在 `agents-grid` 的六个真实客户端／渲染器组合中，系统鼠标另从「中」的右半格拖到「文」的左半格；要求四格全部高亮、紧邻两格不变、Ctrl+Shift+C 复制为「中文」。然后仍须完成原有整条回复的选择、复制、粘贴与 HTTP 核对。该检查覆盖 160×48 并使用固定 Sarasa Light 字体。每次结果只对回放的那份 EXE 有效。

The six default-grid agent cases also exercise the live close-tab shortcut after copying a reply. The hosted controller clicks the native Cancel button, observes that keyboard focus returns to the same terminal child, physically types the submission prefix, pastes, and submits. No terminal click or focus repair is allowed after Cancel. Each receipt includes the button's pressed/capture state, restored foreground and focus handles, and the provider's digest of the complete prompt.

The `picture-keys` replay also checks a generated bitmap-only clipboard under desktop VT keyboard negotiation. An actual ConPTY child compares all bytes from one default paste action, including requested key releases, between two input barriers. It covers classic Ctrl+V, kitty disambiguation/events/all, stack pop, xterm modifyOtherKeys levels 0–2, both xterm formats and kitty push/pop over an active xterm mode. Encoded cases must also match an ordinary unbound Ctrl+V down/up pair through the frontend. The independent native Windows key-event receiver still checks the real client output replay; the Codex image timing suite separately checks the HTTP image payload. All three workflows use the Windows family name identified when registering the pinned Sarasa Light font.

Use `suite=profile-sequence` on the exact EXE to replay the aggregate profile workflow: command-line profiles, environment, startup sizing, settings in both host modes, Cancel/keyboard recovery, and dialog checks. `suite=close-cancel` isolates the Cancel test. Native click receipts record changes in foreground, GUI-thread focus/capture, pointer hit and button state. The first unsuccessful click still fails; neither path repairs focus after a dismissal.

`protocol-reference.yml` with `family=font-ops` captures XTerm OSC 50 replies and actual cell geometry on a hosted X server. `font-zoom-replay.yml` with `suite=font-ops`, `source_run` and `source_commit` compares an exact Windows EXE on GDI and DirectX, using separate cold Sarasa Light and Consolas windows as glyph controls. The local `dist` folder is not a test environment.

`selection` 还覆盖 Ctrl+Shift 框选跨越普通行和 DEC 双倍宽度、双倍高度行；同一可见范围必须高亮并复制相应的整字，程序不应收到鼠标事件。参见[修复前后的检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-scaled-rows.md)。

`agents-grid` 的测试回复包含普通顺序和左右混排的内容。同一行还显示三个隔离的希伯来字形作为原生像素对照。先从系统鼠标拖选中核对两个被高亮的屏幕字符、两侧保护格及剪贴板的组合附标，再验证原有的中文宽字、整段复制、关闭取消和回贴提交。

`picture-keys` 的原生接收器分别对 Ctrl+V、Ctrl+Shift+V 核对整条 Windows 按键记录（顺序、扫描码、字符、修饰、重复数）。800 ms 后可重试读取测试进程发布的快照，但不能补发按键，迟到或多余的按键均使测试失败。VT 协商字节另行运行。`agents-grid` 在整段回复提交后，还会反向拖选新回复中的两个混排字符，把剪贴板换成只有图片的哨兵，再用 Ctrl+Shift+C/V 复制、粘贴。服务端必须收到含这两个字符的独立用户消息，不能混入邻格或丢失组合附标。

选区必须在应用只移动光标时保持可复制；应用实际改写选中字形时才取消。`suite=interaction` 的 `selection` 组在 Sarasa 和默认字体、GDI 和 DirectX 四个窗口中检查高亮、右键归属和原始应用输入。见[光标更新和选择记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-cursor-traffic.md)。

`suite=colour-input` 还重放 `22ed829` 记录中 Codex 输入乱序现场在颜色查询前实际发出的 VT。原生 `ReadConsoleInputW` 接收器与真实客户端分开：同一 EXE 分别在 GDI、DirectX 下向它粘贴完整标记；无查询的对照以及查询前、并发启动和查询回复后三种顺序都保留原始按键记录。完整状态回复将输入定界；只移除明确的回复后，用户字节须与基准逐字相同。

`suite=draft-product` 与 `suite=draft-reference` 分别在受测 EXE（GDI、DirectX）和独立系统 ConPTY、WinPTY 上运行固定版本的真实 Codex。每种窗口、每个时点各开三个新会话，区分首次可见输入框与一个完整回复后。独立宿主一次写入整段原生按键记录；产品使用发现接口粘贴和实按 Ctrl+Shift+V。输入按原样只提交一次，不因字符串出错而重试，保存屏幕、原始输出和本地服务的回执。[原始证据与输入边界](../research/codex-file-draft-order.md)。

`suite=paste-order` 用指定 EXE 在 Windows 原生接收端连续粘贴 4096 行和第二段 Unicode 文本；GDI、DirectX 各开关一次 bracketed paste。按原始 UTF-16 比较全部文字、回车、顺序和两段边界；失败也保留期望值和实收值。同套检查也在托管桌面实按两次 Ctrl+Shift+V。原生接收端确认已收到第一段的开头，才替换剪贴板并实按第二次；报告单列第二次按键前的接收字节数。 [修复前后的原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/consecutive-paste.md)。

`selection` 分组还检查 Shift 按下与第一次拖动之间的滚屏。先确认原行七个字格的像素移到了目标行，再松开并核对终端实际高亮、系统剪贴板、子进程原始输入。普通和矩形选区、向上和向下、GDI 和 DirectX、Sarasa 字体和空 profile 都单独记录。[实际窗口、剪贴板与精确镜像回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-during-scroll.md)。

`protocol-reference.yml` 的 `family=regis-first-expose` 为每个输入终点启动独立上游 XTerm，只在最后做一次完整重绘，先核对原始序列、回复与首帧再比较重绘。见[七个历史差异的逐帧核验](../research/regis-first-expose.md)。

`suite=regis-frame-pair` 用同一份 EXE、Sarasa Light 和实际 GDI 窗口回放这些终点。每个终点一个新的 Windows 进程；使用固定 6×13 像素的字符格、原序列及状态应答，保留重绘前后 160×120 区域的实际像素、固定观察期内各次采样的哈希及差异数。这个回放只测整段写入；文字对照检查字形可见和重绘不变，保留两套字体的像素差异。历史像素不相等仍返回失败。
`protocol-reference.yml` 的 `family=regis-bank-start` 独立收集初次共享、私有、RIS、DECSTR、ReGIS 先用、私有 ReGIS 先用及显式赋色七个场景，两种传输均保留。`suite=regis-bank-start` 在实际 GDI 窗口复用同一输入，以原版画面核对完整区域及四个色号的色块。



`selection` 另覆盖滚动分栏穿过双向文字的场景：先在原图与滚动后截图中用字格底色定位同一字，再检查系统剪贴板和应用实际收到的字节。分开记录窗口消息和 Windows 实按 Shift、鼠标、Ctrl+Shift+C。[分栏选区前后对比](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-split-scroll.md)。如果按下的字被整个滚出或被栏边截断，要同时检查松手后无高亮、右键归应用、后续新选区仍可复制。[原始失败与检验步骤](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-discarded-scroll.md)。

`protocol-reference.yml` with `family=column-press` captures 26 logical cells on each of 28 rows after ICH, DCH, SL, SR, DECIC and DECDC or the corresponding unedited control. `font-zoom-replay.yml` with `suite=column-cells` compares an exact executable with the original XTerm replies, retaining each different column. `suite=interaction`, `groups=["selection"]` separately checks the rendered highlight, copied text and raw mouse input during a held Shift gesture. The upstream cell checks do not prescribe Windows mouse bindings. The full workflow also runs the two column checks on its exact product. The 72-row edge audit records all 1,872 replies and independently checks that all surviving source glyphs remain whole; the separate 28-row literal XTerm comparison still fails on any difference. See [wide glyphs at a delete margin](../research/column-edge-integrity.md).

`suite=regis-presented-matrix` 对同一份 EXE 分别用 GDI、DirectX 回放 10 个终点，每种渲染器各跑整段写入和逐字节写入。采集目标是测试自己的终端客户区；DirectX 取实际子窗口，记录最初的尺寸同步。用红绿格交换验证画面会更新。写入次数、字节哈希、终端应答、重绘前后图像、原版像素差异及采集失败分别保留。[远程结果与制品](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-presented-matrix.md)。

The `selection` group holds Shift and the left button while the application erases text using ECH, EL, ED, DECSEL, DECERA and DECSERA. Clipboard changes, highlighted cells and subsequent right-button delivery are checked independently, including the protected, already-blank and wide-character cases. [Exact images and regression evidence](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-erase.md).

中途切换标签的场景另见[跨标签松开 Shift 拖选](https://github.com/xiongnemo/nemoterm/blob/ebbd444665d223d09e88895f93a7496b2d46e0cc/research/tab-drag-release.md)。`tab-clipboard-ownership` 用两个新窗口分别交换 GDI 与 DirectX 作为目标，检查目标原选区、来源未完成选区、窗口捕获以及双方的输入字节。这里的两个窗口分开运行，每次只有一对标签。

`selection` 组的 `bindings` 用例还验证右键粘贴后紧接回车的顺序。子程序开启鼠标上报和括号粘贴，显示 `!RUN!`。在“右键复制并粘贴”配置下，对 `RUN` 做 Shift 左键拖选，然后把右键按下、松开和 Enter 的按下、松开发给同一个终端窗口，中间不给顶层回调运行机会。检查系统剪贴板恰为 `RUN`，并在两次终端状态回复之间检查子程序依次收到 `ESC [ 200 ~`、`RUN`、`ESC [ 201 ~` 和一个 CR；最后一项不能跑到选区之前。`right-click-then-return.json` 同时保存 EXE 身份、预期和实收字节。这是可重复的消息顺序，不是对用户手速的测量。

同一 `selection` 回放还在应用开启鼠标跟踪时按住行尾的 `V` 或 `界` 的后半格，让应用左移该行后反向拖选。分别比对移动前后的整段字形、腾出的空格、分栏边界外的 `W`、松手后的高亮、Ctrl+Shift+C 和右键取得的 `中V` 或 `中界`，并核对手势没有漏送给子进程。原有 XTerm 412 逐格比对仍独立报告。[该 EXE 的 20 项实测与两幅高亮截图](../research/column-edge-integrity.md)。

`suite=unicode-boundary` 的 WinPTY 对照保留两种读屏结果：原始行读取和完整 `CHAR_INFO` 矩形读取；另行记录原始终端输出。普通视图的截止时间不变，之后重绘或切换 transcript 不能补算通过。[同一 EXE 的 5 项回放](https://github.com/xiongnemo/nemoterm/actions/runs/44550320946)及[原始制品](../research/winpty-wide-claude-b3274ed.zip)：GDI 和 DirectX 的原生接收端逐字节收到相同的括号粘贴（含中文、分解重音及两个 Nerd Font 字符）。独立系统 ConPTY、WinPTY 和串行 WinPTY 中的真实 Claude 都提交了 NFC 文本。普通 WinPTY 此次在截止前通过逐格画面确认回复：当时没有可用的旧行快照，原始输出也未出现完整回复标记。串行 WinPTY 则先从终端输出确认。两者的活动缓冲区都记录了回复，旧读法均未记录到标记。这里的可见格只用于确认 ASCII 回复标记；输入字序另以原始字节和请求为准。
