# Windows x64 试用版 d7db3abf：擦图时保留另一屏

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44669471663/artifacts/14598474988)（4,945,920 字节），SHA-256：`6ef3dd13f856fd0980bcbf6fc0b2ed6bd33d3699c0e7d92a206568e413a00c39`。

主屏上的大张 ReGIS 图擦除后，备用屏上的图现在还能切回并重绘。旧版的 GDI 和 DirectX 都丢失了红线的全部 101 个像素；新版两端都保留 101 个。[对照、原始失败与三种编译器的组件结果](regis-sparse-erase.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm，24 轮 Codex | 3,788,800 | 22,794,240 | 4,497,408 |
| GDI，24 轮 Codex | 5,500,928 | 34,529,280 | 6,807,552 |
| DirectX，24 轮 Codex | 9,711,616 | 44,851,200 | 11,300,864 |
| GDI，六种满屏负载 | 19,128,320 | 55,906,304 | 22,261,760 |
| DirectX，六种满屏负载 | 28,565,504 | 71,708,672 | 32,858,112 |

[24 轮 Codex 实际窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44670104417)：160×48、SarasaTermSC Nerd Light；三组均正常退出。观测到的模块和子进程中没有 WebView。REA 静态检查确认此 EXE 是 x64 PE、没有 CLI 数据目录。

[本版 81 项交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44669471663)通过 79/81。两项失败均是 Codex 启动早期的贴图；输入框稳定后，实际键盘和窗口接口各用两种快捷键，四次均收到一张像素正确的图片。另外，真实 Vim 和 tmux 中的 Vim（GDI、DirectX、两种 TERM）八个窗口通过；Sixel 的两种渲染器也都通过。十项满屏 agent 交互均通过。[原始记录与制品身份](acceptance-d7db3abf.zip)。ReGIS 与原版 XTerm 的历史重绘比较仍有差异。
