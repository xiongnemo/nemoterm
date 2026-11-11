# Nemoterm

Windows 原生 C 终端，基于 PuTTY 0.85 的 MIT 许可终端核心、Win32/GDI 和 ConPTY。
不使用 WebView。**开发中，尚未完成全部现代终端协议与真实 agent 验收。**

这是 PuTTY Windows **pterm 的 downstream fork**，不是 PuTTY 官方版本。
私有项目：[xiongnemo/nemoterm](https://github.com/xiongnemo/nemoterm)。
每次 push/PR 的 GitHub Actions 会执行 Windows 回归与构建，另运行 Linux Sixel
ASan/UBSan；在成功的 Actions run 中下载 `nemoterm-windows-x64-<commit>` artifact。
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
* Ctrl+右键：始终打开上下文菜单，其中有 Copy and Paste。
* Shift+左键拖选：强制选择终端字符网格，绕过应用鼠标模式；备用屏同样适用。
* 没有选中文字时，普通右键在应用鼠标模式下交给应用，否则显示菜单。

## 验证与边界

```powershell
.\scripts\test.ps1
```

当前核心回归包含：鼠标模式 1000/1002/1003、1006、1049 的 12 组组合，
Shift 选择中文与组合字符、普通鼠标字节上报、真彩色/256 色、备用屏恢复、
逐字节 OSC 标题、括号粘贴，以及 Sixel 解码的精确像素/内存预算/异常输入。
这些测试不等于所有终端协议完整支持，详见 [需求账本](docs/REQUIREMENTS.md)。

**当前已知问题：** 本机 Windows 10 19044 自带 ConPTY 会破坏 Sixel 的 DCS
传输；目前仅解码器和终端核心测试通过，实际窗口图片尚未显示正确。
正在补齐传输链路。窗口 resize 和完整鼠标兼容性也仍需专项验收。

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
