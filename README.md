# Nemoterm

[![Test and build](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xiongnemo/nemoterm/actions/workflows/ci.yml)
[![Single executable](https://github.com/xiongnemo/nemoterm/actions/workflows/single-exe.yml/badge.svg?branch=main)](https://github.com/xiongnemo/nemoterm/actions/workflows/single-exe.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

面向 Windows 的轻量原生终端：C/C++、Win32 界面、可切换渲染器，最终交付一个 `nemoterm.exe`。

Nemoterm 是 **PuTTY 0.85 Windows pterm 的下游 fork**，沿用其终端核心与压缩回滚，
并将 Microsoft Terminal 的 OpenConsole / ConPTY 源码链接进同一可执行文件。
本项目独立维护，非 PuTTY 或 Microsoft 官方版本。

**项目仍在开发中。** CI 产物是开发快照；协议兼容性、真实终端应用和长期资源占用仍在持续验证。
已实现功能与测试边界见 [协议支持表](docs/PROTOCOLS.md) 和 [需求与验证记录](docs/REQUIREMENTS.md)。

## 功能

- **单文件分发**：无需 WebView，也无需附带 `OpenConsole.exe` 或 `conpty.dll`。
- **Shell 选择**：检测 PowerShell 7、Windows PowerShell、BusyBox ash、Git Bash、WSL Bash 和 cmd，支持保存默认 shell 与启动目录。
- **多标签**：标签栏可放在上、下、左、右；支持悬停终端预览、中键关闭和标签滚动。
- **原生交互**：鼠标上报、滚轮、矩形选择、可配置快捷键，以及窗口缩放与历史重排。
- **可切换渲染**：默认 GDI，可选 OpenGL 或 DirectX / Direct2D 合成；GPU 初始化或绘制失败时回退 GDI。
- **终端能力**：UTF-8、真彩色、Sixel 图片、OSC 8 超链接、括号粘贴、同步输出，以及 kitty 键盘和 xterm modifyOtherKeys 的已实现子集。
- **字体与设置**：原生设置窗口，按需加载的内嵌 Nerd 图标字体，独立的 Nemoterm 配置存储。

## 下载

在 [Single executable from source](https://github.com/xiongnemo/nemoterm/actions/workflows/single-exe.yml)
中选择 **`main` 分支上成功的运行**，在页面底部的 Artifacts 下载：

| 产物 | 用途 |
| --- | --- |
| `nemoterm-single-exe-x64-<commit>` | 单文件版本，解压后只有 `nemoterm.exe`；保留 30 天 |
| `single-exe-evidence-<commit>` | 构建日志与原生测试证据 |
| `unverified-single-exe-x64-<commit>` | 失败运行保留的诊断版本，未通过该轮验收 |

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
.\nemoterm.exe --shell pwsh --tabs --tab-side left
.\nemoterm.exe --directory "C:\work" --cols 100 --rows 30
.\nemoterm.exe --font "Consolas" --font-size 12 -e pwsh.exe -NoLogo
.\nemoterm.exe --settings
```

新配置默认 **160×48 字符**，放不下时缩小到所在屏幕的工作区。已有配置和显式尺寸继续生效。
默认字体配置为 `SarasaTermSC Nerd Font Light`；可以通过 `--font` 或设置窗口选择已安装的等宽字体。
内嵌字体用于补齐缺失的 Nerd 图标，不包含完整的中文正文字体。

### Shell 与启动目录

`--shell` 接受 `auto`、`pwsh`、`powershell`、`busybox-ash`、`git-bash`、`wsl-bash`、`cmd`。
`auto` 依次尝试 PowerShell 7、Windows PowerShell、cmd。

- `--list-shells` 输出检测结果的 JSON；检测本身不运行 shell，也不启动 WSL 虚拟机。
- Windows PowerShell 从系统目录查找；Git Bash 需有有效的 Git 安装；WSL Bash 需有已注册的默认发行版。
- `--directory "路径"` 指定启动目录，留空时继承启动器目录；Git Bash / WSL Bash 也接受各自的 POSIX 路径。
- `-e` 后的内容作为自定义启动命令，优先于保存的 shell。**Nemoterm 参数应写在 `-e` 之前。**
- 在 Session / Shell 中保存默认选择；`-load "配置名"` 可加载命名配置。

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

右键已选中的文本默认只复制；可在 Window / Selection 改为复制并粘贴。
Window / Bindings 可修改快捷键和矩形选择修饰键；Window / Tabs 配置标签位置与预览。
多标签启动使用 `--tabs`，或保存对应设置。

通过 `--settings` 或上下文菜单中的 **Change Settings** 调整字体、颜色、光标、回滚和渲染器。
配置保存在 `HKCU\Software\Nemo\Nemoterm`，与 PuTTY / pterm 分开。

OSC 52 剪贴板读取默认关闭，读写权限可在 Terminal / Clipboard 分别设置。
Shell Integration 的命令与输出导航需要 shell 输出 OSC 133 / 633 标记；程序不会自动修改 shell 配置。

## 渲染与内存

Window / Rendering 可选择 GDI、OpenGL 或 DirectX（Direct2D 合成）。
GPU 模式使用 Windows 系统 DLL 与显卡驱动，不新增分发文件；目前尚未证明它们在所有场景下比 GDI 更快。

GDI 的优化目标是前端私有工作集 **低于 20 MB**、总工作集约 **50 MB**，按十进制字节计。
控制台宿主、shell 和终端内应用是独立进程，量测时分别记录；这是优化目标，不是任意负载下的内存保证。
可选 OpenGL 模式不受 20 MB 目标约束，DirectX 仍有超标场景。切回 GDI 后，驱动保留的内存可能需要关闭窗口才能释放。

“单 EXE”指一个分发文件：程序仍会启动同一个 EXE 的隐藏控制台宿主进程，并运行所选 shell。
它继续依赖 Windows 的 ConDrv 驱动和系统 DLL。详见 [单文件架构](research/single-executable.md)、
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

已有 checkout 可先运行 `git submodule update --init`。
脚本将固定版本的 Microsoft Terminal 源码复制到 `build/`，应用集成修改并链接生成单 EXE；
不修改上游子模块。首次构建需要联网获取构建依赖。

### 测试与 CI

- **Test and build**：Windows 核心回归、MinGW 对照构建、MSVC 原生渲染诊断，以及 Linux ASan / UBSan 检查。
- **Single executable from source**：从源码构建单文件版本，在隔离目录运行原生集成测试，并保存产物与证据。

本地核心与 MinGW 对照测试需要 `gcc.exe` 在 PATH 中：

```powershell
.\scripts\test.ps1
```

单文件原生集成测试：

```powershell
python -m pip install frida==17.24.3
.\scripts\test-single-exe.ps1 -Executable .\build\single-exe-dist\nemoterm.exe
```

原生集成测试会打开窗口并测试输入和剪贴板，应在空闲桌面或专用测试环境运行。
测试结果只适用于记录的提交、系统和场景；编译成功不代表运行验收通过。

## 开发状态

主分支与开发分支的验证进度可能不同。最新开发改动及待验证项见
[开发分支需求账本](https://github.com/xiongnemo/nemoterm/blob/feature/attribute-colour-settings/docs/REQUIREMENTS.md)。
部分新颜色设置、字符集恢复和字符保护改动仍在验证中，尚未全部合入 `main`。

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
