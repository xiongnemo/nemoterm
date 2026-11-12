# Nemoterm

Windows 原生 C 终端，基于 PuTTY 0.85 的 MIT 许可终端核心、Win32/GDI 和 ConPTY。
不使用 WebView。**开发中，尚未完成全部现代终端协议与真实 agent 验收。**

这是 PuTTY Windows **pterm 的 downstream fork**，不是 PuTTY 官方版本。
私有项目：[xiongnemo/nemoterm](https://github.com/xiongnemo/nemoterm)。
GitHub Actions 会从源码构建单文件版本，运行隔离目录中的原生回归，
成功后上传 `nemoterm-single-exe-x64-<commit>` artifact，解压后只有 `nemoterm.exe`。
许可证已嵌入 About / View Licence 和 `--licenses`，测试证据另存 artifact，保留 30 天。
另一条 CI 执行 Windows 核心回归、MinGW 对照构建和 Linux ASan/UBSan；
`nemoterm-windows-x64-<commit>` 是供开发对照的旧多文件包。

## 构建与启动

单文件版本已在本机 Windows 10 19044 和 CI Windows Server 2025 验证。
下载 CI 产物即可使用；源码构建需要 Python、Git 子模块、CMake/Ninja、NuGet 和
Visual Studio 2026 x64 开发者 shell。MinGW 对照构建仍使用 `scripts/build.ps1 -Tests`。

```powershell
git submodule update --init
.\scripts\build-single-exe.ps1
python -m pip install frida==17.24.3 # native input/DPI test instrumentation only
.\scripts\test-single-exe.ps1 -Executable .\build\single-exe-dist\nemoterm.exe
# 下载的单文件产物可放在任意目录，以下示例放在 dist 中：
.\dist\nemoterm.exe
.\dist\nemoterm.exe -e pwsh.exe -NoLogo
.\dist\nemoterm.exe --cols 100 --rows 30 --font-size 14 -e cmd.exe
.\dist\nemoterm.exe --settings
```

支持 `--font "字体名称"`、`--font-size 12`、`--cols 80`、`--rows 24`、
`--scrollback 2000`、`--right-click copy|copy-paste`。`-e` 后原样传递启动命令。
参数应放在 `-e` 之前。保存的命名配置沿用 `-load "配置名"`。
也可以 Ctrl+右键 → Change Settings，在原生设置窗口配置字体、颜色、光标和历史。
配置写入 `HKCU\Software\Nemo\Nemoterm`，与现有 PuTTY/pterm 分开。

新配置默认 **160×48 字符**。启动时按实际字体与窗口边框计算尺寸，放不下时
缩小字符网格到所在屏幕工作区；显式尺寸和已有配置继续生效。
Window/Rendering 可在默认低内存 GDI 与可选 OpenGL GPU 合成之间切换。
OpenGL 使用系统 DLL 和已安装显卡驱动，无新增分发依赖；初始化或绘制失败自动回退 GDI。
GPU 模式允许超过原内存目标，切回 GDI 后需重启窗口才能完全释放驱动内存。
它缓存栅格化文字并由 GPU 合成，不代表已经证明比 GDI 更快。[实现与验证](research/rendering.md)。

应用可通过字符或像素请求调整窗口大小；省略的维度保持当前值，显式零使用所在显示器
可容纳的尺寸。请求遵守禁止远程调整、锁定窗口及字体缩放设置；最小化期间仍可处理
输出和恢复尺寸。极小窗口受字符格和 Windows 标题栏最小尺寸限制。
[参数、原生测试及平台差异](research/window-resize.md)。

启动 shell 可选 `--shell auto|pwsh|powershell|busybox-ash|git-bash|wsl-bash|cmd`。
`--choose-shell` 打开启动选择窗口；Session 的 Shell 下拉框和“Choose shell on
startup”可随 Default Settings 或命名配置保存。自定义命令使用
`--shell-command '"C:\path with spaces\shell.exe" --argument'`；`-e` 优先于保存的 shell。
`--list-shells` 向标准输出打印 JSON，检测不会运行 shell 或启动 WSL 虚拟机。
Windows PowerShell 从系统目录查找；Git Bash 需验证 Git 安装布局；WSL 需有注册的默认
发行版。自动选择依次优先 pwsh、Windows PowerShell、cmd。
本机六种 shell（含 WSL Debian）的交互命令和退出测试已通过；[记录](research/shell-selection.md)。

启动目录使用 `--directory "C:\work"`，或在 Session/Shell 保存；留空继承启动器目录。
内置 Git Bash 和 WSL Bash 也接受各自的 POSIX 路径（WSL 使用默认发行版）。
当 shell 输出 OSC 7、9;9、633 P;Cwd 或 1337 CurrentDir 时，Duplicate Session
默认继承报告的本机目录；同页可关闭此行为。菜单的 Copy Working Directory URI
复制规范化 file URI。远端主机的目录仅作为元数据保留；[协议、配置示例和边界](research/working-directory.md)。

OpenConsole 和 ConPTY 已从固定版本的 Microsoft Terminal 源码链接进 Nemoterm。
同一 EXE 的隐藏进程承载控制台，无运行时解压，也不需要旁边的 OpenConsole.exe 或
conpty.dll；仍使用 Windows 的 ConDrv 驱动与系统 DLL。[源码和 REA 证据](research/single-executable.md)。
单文件隔离测试还验证启动器退出后，控制台子进程可以继续运行。

默认字体为机器上安装的 `SarasaTermSC Nerd Font Light`，UTF-8，ClearType。
该字体缺少的 Nerd 图标由 EXE 内嵌的 Symbols Nerd Font Mono 按需补齐，
支持 BMP 和补充平面图标，无需额外安装字体；已有字形继续使用所选字体。
回退保留字符格和复制内容，字体句柄有固定上限；[字体验证](research/font-fallback.md)。

## 交互

* Ctrl+Shift+C：复制选择内容；Ctrl+Shift+V：粘贴系统剪贴板。
  Window/Bindings 可改复制、粘贴、复制并粘贴的快捷键，以及矩形选择修饰键。
* Ctrl+左键拖选：矩形选择；应用捕获鼠标时加 Shift。拖动中松开修饰键保持选区形状。
* 右键已选择的文本：默认只复制；可在 Window/Selection 改为复制并粘贴。
  复制并粘贴使用当前选区，系统剪贴板繁忙时也不会粘贴旧内容。
* Ctrl+右键：始终打开上下文菜单，其中有 Copy and Paste。
* Shell Integration 菜单可跳到上一／下一处提示符，或选择命令、输出后用正常复制键复制。
  需要 shell 已输出 OSC 133／633 标记；不会自动修改 shell 配置。Window/Bindings/Commands
  可为四个动作设置快捷键，默认不绑定。选择范围只包含保留的历史；[实现边界与验证状态](research/shell-marks-design.md)。
* Shift+左键拖选：强制选择终端字符网格，绕过应用鼠标模式；备用屏同样适用。
* OSC 8 链接悬停显示完整地址，并为同组标签加下划线；Ctrl+左键打开，
  Ctrl+右键菜单可打开或复制地址。拖动或按住 Shift 仍选择标签文本。
* 没有选中文字时，普通右键在应用鼠标模式下交给应用，否则显示菜单。
* OSC 52 允许应用复制文本；读取剪贴板默认关闭，可在 Terminal/Clipboard 分别配置读写。
  启用读取后，运行中的会话（包括远端主机）可以获取剪贴板文本。
* 默认使用现代 xterm 功能键、Home/End 和修饰键编码；命名配置可继续选择旧键盘模式。
  Ctrl+PageUp/PageDown 在默认模式下发送给应用；Shift+PageUp/PageDown 保留本地滚动。
* 支持应用协商 xterm modifyOtherKeys 的 0–3 级和两种编码格式；
  Terminal/Keyboard/Extended 可设置初始值，默认关闭。kitty 增强键盘启用时优先。
* 同一页面可启用实验选项 `Preserve Windows key events`，通过 Win32 输入协议
  保留 Windows 控制台应用的 Shift+Enter、Ctrl+Space、左右修饰键和按键释放。
  默认关闭：当前 ConPTY 的普通 VT 转换会丢失 F21–F24，且此路径会绕过自定义
  传统按键编码。kitty/modifyOtherKeys 协商仍优先；[验证与限制](research/win32-input.md)。

## 验证与边界

```powershell
.\scripts\test.ps1
```

当前核心回归包含：鼠标 9/1000/1001/1002/1003、1005/1006/1015/1016 编码协商、
1004 焦点、1007 备用屏滚轮、四向滚轮、两个侧键、修饰键与捕获取消，及 1049 备用屏组合，
Shift 选择中文与组合字符、普通鼠标字节上报、真彩色/256 色、备用屏恢复、
冒号RGB、斜体/隐藏、五种下划线及独立下划线颜色、压缩历史中的样式还原，
DECSCUSR 光标形状/闪烁、DEC 12，以及 DECRQSS 的样式/滚动边界/尺寸读回，
DECSTR软复位、XTSAVE/XTRESTORE模式组保存、DECNKM小键盘和DECOM光标恢复，
矩形填充/重叠复制/属性修改及流式范围，保留组合字符、保护位和链接；[矩形编辑验证](research/rectangle-editing.md)，
左右滚动边距及跨边界 Sixel 按列滚动；[边距验证](research/horizontal-margins.md)，
XTGETTCAP 终端名/颜色/逻辑按键查询、应用光标模式及修饰键组合，
kitty 键盘协议的五种增强标志、主/备用屏独立模式栈、按下/重复/释放、备用键码与关联文本，
逐字节 OSC 标题、调色板/默认颜色设置与查询、括号粘贴，以及 Sixel 解码的精确像素/内存预算/异常输入。
OSC 8 已接入字符格、压缩历史、覆盖/擦除和按已绘制画面命中地址的核心接口；
链接记录上限为 256 KiB / 1024 条，旧编号回收后不会指向新地址。
Terminal/Hyperlinks 设置可禁用 OSC 8，或允许注册的自定义 URI 协议。
默认可打开 HTTP、HTTPS、FTP、mailto 和本机 Windows 驱动器的 file 链接；
file 主机必须为空、localhost 或匹配本机名称。远程文件地址可复制，不能直接打开。
`python tests/hyperlink_window_smoke.py` 通过临时 URI 处理器验证实际打开的完整地址、
悬停分组像素、最长地址、菜单/剪贴板、配置开关、Shift 拖选、四种应用鼠标模式、
捕获取消、缩放及同步输出。另用 6,000 个长链接与 800 张 Sixel 验证淘汰和进程内存。
`python tests/keyboard_window_smoke.py` 检查 kitty 协商后经过实际 ConPTY 的输入字节，
包括 Unicode 提交、修饰键、失焦清理、窗口缩放和 Ctrl+Shift+C/V 括号粘贴。
`python tests/mok_window_smoke.py` 检查 xterm modifyOtherKeys 的等级、格式、修饰位屏蔽、
查询/复位、Unicode、kitty 优先级和相同的复制/鼠标/缩放行为；另测保存的初始配置。
独立 xterm 对照、Windows 映射和已知差异见 [编码记录](research/modify-other-keys.md)。
`python tests/state_control_window_smoke.py` 检查软复位保留文字/Sixel、鼠标模式组恢复、
缩放后的像素坐标、Shift复制和同步绘制；[XTerm对照与状态语义](research/state-control.md)。
`python tests/win32_input_window_smoke.py` 使用临时配置启用 Win32 输入，验证真实
`ReadConsoleInputW` 记录、UTF-16、重复次数、Ctrl+C/Ctrl+Break 信号、尺寸通知和
VT/kitty/modifyOtherKeys 切换，以及 Shift 选择和 Ctrl+Shift+C/V。测试结束删除临时配置。
`powershell.exe -NoProfile -File tests/settings_window_smoke.ps1` 检查真实设置窗口的
选项可见性、右键默认策略、保存/加载和从设置页启动本地会话；[设置截图](research/mok-settings.png)。
`python tests/osc52_window_smoke.py` 检查四种应用剪贴板权限、中文/emoji、
本地选区保留、同步输出、锁竞争和延迟读取期间窗口响应，以及复位后的迟到回复取消。
每次 OSC 52 文本上限 256 KiB；系统剪贴板、本地选区及有界的辅助缓冲区分别处理。
核心测试直接调用 Windows 布局转换器验证美式、俄语、德语 AltGr 和美式国际死键，
不会激活或切换用户布局；真实 IME 候选窗口、更多物理键盘及长期 agent 使用仍需验收。
`python tests/codex_window_smoke.py` 使用实际 Codex 0.167.0 客户端连接本地测试响应，
验证中文/emoji、流式 Markdown、长回复、32 次缩放、Shift 选择和 Ctrl+Shift+C/V；
`--inline` 验证非备用屏模式。配置和会话使用临时目录，无需 API 密钥或在线模型。
CI 固定客户端版本并运行两种模式；[复现、修复及验收范围](research/real-agent.md)。
内置宿主已修复 UTF-16 代理项释放事件导致的 emoji 丢失；快速跨位置拖选也不会再被
误判为双击/三击。同位置的词/行选择及应用高亮协议继续保留。
截图见 [链接悬停](research/hyperlink-hover.png) 与 [完整地址](research/hyperlink-address.png)。
`python tests/mouse_window_smoke.py` 另验证真实 Win32 消息经 ConPTY 到子进程的
拖动/像素/滚轮/侧键/焦点输入、多键捕获、Shift 事件隔离，以及连续缩放和最大化/还原的窗口尺寸通知。
`python tests/sync_window_smoke.py` 验证 2026 同步输出期间的像素保持、
查询与输入、结束/超时/缩放释放，以及整个进程的工作集；快照使用有界压缩条带。
`python tests/sgr_window_smoke.py` 检查样式、颜色、复位及同步快照的真实像素，
并检查中英文斜体字形宽度，防止字体平均宽度和终端格宽混用导致字形被压窄。
截图见 [SGR 样式](research/sgr-styles.png)。
`python tests/font_resize_window_smoke.py` 验证“缩放字体”模式下的横向、纵向、
同时放大和恢复，检查字形宽度、固定行列数及 GDI 句柄回收。
`python tests/query_window_smoke.py` 检查三种光标的实际像素、闪烁开关、
状态查询、缩放后的尺寸读回和同步输出期间的光标保持；
另对照普通/应用光标模式的能力查询与 15 类真实窗口按键消息传给 ConPTY 子进程的字节。
`python tests/highlight_window_smoke.py` 检查 1001 应用高亮握手、准确选区像素、
正反向及多击回报、Shift 接管、超时与缩放清理；[高亮截图](research/highlight-selection.png)。
`python tests/sixel_window_smoke.py` 逐像素检查图片随窗口行列变化保留、横向裁剪/恢复、
主屏临时历史和备用屏删除行、局部滚动与移动后擦除，并记录工作集。
`python tests/sixel_font_window_smoke.py` 验证字体尺寸变化后保留图片和擦除孔洞，
包括新格宽/格高下擦除、分段滚动、历史与主/备用屏。图片保持原始像素尺寸，
起点和滚动位移随字符格变化；不复制或重采样位图。真实多屏 DPI 切换仍待验收。
这些测试不等于所有终端协议完整支持，详见 [需求账本](docs/REQUIREMENTS.md)。

本机 Windows 10 19044 自带 ConPTY 会破坏 Sixel 的 DCS 传输；单文件版本已将
固定版本的微软 ConPTY/OpenConsole 源码编入 EXE，并通过真实窗口 Sixel 色块显示验证。
使用 `nemoterm-single-exe-x64-<commit>` 产物时，只需其中的 `nemoterm.exe`。
仅 MinGW 开发对照包仍需保留附带的 DLL 和 OpenConsole。
原生 x64 已实测；`NEMOTERM_CONPTY=system` 可显式选择系统实现用于对照。
完整协议、图片复杂生命周期与真实 agent 仍需继续验收。

窗口缩放已通过实际 ConPTY 尺寸通知验证，并修复备用屏被清空的问题。
主屏与回滚历史默认按新列宽重排，保留软/硬换行、宽字符、组合音标、样式和超链接。
Window 中可关闭重排，恢复裁剪/放大还原行为。备用屏、Sixel 覆盖行及 DEC 双宽/双高行
保持网格布局；图片不被拆分或重采样。`python tests/reflow_window_smoke.py` 检查真实
ConPTY 下的长行、历史、Shift 选择复制与宽高变化；[实现与验证](research/reflow.md)。

内存按用户确认的口径：每窗口私有工作集 <20,000,000 bytes，总工作集约
50,000,000 bytes。量测记录同时列出 ConPTY 和子进程，禁止用主动清空工作集
制造低数值。`scripts/measure-memory.ps1 -ProcessId <PID>` 可复查。
文本与颜色图形基线已低于目标，图片、长历史与真实 agent 还需要继续验收。

[pterm 研究报告](research/pterm-findings.md) 记录制品散列、REA 导入表、官方源码依据
和实测内存。PuTTY 的压缩回滚、按变化绘制和原生数据结构是当前实现的基础。

## 许可与来源

`vendor/putty-0.85/` 是官方发布源码加 Nemoterm 修改，不是全新从零实现。
原版权及 MIT 许可保留于 [LICENCE](vendor/putty-0.85/LICENCE)。
新 Sixel 代码使用 MIT。构建产物同时复制上游许可文件。
下载来源和 SHA-256 见 [需求账本](docs/REQUIREMENTS.md)。
