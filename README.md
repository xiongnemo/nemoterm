# Nemoterm

[![Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml)
[![Single executable](https://github.com/xiongnemo/nemoterm/actions/workflows/single-exe.yml/badge.svg?branch=main)](https://github.com/xiongnemo/nemoterm/actions/workflows/single-exe.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

面向 Windows 的轻量原生终端：C/C++、Win32 界面、可切换渲染器，提供单文件 `nemoterm.exe` 开发构建。

Nemoterm 是 **PuTTY 0.85 Windows pterm 的下游 fork**，沿用其终端核心与压缩回滚，
并将 Microsoft Terminal 的 OpenConsole / ConPTY 源码链接进同一可执行文件。
本项目独立维护，非 PuTTY 或 Microsoft 官方版本。

**项目仍在开发中。** CI 产物是开发快照；协议兼容性、真实终端应用和长期资源占用仍在持续验证。
本文说明以 `main` 分支为准。已实现功能与测试边界见 [协议支持表](docs/PROTOCOLS.md)
和 [需求与验证记录](docs/REQUIREMENTS.md)。

[下载](#下载) · [快速开始](#快速开始) · [渲染与内存](#渲染与内存) · [从源码构建](#从源码构建)

## 功能

- **单文件分发**：无需 WebView，也无需附带 `OpenConsole.exe` 或 `conpty.dll`。
- **Shell 选择**：检测 PowerShell 7、Windows PowerShell、BusyBox ash、Git Bash、WSL Bash 和 cmd，支持保存默认 shell 与启动目录。
- **多标签**：标签栏可放在上、下、左、右；支持悬停终端预览、中键关闭和标签滚动。
- **原生交互**：鼠标上报、滚轮、矩形选择、可配置快捷键，以及窗口缩放与历史重排。
- **可切换渲染**：默认 GDI，可选 OpenGL 或 DirectX / Direct2D 合成；GPU 初始化或绘制失败时回退 GDI。
- **终端能力**：UTF-8、真彩色、Sixel 图片、OSC 8 超链接、括号粘贴、同步输出，以及 kitty 键盘和 xterm modifyOtherKeys 的已实现子集。
- **字体与设置**：原生设置窗口，按需加载的内嵌 Nerd 图标字体，独立的 Nemoterm 配置存储。

## 下载

已验证的固定快照：[下载 `52d0962` 单文件产物](https://github.com/xiongnemo/nemoterm/actions/runs/43449297324/artifacts/14050547004)。
该提交已合入 `main`，在修复分支上通过两条 CI 和 57 组单文件检查；
包含关闭测试的阶段记录与超时诊断。早期运行的超时问题及验证范围见下方 [CI 状态](#测试与-ci)。
产物预计于 **2026-12-13（UTC）** 过期，SHA-256 和完整范围见 [验证记录](research/native-observer-cleanup.md)。

查找后续开发构建：

1. 登录 GitHub，打开 [Single executable from source](https://github.com/xiongnemo/nemoterm/actions/workflows/single-exe.yml)。
2. 筛选 `main` 分支，选择一次 **成功完成** 的运行。
3. 查看同一提交的 [Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml) 结果；两条工作流独立执行。
4. 在运行页面的 **Artifacts** 中下载 `nemoterm-single-exe-x64-<commit>`，解压并运行 `nemoterm.exe`。

GitHub 网页下载 Actions 产物需要登录，见 [GitHub 下载说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)。
产物有保留期限；过期后请选择较新的成功运行，或按下文从源码构建。

| 产物 | 用途 |
| --- | --- |
| `nemoterm-single-exe-x64-<commit>` | 单文件版本，解压后只有 `nemoterm.exe`；保留 30 天 |
| `single-exe-evidence-<commit>` | 构建日志与原生测试证据 |
| `unverified-single-exe-x64-<commit>` | 失败运行保留的诊断版本，未通过该轮验收；保留 7 天 |

另一条 [Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml)
会生成 `nemoterm-windows-x64-<commit>`。这是 MinGW 开发对照包，需要配套的
OpenConsole / ConPTY 文件，不是单文件版本，也不包含全部源码集成修复。

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
- 在 **Session** 中选择 shell，并保存到 `Default Settings` 或命名配置；`-load "配置名"` 可加载命名配置。
- **Session / Shell** 用于编辑自定义命令和启动目录；命令行也可用 `--shell custom --shell-command "命令"`。

更多说明见 [Shell 检测](research/shell-selection.md) 与 [工作目录集成](research/working-directory.md)。

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

右键已选中的文本默认只复制；可在 Window / Selection 改为复制并粘贴，
或使用 `--right-click copy-paste` 启动；`--right-click copy` 恢复仅复制。
Window / Bindings 可修改快捷键和矩形选择修饰键；Window / Tabs 配置标签位置与预览。
多标签启动使用 `--tabs`，或保存对应设置。`--tab-side` 接受 `top`、`bottom`、`left`、`right`；
例如 `--tabs --tab-side left` 将标签栏放在左侧，悬停标签可预览对应终端。

`--choose-shell` 和 `--settings` 都会先打开启动设置窗口；也可从运行中的上下文菜单选择
**Change Settings**，调整字体、颜色、光标、回滚和渲染器。
配置保存在 `HKCU\Software\Nemo\Nemoterm`，与 PuTTY / pterm 分开。

OSC 52 剪贴板读取默认关闭，读写权限可在 Terminal / Clipboard 分别设置。
Shell Integration 的命令与输出导航需要 shell 输出 OSC 133 / 633 标记；程序不会自动修改 shell 配置。

## 渲染与内存

运行 `nemoterm.exe --settings`，在 **Window / Rendering** 选择渲染器，再保存配置并启动。
运行中也可通过 **Change Settings** 切换。
GPU 模式使用 Windows 系统 DLL 与显卡驱动，不新增分发文件；目前尚未证明它们在所有场景下比 GDI 更快。

| 模式 | 实现与内存目标 |
| --- | --- |
| GDI（默认） | GDI 绘制；前端私有工作集低于 20 MB，总工作集约 50 MB |
| OpenGL（可选） | GPU 合成；允许超过上述内存目标 |
| DirectX（可选） | Direct2D 硬件合成；沿用 GDI 的内存目标，目前仍有超标场景 |

这里的 MB 按十进制字节计，20 MB 为 20,000,000 字节；私有工作集与私有提交量分别记录。
控制台宿主、shell 和终端内应用是独立进程，量测时分别记录；这是优化目标，不是任意负载下的内存保证。
切回 GDI 后，驱动保留的内存可能需要关闭窗口才能释放。

“单 EXE”指一个分发文件：程序仍会启动同一个 EXE 的隐藏控制台宿主进程，并运行所选 shell。
ConPTY 提供伪控制台连接；OpenConsole 在宿主进程中处理 Windows 控制台 API，
并与 Nemoterm 前端交换终端输入输出。窗口、标签和最终绘制由 Nemoterm 前端负责。
程序继续依赖 Windows 的 ConDrv 驱动和系统 DLL。详见 [单文件架构](research/single-executable.md)、
[OpenGL](research/rendering.md) 与 [DirectX](research/directx.md)。

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

| 工作流 | 主分支上的检查与产物 |
| --- | --- |
| [Test and build](.github/workflows/ci.yml) | Windows 核心回归、MinGW 对照构建及原生集成测试，Linux ASan / UBSan；保留对照包和测试日志 |
| [Single executable from source](.github/workflows/single-exe.yml) | MSVC 从源码构建单 EXE，在隔离目录执行原生协议、像素和客户端测试；保留单文件产物与测试证据 |

截至 **2026-11-14（Australia/Sydney）**，相关提交的运行结果为：

| 运行位置 | Test and build | Single executable from source |
| --- | --- | --- |
| `52d0962`，关闭诊断修复分支 | [通过](https://github.com/xiongnemo/nemoterm/actions/runs/43449297264) | [通过，57 组检查](https://github.com/xiongnemo/nemoterm/actions/runs/43449297324) |
| `1b09f82`，早期修复分支 | [通过](https://github.com/xiongnemo/nemoterm/actions/runs/43431838203) | [通过，57 组检查](https://github.com/xiongnemo/nemoterm/actions/runs/43431838348) |
| `1b09f82`，`main` 合入后复跑 | [通过](https://github.com/xiongnemo/nemoterm/actions/runs/43434238410) | [达到 45 分钟上限，取消](https://github.com/xiongnemo/nemoterm/actions/runs/43434238339) |

早期超时的单文件运行未完成验收，也未上传已验证的 EXE；超时原因仍在排查。
新检查点的 6 个关闭场景均正常完成，不能由此宣称所有历史卡住现象已解决。
固定快照的通过记录不代表后续运行均通过。页面顶部徽章显示 `main` 的工作流状态，
具体提交的测试范围、日志和产物应以对应运行记录为准。

本地核心与 MinGW 对照测试需要 `gcc.exe` 在 PATH 中：

```powershell
.\scripts\test.ps1 -Destination .\build\mingw-dist
```

这条命令也会构建 MinGW 对照包；示例将其放到 `build/mingw-dist`。
单文件构建产物仍位于 `build/single-exe-dist`。

单文件原生集成测试：

```powershell
python -m pip install frida==17.24.3
.\scripts\test-single-exe.ps1 -Executable .\build\single-exe-dist\nemoterm.exe
```

结果默认写入 `build/single-exe-check`。重跑时用 `-Destination` 指定新的目录，脚本不会覆盖已有证据。
上面的本地命令不包含 Codex 客户端测试；传入 `-CodexExecutable "路径\codex.exe"` 才会运行这些检查。
CI 使用 `tools/codex-fixture` 锁定的客户端版本，并通过本地响应测试默认、内嵌及多标签界面。

原生集成测试会打开窗口并测试输入和剪贴板，应在空闲桌面或专用测试环境运行。
测试结果只适用于记录的提交、系统和场景；编译成功不代表运行验收通过。

## 开发状态

主分支与开发分支的验证进度可能不同。部分新颜色设置、字符集恢复和字符保护改动仍在验证中，
尚未全部合入 `main`。开发分支中的实现和测试结果应以各自提交为准。

长期鼠标与窗口生命周期、真实 IME / 多显示器 DPI、长时间终端应用负载仍有待完成的验收。
kitty / iTerm 图片、彩色 emoji 和完整 ISO 2022 等能力不能视为已完整支持；
各转义序列的状态以 [协议支持表](docs/PROTOCOLS.md) 为准。

提交问题时，请附上提交号或 CI 产物名、Windows 版本、shell、渲染模式和可复现步骤。

## 许可与上游

Nemoterm 自有代码采用 [MIT License](LICENSE)。第三方代码、字体与数据保留各自的许可和声明：

| 来源 | 用途与许可 |
| --- | --- |
| [PuTTY 0.85](vendor/putty-0.85/LICENCE) | pterm 终端核心与 Win32 基础，MIT |
| [Microsoft Terminal](https://github.com/microsoft/terminal/tree/f6de9e0618015def1c9dda5b82f9d3abf03eb799) | 固定版本的 OpenConsole / ConPTY，MIT 与第三方声明 |
| [Nerd Fonts](vendor/nerd-fonts/README.md) | 内嵌图标字体，保留其许可与组件声明 |

单文件产物将许可嵌入 EXE，可通过 **About / View Licence** 或 `--licenses` 查看。
上游源码研究和最初的内存分析见 [pterm 研究记录](research/pterm-findings.md)。
