# Windows x64 试用版 bda4d485：窗口尺寸通知与交互验收

[下载已测单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44703215110/artifacts/14613364439)，解压后运行 `nemoterm.exe`。4,947,968 字节，SHA-256 `ac45d753b7072265bb2d41bc4f29cd30549f3e384d012838113cc51172726744`。

程序订阅模式 2048 后，更改窗口或字号会收到新的行列数和文字区像素尺寸。[四个实际窗口通过 76/76 项](inband-resize.md)，包含子程序在读到通知时取到的 Windows 控制台尺寸。

| 前端（字节） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,772,416 | 22,671,360 | 4,452,352 |
| NemoTerm GDI，24 轮 Codex | 5,562,368 | 34,574,336 | 6,983,680 |
| NemoTerm DirectX，24 轮 Codex | 9,699,328 | 44,761,088 | 11,182,080 |
| NemoTerm GDI，六种满屏负载 | 19,599,360 | 56,500,224 | 23,162,880 |
| NemoTerm DirectX，六种满屏负载 | 29,278,208 | 74,317,824 | 33,251,328 |

[24 轮 Codex 对照](https://github.com/xiongnemo/nemoterm/actions/runs/44704073412)使用同一台托管 runner，160×48、SarasaTermSC Nerd Light；三组都正常退出，前端运行模块与进程观测未见 WebView。另测六种满屏负载，两种渲染器分别通过严格小于 20,000,000 字节和不超过 30,000,000 字节的私有工作集门槛。表中不包含 shell、控制台宿主或 agent 本身的工作集。

[81 项交互](https://github.com/xiongnemo/nemoterm/actions/runs/44703215110)通过 **79/81**。选区与快捷键 6/6、标签 9/9、满屏客户端 10/10。在客户端接管鼠标时，用 Shift 从「中」的右半拖到「文」的左半，四格高亮，两侧背景未变；十次快捷键复制均为 `中文`。查看[前端像素裁图](agent-wide-bda4d485.png)与[原始截图](https://github.com/xiongnemo/nemoterm/actions/runs/44703215110/artifacts/14614082389)。tmux/Vim 的四次剪贴板权限交互和四次常规窗口交互均通过。

编辑器就绪后四次实际 Codex 请求各带一张像素正确的图片。早期四次分别为：正确图片 0，只有文字 4，未收到请求 0。同一次失败没有重发手势或改为通过。[交互回执、采样与原始制品身份](acceptance-bda4d485.zip)。

这是开发试用版。交付时两项较长的打包回归仍在运行；交付的文件来自已经成功的 source-host 构建。完整工作流的严格对照仍有[宽字符编辑边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)、[横向编辑的中间画面](regis-horizontal.md)及 [WSL1](wsl-relay-window.md) 差异。
