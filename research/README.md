# 当前测试版与待审阅材料

- [当前 dist 试用版 `226ddd98` 的交互和内存验收](acceptance-226ddd98.md)。[试用版历史和原始制品](../docs/PREVIEW_HISTORY.md)。
- [终端程序请求改变行列数时保留 Shift 选区](selection-page-size.md)：`226ddd98` 的 GDI 和 DirectX 实际窗口，修复前 4/28、修复后 28/28。
- [标签中键误关的修复和两版实际鼠标记录](tab-middle-gestures.md)。
- [Codex 输入就绪前后的贴图](codex-bitmap-requests.md)单列启动草稿和正常输入的结果；更早的 [`dc8b6913` 验收记录](https://github.com/xiongnemo/nemoterm/blob/212f1fcbf302e6b46d3ae2a887ac70915e367082/research/acceptance-dc8b6913.md) 已归档。
- [80／132 列、窗口尺寸与 Shift 选区](column-modes.md)：旧版、只改前端的版本，以及同时修复内置控制台后的原始记录和截图。
- [混合 profile 的关闭超时](profile-close-dc8b6913.md)：一次原始失败、对应转储的分析及相同 EXE 的六次独立复测。
- [主屏变窄后的 Shift 选区](selection-reflow.md)、[终端程序编辑列时的选区](selection-column-edits.md)，以及[宽字在行尾与 XTerm 的差异](column-edge-integrity.md)。
- [WSL profile 与子进程退出](wsl-profile.md)、[WSL 字节转发和窗口退出](wsl-relay-window.md)。
- [擦除大张 ReGIS 图后保留另一屏的图](regis-sparse-erase.md)：GDI、DirectX 的旧版失败与新版回放。
- [ReGIS 首帧](regis-first-expose.md)与[窗口重绘前后画面](regis-presented-pairs.md)。
- [pterm 的进程和内存](pterm-findings.md)：原版 PuTTY 0.85 的二进制证据、私有与总工作集，以及与 Nemoterm 的比较范围。

测试需要的固定输入在 [testdata/upstream](../testdata/upstream)。已完成工作的原始截图和记录在[本轮清理前的版本](https://github.com/xiongnemo/nemoterm/tree/408a251dca608961d936f0200001cdd2f649079b/research)和[更早的归档](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)。
