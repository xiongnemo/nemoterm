# Windows x64 试用版 032bb830：内嵌 WSL 的像素尺寸与交互验收

[下载已测单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44709431096/artifacts/14616159271)，解压后运行 `nemoterm.exe`。4,948,480 字节，SHA-256 `78d80809569f5f12a8b3651e5af4b3c7b83ceaf02ad7d9acf0026b3843422a64`。

内嵌 WSL 会话在启动、改变窗口和普通字号缩放后，Linux 程序现在能读到真正的文字区像素。托管 WSL1 锁定行列只改字号时，`TIOCGWINSZ` 会保留旧值；终端的像素查询和主动通知仍正确。原生 Ubuntu 的同一 ELF 五组尺寸均正确。见[实际窗口、Sixel 原图与内核对照](wsl-profile.md)。另在四个普通 Windows 窗口核对尺寸通知，76/76 项通过，原始回执在本页证据包中。

| 前端（字节） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,772,416 | 22,724,608 | 4,456,448 |
| NemoTerm GDI，24 轮 Codex | 5,509,120 | 34,582,528 | 6,942,720 |
| NemoTerm DirectX，24 轮 Codex | 9,691,136 | 44,818,432 | 11,210,752 |
| NemoTerm GDI，六种满屏负载 | 18,837,504 | 53,391,360 | 22,417,408 |
| NemoTerm DirectX，六种满屏负载 | 29,167,616 | 72,404,992 | 32,333,824 |

[24 轮 Codex 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44710187828)使用同一台托管 runner，160×48、SarasaTermSC Nerd Light；三组都正常退出，前端运行模块与进程观测未见 WebView。另测六种满屏负载，两种渲染器分别通过严格小于 20,000,000 字节和不超过 30,000,000 字节的私有工作集门槛。表中不包含 shell、控制台宿主或 agent 本身的工作集。

[81 项交互](https://github.com/xiongnemo/nemoterm/actions/runs/44709431096)通过 **79/81**。选区与快捷键 6/6、标签 9/9、满屏客户端 10/10。在客户端接管鼠标时，用 Shift 从「中」的右半拖到「文」的左半，四格高亮，两侧背景未变；十次快捷键复制均为 `中文`。查看[前端像素裁图](agent-wide-032bb830.png)与[原始截图](https://github.com/xiongnemo/nemoterm/actions/runs/44709431096/artifacts/14617302843)。tmux/Vim 的四次剪贴板权限交互和四次常规窗口交互均通过。

编辑器就绪后四次实际 Codex 请求各带一张像素正确的图片。早期四次分别为：正确图片 2，只有文字 2，未收到请求 0。同一次失败没有重发手势或改为通过。[交互回执、采样与原始制品身份](acceptance-032bb830.zip)。

这是开发试用版。试用 EXE 来自已成功的 source-host 构建；交互和内存均按同一份 EXE 核对。交付时 MinGW 便携包和独立单文件两项较长回归仍在运行。完整工作流的严格对照仍有[宽字符编辑边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)、[横向编辑的中间画面](regis-horizontal.md)及 [WSL1](wsl-relay-window.md) 差异。
