# Windows x64 试用版 371a6f01

[下载单文件制品](https://github.com/xiongnemo/nemoterm/actions/runs/44754283954/artifacts/14635929258)，解压后运行 `nemoterm.exe`。4,940,800 字节，SHA-256 `98d63fdb00e1d54d66c60019beb6622d002452933ec61854fec51d48630f9248`。下列验收使用同一份 Windows x64 EXE。

**候选版状态：** 远程交互汇总和截图已出，Windows x64 综合回归和隔离单文件回归仍在运行。当前 `dist` 仍为 `03d0e0bc`。

首次用 `--list-shells` 查询已安装的 shell，不再创建 Default profile。三种查询方式返回相同结果；正常启动仍会创建 Default，传给子程序的同名参数也保持原样。Git Bash 共 24 次启动和关闭均自然退出，无残留。旧版曾有一次 10 秒超时，未复现，不能认定已找到超时的原因。[修复前后的原始回执](shell-list-first-use.zip)。

`TERM=xterm` 的退格键能力查询现在保留请求名的原始拼写，与绑定相同终端数据库的 XTerm 比对为 64/64；系统自带的另一份数据库仍有差异。[比较记录](https://github.com/xiongnemo/nemoterm/actions/runs/44754283954/artifacts/14635769707)。

[原始交互报告](https://github.com/xiongnemo/nemoterm/actions/runs/44754283954/artifacts/14639915736)：80/81；未通过：`agent-image-codex`。Codex 输入框就绪后，两种快捷键分别经系统实按和窗口接口贴图，4/4 首条消息都收到一张像素正确的图片，后续无重复。启动时刚看见输入提示的四次结果：2 次纯文字，2 次正确图片；成功的两次在按键前已收到 Codex 的就绪标志，纯文字的两次都未收到。这解释了为什么第一次看见输入文字不能用来判定是否已能贴图。[原始提交回执](https://github.com/xiongnemo/nemoterm/actions/runs/44754283954/artifacts/14637717010)。

GDI 与 DirectX 的五种全屏布局、同步更新期间的 13 种选区操作和 24 项复制及右键组合分别通过。Codex、Claude Code、OpenCode 的十个窗口均有独立截图复核；中英文原生 DPI 各 12/12。Vim、tmux 内的 Vim 与 Sixel 窗口记录同时保留。

在独立窗口和标签页的 100%–200% 真实系统缩放下，复核响铃、响铃过载、渲染、字符编码、画线字符和界面语言六页。44 帧里 264 份页面记录的受测控件均完整显示，未被底部按钮覆盖。原始中文截图也显示一个翻译遗漏：画线字符子页的标题和分组说明仍为英文。见证据包内的 `settings-pages.png` 和 `settings-pages.json`。

| 前端负载（不计子进程，十进制 MB） | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| GDI，六种 160×48 满屏负载 | 19.25 MB | 55.97 MB | 22.43 MB |
| DirectX，相同六种负载 | 29.20 MB | 74.46 MB | 33.08 MB |
| 原版 pterm，真实 Codex 24 轮 | 3.80 MB | 22.75 MB | 4.49 MB |
| GDI，真实 Codex 24 轮 | 5.57 MB | 34.64 MB | 6.86 MB |
| DirectX，真实 Codex 24 轮 | 9.77 MB | 44.91 MB | 11.30 MB |

[同一 EXE 的可复核记录和原始制品身份](acceptance-371a6f01.zip)。[完整 Actions 回归](https://github.com/xiongnemo/nemoterm/actions/runs/44754283954)保留所有结论。ReGIS、宽字边界及部分 WSL1 协议等历史差异仍在；本版不是全部协议通过的声明。
