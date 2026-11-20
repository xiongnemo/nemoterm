# Nemoterm

[![Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

面向 Windows 的轻量原生终端：C/C++、Win32 界面、可切换渲染器，提供单文件 `nemoterm.exe` 开发构建。

Nemoterm 是 **PuTTY 0.85 Windows pterm 的下游 fork**，沿用其终端核心与压缩回滚，
并将 Microsoft Terminal 的 OpenConsole / ConPTY 源码链接进同一可执行文件。
本项目独立维护，非 PuTTY 或 Microsoft 官方版本。

**项目仍在开发中。** CI 产物是开发快照；协议兼容性、真实终端应用和长期资源占用仍在持续验证。
[当前 Windows x64 测试版与已知限制](#下载)。已实现功能与测试边界见 [协议支持表](docs/PROTOCOLS.md)
和 [需求与验证记录](docs/REQUIREMENTS.md)。

支持 English / 简体中文 / 跟随 Windows 显示语言，在 **Window → Interface language** 中选择并保存，重启后生效。详见[界面语言说明](docs/I18N.md)。

[下载](#下载) · [快速开始](#快速开始) · [渲染与内存](#渲染与内存) · [从源码构建](#从源码构建)

## 功能

- **单文件分发**：无需 WebView，也无需附带 `OpenConsole.exe` 或 `conpty.dll`。
- **Shell 选择**：检测 PowerShell 7、Windows PowerShell、BusyBox ash、Git Bash、WSL Bash 和 cmd，支持保存默认 shell 与启动目录。
- **多标签**：标签栏可放在上、下、左、右；支持悬停终端预览和标签滚动。使用[经典 Win32 属性页式轮廓（四边切换前后实图）](research/tab-faces-fe5f98f9.png)，当前标签贴合终端，侧栏的标题保持横排。[本版远程实测的八张原图和悬停预览](https://github.com/xiongnemo/nemoterm/actions/runs/44820130857/artifacts/14672445667)。在同一标签上按下并松开鼠标中键会关闭该标签；拖到其他标签再松手会取消。
- **原生交互**：鼠标上报、滚轮、矩形选择、可配置快捷键，以及窗口缩放与历史重排。
- **文件与图片输入**：拖入文件或文件夹即可粘贴路径；剪贴板只有图片时，交给前台应用读取。
- **本机调试接口**：按需开启实例发现、标签页寻址、输入，以及文字和 PNG 画面快照。
- **可切换渲染**：默认 GDI，可选 OpenGL 或 DirectX / Direct3D 11 合成；GPU 初始化或绘制失败时回退 GDI。
- **终端能力**：UTF-8、真彩色、Sixel、OSC 1337 图片与 GIF、Kitty 图片的直接传输子集、OSC 8 超链接、括号粘贴、同步输出，以及 kitty 键盘和 xterm modifyOtherKeys 的已实现子集。
- **字体与设置**：原生设置窗口、当前标签字号缩放、声音或视觉响铃，按需加载的内嵌 Nerd 图标字体，独立的 Nemoterm 配置存储。

Kitty 图片支持直接 RGB/RGBA/PNG、压缩传输、裁剪、透明度、查询、放置/删除、相对放置和 Unicode 占位。文件/共享内存传输及 Kitty 动画尚未实现；具体限制和逐项证据见 [协议支持表](docs/PROTOCOLS.md)。

## 下载

[下载 Windows x64 单文件试用版 `fe5f98f9`](https://github.com/xiongnemo/nemoterm/actions/runs/44820130857/artifacts/14672630186)。中文界面关闭单个会话时，确认问题也使用中文。[中英文关闭确认、取消后立即输入及后台标签检查](research/close-dialog-language.md)为 **8/8**。[本版完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44820130857)与上一版的内存结果分别计分。

[上一版 `c55cca64` 的单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44814333692/artifacts/14669630337)。修复应用用 `file:/C:/work` 或大写 `FILE:` 报告工作目录时，按 Ctrl+Shift+T 仍在旧目录打开的问题。[新标签实际目录与复制 URI](research/osc7-tab-directory.md)在 GDI、DirectX 上合计从 8/14 提升到 14/14。[本版交互和内存](research/osc7-tab-directory.md#单文件交互与内存验收)：六种满屏负载的前端私有工作集峰值为 **GDI 19.47 MB、DirectX 29.52 MB**。真实应用快捷键和右键 18/18，就绪后贴图 4/4；严格交互 **79/81**，两项失败均为 Codex 启动早期贴图。[完整运行](https://github.com/xiongnemo/nemoterm/actions/runs/44814333692)另含平台与协议对照。

[上一版 `b04ca12a` 的单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14662764153)。修复 Windows 把重复的中文或表情合并成一条字符消息时只出现一个的问题。44/44 项原生输入检查通过；Codex、Claude Code 和 OpenCode 的十个真实窗口均显示两个“中”，两次退格后分别剩一个、零个。六种满屏负载的前端私有工作集峰值为 GDI **19.97 MB**、DirectX **28.62 MB**。严格交互为 **80/81**，唯一未通过的是 Codex 输入框就绪前的一次贴图；就绪后的四种按键路径均通过。[输入框实图与验收结果](research/character-repeat.md)。

[上一版 `5ccb22b4` 的单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44801554063/artifacts/14660973842)。修复应用左右移列后矩形选区消失、右键被送给应用的问题。GDI 和 DirectX 各 30 项相关手势全部通过。本版四边标签的切换与悬停预览均通过；[看标签实图](research/tab-faces-ba16d56b.png)。六种满屏负载中，前端私有工作集峰值为 GDI **19.95 MB**、DirectX **29.23 MB**。严格交互通过 **80/81**：Codex 刚显示输入提示时有一次物理 Ctrl+Shift+V 只提交了文字，编辑器就绪后两种粘贴键均通过。[本版实测与已知差异](research/acceptance-5ccb22b4.md)。

[上一版 `ba16d56b` 的单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44793711901/artifacts/14657592423)。修复右键复制后快速 Shift 拖选被误判成双击的问题。四边标签预览、实际复制和右侧 DirectX 选区专项已通过。这份 EXE 的六组满屏负载中，GDI 私有工作集最高 **18.88 MB**，DirectX **29.45 MB**。[三个实际 agent 的内存与交互验收](research/acceptance-ba16d56b.md)。[修复前后对照](research/right-copy-ba16d56b.md) · [本版完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44793711901)。

[较早的 `355c73f8` 的单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334/artifacts/14653593498)。保留经典 Win32 风格标签和四边停靠；打字时应用可隐藏指针，Shift 仍能直接拖选屏幕文字。六种满屏负载下的前端私有工作集峰值为 GDI **19.40 MB**、DirectX **28.82 MB**。[本版成绩、SHA-256 和已知差异](research/acceptance-355c73f8.md) · [真实 agent 的选区截图](research/agent-grid-355c73f8.png)。

旧版本的下载、内存和已知差异见[历史试用版](docs/PREVIEW_HISTORY.md)，其中 `cf091974` 通过了当时全部 81 项交互检查。

Codex 0.167.0 刚显示输入提示时，可能已经能打字，但还不能接收图片。等编辑器就绪后粘贴一次，看到附件即可发送，不用先发一条文字消息。Nemoterm 不会自动重试粘贴，以免重复添加附件。[原版 pterm 和微软 Windows Terminal 的真实窗口对照](research/codex-bitmap-requests.md#微软-windows-terminal-的真实窗口)也复现过：Ctrl+V 交给 Codex 时，刚见到文字只提交了文字，稍后则收到完整图片。窗口标题不能判断是否就绪。[实际提交与截图](research/codex-file-draft-order.md) · [按键后 Windows 何时索取位图](research/codex-bitmap-requests.md)。

查找后续开发构建：

1. 登录 GitHub，打开 [Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml)。
2. 选择目标分支的一次完整成功运行；`scope=dpi` 只执行 DPI 专项。
3. 在 **Artifacts** 中下载 `nemoterm-single-exe-x64-<commit>`，解压并运行 `nemoterm.exe`。
4. 同一运行包含单文件、协议、DPI 和交互任务；具体检查与原始证据见各 job 和 artifact。

GitHub 网页下载 Actions 产物需要登录，见 [GitHub 下载说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)。
产物有保留期限；过期后请选择较新的成功运行，或按下文从源码构建。

| 产物 | 用途 |
| --- | --- |
| `source-console-host-x64-<commit>` | 本轮实际受测的单 EXE 和身份清单；各测试再按清单核对字节和 SHA-256 |
| `nemoterm-single-exe-x64-<commit>` | 单文件版本，解压后只有 `nemoterm.exe`；保留 30 天 |
| `single-exe-evidence-<commit>` | 构建日志与原生测试证据 |
| `unverified-single-exe-x64-<commit>` | 失败运行保留的诊断版本，未通过该轮验收；保留 7 天 |

同一条 [Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml)
会生成 `nemoterm-windows-x64-<commit>`。这是 MinGW 开发对照包，需要配套的
OpenConsole / ConPTY 文件，不是单文件版本。该 CI 现在为 MinGW 前端配套同一提交
构建的源码宿主，包含字节输入和光标回复同步修复；构建来源与哈希保存在包内清单。
本地 `scripts/build.ps1` 则默认获取固定版本的上游宿主，未自动应用该替换。

当前发布目标为 **Windows x64**，已有 Windows 10 19044 与 CI Windows Server 2025 的验证记录。
不同系统版本、显卡和应用的覆盖范围以对应提交的测试记录为准。

## 快速开始

解压单文件产物后，在所在目录运行：

```powershell
.\nemoterm.exe
.\nemoterm.exe --choose-shell
.\nemoterm.exe --shell powershell --tabs --tab-side left
.\nemoterm.exe --directory "C:\work" --cols 100 --rows 30
.\nemoterm.exe --font "Consolas" --font-size 12 -e pwsh.exe -NoLogo
.\nemoterm.exe --settings
```

新配置默认 **160×48 字符**，放不下时缩小到所在屏幕的工作区。已有配置和显式尺寸继续生效。
默认字体配置为 `SarasaTermSC Nerd Font Light`；可以通过 `--font` 或设置窗口选择已安装的等宽字体。
内嵌字体用于补齐缺失的 Nerd 图标，不包含完整的中文正文字体。

### Shell 与启动目录

`--shell` 接受 `auto`、`pwsh`、`powershell`、`busybox-ash`、`git-bash`、`wsl-bash`、`cmd`、`custom`。
`auto` 依次尝试 PowerShell 7、Windows PowerShell、cmd，再尝试其余已检测到的 shell。
Nemoterm 使用系统中已有的 shell；单文件产物不包含 PowerShell 7、BusyBox、Git 或 WSL 发行版。

| 要启动的 shell | 参数 |
| --- | --- |
| Windows PowerShell | `--shell powershell` |
| PowerShell 7 | `--shell pwsh` |
| BusyBox ash | `--shell busybox-ash` |
| Git Bash | `--shell git-bash` |
| WSL 默认发行版中的 Bash | `--shell wsl-bash` |

- `--list-shells` 输出检测结果的 JSON；检测本身不运行 shell，也不启动 WSL 虚拟机。
- Windows PowerShell 从系统目录查找；Git Bash 需有有效的 Git 安装；WSL Bash 需有已注册的默认发行版。
- 检测到 WSL 发行版不代表其中一定安装了 Bash；显式指定的 shell 不存在时会报错。
- `--directory "路径"` 指定启动目录，留空时继承启动器目录；Git Bash / WSL Bash 也接受各自的 POSIX 路径。

- `-e` 后的内容作为自定义启动命令，优先于保存的 shell。**Nemoterm 参数应写在 `-e` 之前。**
- `--cols` 和 `--rows` 设置启动窗口的实际字符数（默认 160×48，受屏幕工作区限制）。`-132` / `+132` 分别允许或禁止应用在启动后请求切换 80／132 列；它们不把窗口直接开成 132 或 80 列。profile 禁止远程改窗口尺寸时，该限制优先。
- 明确的命令行设置优先于保存配置，包括 `--tabs`、字体及尺寸；见[参数验证](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/command-line-profile.md)。
- 开发分支还修复了标签窗口在最小化期间接收尺寸请求后、恢复时内容区域偏小的问题，见[恢复尺寸验证](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/host-restore-size.md)。
- 在 **Profile / Shell** 中选择 shell，使用 **Save and Apply** 保存当前 profile；`--profile "名称"` 可加载命名 profile。
- **Profile / Shell** 用于编辑自定义命令和启动目录；命令行也可用 `--shell custom --shell-command "命令"`。

如果 WSL 程序会在粘贴时逐字节引用输入（XTerm `?2005`），到 **配置方案 → Shell** 勾选 **「x64 WSL 会话使用 Linux PTY」**，点「保存并应用」，再开一个 WSL 标签。这样中文和表情的每个 UTF-8 字节都能带上引用前缀。原来打开的标签保持原样；取消勾选后，新 WSL 标签恢复默认 ConPTY。PowerShell、Git Bash 不受影响。

这项设置适用于 x86-64 Linux 发行版，内嵌在同一个 `nemoterm.exe` 里。如果之前设置过环境变量 `NEMOTERM_WSL_PTY_RELAY`，先移除它，配置方案的选择才会生效。在托管 WSL1 上，启用此项仍不能让按行读取的程序把含换行的粘贴当成一整行；这与原始字节是否到齐是两件事。[逐字节与按行读取对照](research/wsl-relay-window.md) · [新标签和配置保存实测](research/wsl-profile.md)。


更多说明见 [Shell 检测](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shell-selection.md) 与 [工作目录集成](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/working-directory.md)。

### 常用操作

| 操作 | 默认绑定 |
| --- | --- |
| 复制 / 粘贴 | `Ctrl+Shift+C` / `Ctrl+Shift+V` |
| 矩形选择 | `Ctrl+左键拖动` |
| 绕过应用鼠标捕获进行选择 | `Shift+左键拖动`；矩形选择时再加 `Ctrl` |
| 打开上下文菜单 | `Ctrl+右键` |
| 新建 / 关闭标签 | `Ctrl+Shift+T` / `Ctrl+Shift+W` |
| 下一个 / 上一个标签 | `Ctrl+Tab` / `Ctrl+Shift+Tab` |
| 关闭鼠标下的标签 | 鼠标中键 |
| 打开 OSC 8 链接 | `Ctrl+左键单击` |
| 本地回滚 | `Shift+PageUp` / `Shift+PageDown` |
| 当前标签字号放大 / 缩小 | `Ctrl++` / `Ctrl+-`，或 `Ctrl+滚轮`；应用接管鼠标时滚轮需加 `Shift` |

在 Codex、OpenCode 或 Claude Code 里，按住 `Shift` 用左键拖过要复制的文字；松开鼠标和 `Shift` 后，按 `Ctrl+Shift+C` 或右键即可复制高亮内容。实测的 Windows 原生 Claude Code 2.1.322 会自行排列希伯来文，默认 profile 已能保留它画出的字序，从 PowerShell 启动也一样。其他版本如果出现字序颠倒，可建单独的 profile，在 **终端 → 功能** 中禁用双向文字显示。[混排字符的实际截图和版本范围](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/claude-writer-order.md)。

Codex 刚启动时，输入提示可能比能接收图片的编辑框先出现。如果首次粘贴后没有附件，等正常编辑框就绪，确认草稿里仍没有图片，再在同一草稿按一次 `Ctrl+Shift+V` 即可。[原始回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-a9c8150.md)验证了第二次操作只提交一张图，不需要重启或先发送文字。

在滚动中的输出里按住 `Shift` 拖选时，画面会暂时停住，方便选中眼前的文字；松手后继续显示积压的输出。 从 `a7253b2c` 起，应用同步刷新同一行时，如果只改动选区旁边的内容，高亮会保留，仍可右键复制。若选中文字本身已被替换，高亮会撤掉，右键恢复原本的用途。[修复前后的窗口对照](research/sync-selection-3308de91.md)。

默认右键只复制，输入框保持原样。要让一次右键把选区直接贴进当前输入框，在当前 profile 的 **窗口 → 选择 → 右键点击选中文字时** 选 **复制并粘贴**，然后保存。命令行也可用 `--right-click copy-paste` 或 `--right-click copy` 选择这两种行为。

在 **窗口 → 外观 → 字体访问** 中，可以分别允许应用查询字体名称或更改字体。两项默认均关闭。应用通过 OSC 50 换字体时只影响当前标签；本地字号快捷键和 Profile 的默认字体仍可独立设置。

Window / Bindings 可修改快捷键和矩形选择修饰键；Window / Tabs 配置标签位置与预览。

字号缩放使用 `Ctrl+滚轮`：应用接管鼠标时，加 `Shift` 才强制缩放。
缩放只改变当前终端，保持窗口外框大小；菜单可恢复默认字号，
Window / Bindings / Font 可修改滚轮修饰键及放大、缩小、恢复快捷键。
键盘默认 `Ctrl++` / `Ctrl+-` 放大、缩小，也支持 `Ctrl+=` 和数字小键盘；可在 Bindings / Font 修改或禁用。Terminal / Bell 可选择响铃方式，过载限制在 Bell / Overload。
设置、关于、日志及其子弹窗打开时，同一实例的终端窗口不可获得输入；关闭弹窗后恢复。
字号像素、应用鼠标输入、标签隔离和真实响铃 API 已通过专项回归与完整 CI。
Sarasa 字体在本机 GDI、OpenGL、DirectX 下的字号回归也已通过；
此前 `69cd5a4` 本机测试的 Windows 提示音已获实际听感确认。物理滚轮和跨屏 DPI 仍需单独验证，
此前的听感确认不算作新产物的一次听感测试。
详见[字号与响铃记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/font-zoom-and-bell.md)。
默认使用多标签，`Ctrl+Shift+T` 新建标签。`--no-tabs` 可启动独立窗口。`--tab-side` 接受 `top`、`bottom`、`left`、`right`；
例如 `--tabs --tab-side left` 将标签栏放在左侧，悬停标签可预览对应终端。
要让 `Ctrl+Shift+T` 从正在使用的目录打开，在 **配置方案 → Shell** 勾选「新建或复制标签页时使用 Shell 报告的目录」。这需要 shell 或应用报告当前目录；远程主机报告的目录不会当成本机路径。[OSC 7 工作目录实测](research/osc7-tab-directory.md)。

`--choose-shell` 和 `--settings` 都会先打开启动设置窗口；也可从运行中的上下文菜单选择
**Profile Settings**，调整字体、颜色、光标、回滚和渲染器。
设置窗口的 **Profile** 页提供 **Add / Edit / Save / Delete**。首次启动自动创建不可删除的 **Default**；Add 会复制当前设置到新 profile，Edit 选择要编辑的 profile。**Save and Apply** 将设置保存到当前 profile 并应用到当前标签；Cancel 放弃尚未保存的编辑，已经点击 Add / Save / Delete 的操作保留。

**Window / Translation** 管理终端字符编码和字符宽度；画线字符选项在它的 **Line drawing** 子页。
界面语言在独立的 **Window / Interface language（窗口 / 界面语言）** 页设置，保存后重启生效，所有 profile 共用；取消不保存。也可用 `--ui-language en|zh-CN|system` 临时覆盖本次启动。详见[界面语言说明](docs/I18N.md)。

不带参数启动使用 Default，也可用 `--profile "名称"` 指定；Profile 菜单可以用所选 profile 新建标签。字体、颜色、绑定等即时应用，Profile / Shell 的 shell 和目录设置在新标签或下次启动生效。临时 `-e` 命令不会保存到 profile。配置保存在 `HKCU\Software\Nemo\Nemoterm`，与 PuTTY / pterm 分开；已有配置和 `-load` 继续兼容，旧 Default Settings 显示为 Default。

在 WSL 的 Bash 里，`TERM=xterm vim` 和 `TERM=xterm-256color vim` 会让 Vim 采用对应的终端能力描述，后者声明 256 色。这两个名称不需要安装或启动 Linux 上的 XTerm 图形程序。当前试用版已在两种 `TERM` 下实际验证 Vim 和 tmux 中的 Vim；Sixel 另有像素检查。参见[本版交互结果](research/character-repeat.md)、[已知协议差异](docs/PROTOCOL_COVERAGE.md)和 [ncurses 对终端名称的说明](https://invisible-island.net/ncurses/man/term.7.html)。

OSC 52 剪贴板读取默认关闭，读写权限可在 Terminal / Clipboard 分别设置。
需要按 Terminfo 数据库发送功能键时，在 **Terminal / Keyboard** 选择 **Terminfo**；其子页可设置启动终端名称，以及独立的查询和切换权限（默认允许查询、禁止应用切换）。设置随当前 profile 保存；详见 [Terminfo 说明](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-database.md)。
Shell Integration 的命令与输出导航需要 shell 输出 OSC 133 / 633 标记；程序不会自动修改 shell 配置。

## 渲染与内存

运行 `nemoterm.exe --settings`，在 **Window / Rendering** 选择渲染器，再保存配置并启动。
运行中也可通过 **Profile Settings** 切换。
GPU 模式使用 Windows 系统 DLL 与显卡驱动，不新增分发文件；目前尚未证明它们在所有场景下比 GDI 更快。

| 模式 | 实现与内存目标 |
| --- | --- |
| GDI（默认） | GDI 绘制；前端私有工作集低于 20 MB，总工作集约 50 MB |
| OpenGL（可选） | GPU 合成；允许超过上述内存目标 |
| DirectX（可选） | Direct3D 11 合成；前端私有工作集上限 30 MB |

这里的 MB 按十进制字节计，20 MB 为 20,000,000 字节，30 MB 为 30,000,000 字节；私有工作集与私有提交量分别记录。

[下载区](#下载)链接到当前试用版的实测表。**24 轮 Codex** 一栏比较同一台托管 Windows 机器上的 pterm、Nemoterm GDI 和 DirectX，固定 160×48 与 SarasaTermSC Nerd Light；**六种满屏负载**一栏记录大量文字、Unicode 和图形内容下的峰值。内存按前端进程统计，shell、Codex 和控制台宿主单独计数。[pterm 为什么占用较低](research/pterm-findings.md) · [历史内存记录](docs/PREVIEW_HISTORY.md#内存)。

切回 GDI 后，驱动保留的内存可能需要关闭窗口才能释放。

“单 EXE”指一个分发文件：程序仍会启动同一个 EXE 的隐藏控制台宿主进程，并运行所选 shell。
ConPTY 提供伪控制台连接；OpenConsole 在宿主进程中处理 Windows 控制台 API，
并与 Nemoterm 前端交换终端输入输出。窗口、标签和最终绘制由 Nemoterm 前端负责。
程序继续依赖 Windows 的 ConDrv 驱动和系统 DLL。详见 [单文件架构](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/single-executable.md)、
[OpenGL](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/rendering.md) 与 [DirectX](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/directx.md)。

## 从源码构建

准备 Python 3、Git、CMake、Ninja、NuGet CLI，以及 Visual Studio 2022 / 2026 的 x64 C++ 工具链
（含 MSVC、ATL 和 Windows SDK 10.0.26100.0）。在 **x64 Developer PowerShell** 中运行：

```powershell
git clone --recurse-submodules https://github.com/xiongnemo/nemoterm.git
cd nemoterm
.\scripts\build-single-exe.ps1
.\build\single-exe-dist\nemoterm.exe
```

已有 checkout 可先运行 `git submodule update --init --recursive`。
脚本将固定版本的 Microsoft Terminal 源码复制到 `build/`，应用集成修改并链接生成单 EXE；
不修改上游子模块。首次构建需要联网获取构建依赖。

### 测试与 CI

所有自动测试在 GitHub-hosted runner 上执行，使用一次性桌面和隔离配置。完整入口：

```powershell
gh workflow run ci.yml --ref <branch> -f scope=full
gh run view <run-id>
gh run download <run-id> --dir <new-evidence-directory>
```

| 工作流 | 检查与产物 |
| --- | --- |
| [Test and build](.github/workflows/ci.yml) | 汇总源码单 EXE、MinGW 对照包、C/C++ 与原生协议测试、MSVC 诊断、ASan/UBSan，以及以下复用任务 |
| [Single executable](.github/workflows/single-exe.yml) | 对同一个 EXE 运行协议、像素、客户端、生命周期和内存套件，保留成品与证据 |
| [Remote DPI](.github/workflows/dpi.yml) | 英文/中文、独立窗口/标签宿主、100–200% 真实缩放与动态切换 |
| [Remote interaction](.github/workflows/remote-interaction.yml) | 远程交互分组及 160×48 Sarasa 网格负载；真实隔离客户端、六种 shell、日志与截图 |
| [Independent protocol reference](.github/workflows/protocol-reference.yml) | 固定上游版本的独立观测；包含历史 XTerm 采集与完整 ncurses 按键数据库验证，手动专项入口 |

只修改测试脚本时可回放已构建产物，并拒绝生产代码不匹配的镜像。分组命令、固定依赖、进程清理规则和物理设备验证边界见 [远程测试操作单](docs/INTERACTION_ACCEPTANCE.md)。

Git Bash 关闭残留已通过专用远程回放定位；候选 `8084338` 拒绝关闭后的新控制台连接，24 次 Git Bash 关闭及 6 次原生对照均自然回收。相同测试在旧版上仍复现 4/4 延迟连接卡死；完整 CI 为 21/22，唯一失败是 DirectX 内存门槛，见 [关闭修复记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/closed-console-connections.md)。[原始失败证据](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/git-bash-close-race.md) 保留。

上游协议对照、句柄和分配诊断继续使用专用远程工作流。页面顶部徽章显示 `main`，开发分支的准确结论以对应 run 和 [本轮记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/remote-test-migration.md) 为准；编译成功不等于运行验收通过。

## 开发状态

文件和文件夹拖入窗口时会按 shell 转义后粘贴路径，也支持资源管理器复制文件后的粘贴。
剪贴板只有图片时，Paste 绑定会按前台应用选用的键盘协议发送一次 Ctrl+V，由应用读取图片（[传统模式、kitty 和 xterm 的实测记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/image-paste-key-protocol.md)）；已用隔离的真实 Codex / OpenCode
验证图片提交。行为、测试方法与边界见 [文件和图片输入](docs/INPUT_TRANSFERS.md)。

本机调试可用 `nemoterm.exe --automation` 按需开启发现、标签页寻址、输入和画面接口。
`python tools/nemoterm_debug.py discover` 会列出可连接的实例；文字快照和 PNG 截图
无需抢焦点或读写剪贴板。它使用仅限当前用户和登录会话的 Windows 命名管道，默认关闭，
不增加单文件终端的运行依赖。用法、协议及边界见 [本机自动化接口](docs/AUTOMATION.md)。

实现与验收按具体提交记录。颜色设置、字符集恢复和字符保护已有远程测试证据，
完整转义序列清单与剩余缺项见 [协议覆盖表](docs/PROTOCOL_COVERAGE.md)。
上方固定下载快照的范围以其验证记录为准，不能由当前源码反推旧产物已支持全部新增功能。

长期鼠标与窗口生命周期、真实 IME / 多显示器 DPI、长时间终端应用负载仍有待完成的验收。
kitty / iTerm 图片、彩色 emoji 和完整 ISO 2022 等能力不能视为已完整支持；
各转义序列的状态以 [协议支持表](docs/PROTOCOLS.md) 为准。

提交问题时，请附上提交号或 CI 产物名、Windows 版本、shell、渲染模式和可复现步骤。

## 许可与上游

Nemoterm 自有代码采用 [MIT License](LICENSE)。第三方代码、字体与数据保留各自的许可和声明：

| 来源 | 用途与许可 |
| --- | --- |
| [PuTTY 0.85](vendor/putty-0.85/LICENCE) | pterm 终端核心与 Win32 基础，MIT |
| [puff 2.3](vendor/putty-0.85/terminal/puff/puff.h) | zlib 上游的精简 DEFLATE 解码器，保留 zlib 许可；本项目修改和来源见 [清单](vendor/putty-0.85/terminal/puff/SOURCE.json) |
| [Microsoft Terminal](https://github.com/microsoft/terminal/tree/f6de9e0618015def1c9dda5b82f9d3abf03eb799) | 固定版本的 OpenConsole / ConPTY，MIT 与第三方声明 |
| [Nerd Fonts](vendor/nerd-fonts/README.md) | 内嵌图标字体，保留其许可与组件声明 |

单文件产物将许可嵌入 EXE，可通过 **About / View Licence** 或 `--licenses` 查看。
上游源码研究和最初的内存分析见 [pterm 研究记录](research/pterm-findings.md)。
