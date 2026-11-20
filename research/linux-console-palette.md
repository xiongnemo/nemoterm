# Linux 调色命令后，Windows 程序能否读回屏幕上的字？

`3308de91` 可以。`9521179a` 的窗口能正常显示调好的颜色，也能显示紧跟命令的 `@`，但同一个 Windows 子程序用 `ReadConsoleOutputW` 读回那一行时，16 个 `@` 全是空格；用 `GetConsoleScreenBufferInfoEx` 读到的也是原来的颜色。这是内置 OpenConsole 解析输出时吞掉后续文字造成的；截图或只测 OSC 4 的回复都看不出问题。

| 相同的六个阶段 | 旧 EXE `9521179a` | 新 EXE `3308de91` |
| --- | ---: | ---: |
| GDI（整段 / 逐字节） | 3/6、3/6 | 6/6、6/6 |
| DirectX（整段 / 逐字节） | 3/6、3/6 | 6/6、6/6 |

Ubuntu runner 上的 `tput -T linux initc` 实际输出 16 条 `ESC ] P nrrggbb`，`tput -T linux oc` 输出 `ESC ] R`。这两种命令都没有结束符；Windows 子程序在每条之后立即写一个 `@`。旧版在旧式设置、旧式复原、现代 OSC 4 设置后改用旧式复原三个阶段失败，在三个现代命令对照阶段通过。修复后，四种组合的窗口像素、16 项 OSC 4 回复、Win32 缓冲区文字和调色板全部符合预期。复原分别与前端 profile 和原生控制台各自的初始颜色比较。使用 `SarasaTermSC Nerd Light`，程序接管鼠标时实按 Shift 拖选，四种组合在每个阶段均看到四格高亮；Ctrl+Shift+C 确实更新剪贴板为 `中文`，子程序没有收到这组快捷键。

在同一新 EXE 上又覆盖了三个阶段：以大写十六进制设置颜色、再复原，以及标准 OSC 2 标题里写入 `R P1123456 is literal title text` 后紧跟两条含无效数字的旧式命令。逐项检查实际标题、文字、颜色和复制。四种组合各通过 **9/9**（含原先六个阶段，不能重复计数）。参考范围是 ncurses 的 `linux` 项和上述兼容语法，不代表 XTerm 或所有终端协议的行为。

- [修复前的四组窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44719881300)：EXE SHA-256 `ee317bc6b8218f6e4dfbe376cda6076b583fc835c6fdbb8d3697f492a0d97224`。
- [修复后原样运行的四组](https://github.com/xiongnemo/nemoterm/actions/runs/44720435221) · [同一 EXE 的语法回归](https://github.com/xiongnemo/nemoterm/actions/runs/44721534168)：EXE SHA-256 `81727d3ba0a9c8deb51dd35923041081527e74645e799d9bc8ad79e52ac1fd44`。
- [原始截图、Win32 读回、剪贴板、子程序字节和 terminfo](linux-console-palette.zip)：内含 12 个未改动的 GitHub 制品；`index.json` 列出每件的编号、SHA-256、产品与测试提交。解开外层 ZIP 后，`python scripts/review-linux-palette.py <制品.zip>` 可离线从原始 PNG 和记录重新计算。旧 EXE 报出三个失败阶段并返回非零。
