# Windows 合并字符消息：输入三个“中”，应用应该收到几个？

Windows 的 Unicode 窗口可以在一条字符消息的 `lParam` 低 16 位报告重复次数。旧版 `5ccb22b4` 在此路径只交付第一个字符。例如发送一次 `WM_CHAR`，码点 `U+4E2D`、计数 3，子程序用 `ReadFile` 和 `ReadConsoleW` 都只收到一个 `中`。这是受控的窗口消息测试；没有假设每次物理按住键或每种输入法都会合并消息。

`b04ca12a` 按消息给出的次数交付完整字符。普通文本以固定大小的缓冲分批发送；Kitty 键盘模式分别发送可独立编辑的字符事件。UTF-16 分别到达的高低代理必须能配对；不完整的单位不变成额外字符。零计数沿用原先一次的兼容行为，`UNICODE_NOCHAR` 探测仍然不产生输入。

| 真实子程序的读取方式 | 旧版（相同 18 项） | 修复版（相同 18 项） | 修复版额外的 4 项 |
| --- | ---: | ---: | ---: |
| `ReadFile`，UTF-8 | 4/18 | 18/18 | 4/4 |
| `ReadConsoleW`，UTF-16 | 4/18 | 18/18 | 4/4 |

两种读取均覆盖普通输入和 Kitty 关联文本，包括 `WM_SYSCHAR`、`WM_IME_CHAR`、UTF-16 代理对、UTF-32 表情、孤立代理及能力探测。额外用例跨过批次边界（65 个 `𠀀`），并检验高低代理的计数不相同时后续 ASCII 保持顺序。每个用例用两次 DSR 回复界定实际子程序读到的字节，核对程序自然退出。使用 `SarasaTermSC Nerd Light`。此专项与同作业的 XTerm 发行版 terminfo 比对分别计分；后者仍有原始差异。

[旧版 Windows 运行](https://github.com/xiongnemo/nemoterm/actions/runs/44806661031/artifacts/14663381712) · [修复版 Windows 运行](https://github.com/xiongnemo/nemoterm/actions/runs/44806811770/artifacts/14663783744) · [两份原始回复档案和来源 SHA-256](character-repeat-native.zip)。两份产品 EXE 的 SHA-256 分别为 `78a2596c83c1b413330c4eada560dc396dd7fd4406e8425878e415b66e10b945`、`ab0cba09fd6c33f3620fdf7e5ae92b49b60026b5376dfae8290171c5a84045cc`，均为 4,943,360 字节。
