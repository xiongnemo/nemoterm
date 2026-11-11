# Nemoterm

Windows 原生 C 终端，基于 PuTTY 0.85 的 MIT 许可终端核心、Win32/GDI 和 ConPTY。
不使用 WebView。**开发中，尚未完成全部现代终端协议与真实 agent 验收。**

这是 PuTTY Windows **pterm 的 downstream fork**，不是 PuTTY 官方版本。
私有项目：[xiongnemo/nemoterm](https://github.com/xiongnemo/nemoterm)。
每次 push/PR 的 GitHub Actions 会执行 Windows 回归与构建，另运行 Linux Sixel
及超链接核心的 ASan/UBSan；在成功的 Actions run 中下载 `nemoterm-windows-x64-<commit>` artifact。
产物含 EXE、许可证、构建 commit 与 SHA-256，保留 30 天。

## 构建与启动

需要 Windows 10 1809+、MinGW-w64 GCC、Python。构建脚本在项目内安装固定版本的 CMake/Ninja。

```powershell
.\scripts\build.ps1 -Tests
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

默认字体为机器上安装的 `SarasaTermSC Nerd Font Light`，UTF-8，ClearType。
字体文件本身没有 U+F120/U+F07B 两个图标；缺失字体字形仍需要补充回退方案。

## 交互

* Ctrl+Shift+C：复制选择内容；Ctrl+Shift+V：粘贴系统剪贴板。
* 右键已选择的文本：默认只复制；可在 Window/Selection 改为复制并粘贴。
  复制并粘贴使用当前选区，系统剪贴板繁忙时也不会粘贴旧内容。
* Ctrl+右键：始终打开上下文菜单，其中有 Copy and Paste。
* Shift+左键拖选：强制选择终端字符网格，绕过应用鼠标模式；备用屏同样适用。
* OSC 8 链接悬停显示完整地址，并为同组标签加下划线；Ctrl+左键打开，
  Ctrl+右键菜单可打开或复制地址。拖动或按住 Shift 仍选择标签文本。
* 没有选中文字时，普通右键在应用鼠标模式下交给应用，否则显示菜单。
* 默认使用现代 xterm 功能键、Home/End 和修饰键编码；命名配置可继续选择旧键盘模式。
  Ctrl+PageUp/PageDown 在默认模式下发送给应用；Shift+PageUp/PageDown 保留本地滚动。

## 验证与边界

```powershell
.\scripts\test.ps1
```

当前核心回归包含：鼠标 9/1000/1001/1002/1003、1005/1006/1015/1016 编码协商、
1004 焦点、1007 备用屏滚轮、四向滚轮、两个侧键、修饰键与捕获取消，及 1049 备用屏组合，
Shift 选择中文与组合字符、普通鼠标字节上报、真彩色/256 色、备用屏恢复、
冒号RGB、斜体/隐藏、五种下划线及独立下划线颜色、压缩历史中的样式还原，
DECSCUSR 光标形状/闪烁、DEC 12，以及 DECRQSS 的样式/滚动边界/尺寸读回，
XTGETTCAP 终端名/颜色/逻辑按键查询、应用光标模式及修饰键组合，
逐字节 OSC 标题、调色板/默认颜色设置与查询、括号粘贴，以及 Sixel 解码的精确像素/内存预算/异常输入。
OSC 8 已接入字符格、压缩历史、覆盖/擦除和按已绘制画面命中地址的核心接口；
链接记录上限为 256 KiB / 1024 条，旧编号回收后不会指向新地址。
Terminal/Hyperlinks 设置可禁用 OSC 8，或允许注册的自定义 URI 协议。
默认可打开 HTTP、HTTPS、FTP、mailto 和本机 Windows 驱动器的 file 链接；
file 主机必须为空、localhost 或匹配本机名称。远程文件地址可复制，不能直接打开。
`python tests/hyperlink_window_smoke.py` 通过临时 URI 处理器验证实际打开的完整地址、
悬停分组像素、最长地址、菜单/剪贴板、配置开关、Shift 拖选、四种应用鼠标模式、
捕获取消、缩放及同步输出。另用 6,000 个长链接与 800 张 Sixel 验证淘汰和进程内存。
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

本机 Windows 10 19044 自带 ConPTY 会破坏 Sixel 的 DCS 传输；构建现在随程序
分发固定版本的微软 ConPTY DLL/OpenConsole，已通过真实窗口 Sixel 色块显示验证。
请将整个产物目录一起解压，保留 EXE 旁的 DLL 和 OpenConsole。
原生 x64 已实测；`NEMOTERM_CONPTY=system` 可显式选择系统实现用于对照。
完整协议、图片复杂生命周期与真实 agent 仍需继续验收。

窗口缩放已通过实际 ConPTY 尺寸通知验证，并修复备用屏被清空的问题。
主屏宽度变化仍采用裁剪/恢复策略，尚未实现历史文本 reflow。

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
