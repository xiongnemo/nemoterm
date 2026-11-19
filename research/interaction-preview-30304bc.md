# 单文件交互验收 `30304bc`

[Windows x64 原始制品](https://github.com/xiongnemo/nemoterm/actions/runs/44472521397/artifacts/14505341500)来自提交 `30304bc5786a9aac68177084f44c9084ec6c2494`。其中 `nemoterm.exe` 为 4,871,680 字节，SHA-256 为 `712ed73e131f6498a354aac6eae77e31dd95a703f952a14189504486384b449a`。[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44472521397)和独立专项回放都使用 GitHub 托管 runner；专项回放不额外计入整套交互的分母。

[完整交互汇总](interaction-report-30304bc.zip)：13 个分组共 **78/80** 通过；只有 Codex 启动时立即贴图的两种输入途径未通过。

- [分栏滚屏选择：截图和原始回执](selection-split-scroll.md)。同一窗口操作在上一版 0/32，本版 32/32。系统键鼠回放在旧版 0/4、本版 4/4；[追加回放](selection-split-clipboard-30304bc.zip)也验证了实际右键只复制，Ctrl+Shift+V 才向应用发送选中的字及附标。
- [默认 160×48 的 Codex、OpenCode、Claude](agent-grid-split-30304bc.zip) 10/10。[更广的客户端场景](agent-cases-split-30304bc.zip) 28/30：窗口接口和系统键盘在 Codex 刚启动时立即贴图均失败；编辑器就绪后，两种途径均通过。[输入阶段和现有限制](codex-file-draft-order.md)。
- [关闭确认和设置对话框](https://github.com/xiongnemo/nemoterm/actions/runs/44472521397/artifacts/14504598438)：在双标签中关闭当前会话、关闭整个窗口，以及关闭独立窗口三种情形，点 Cancel 或按 Esc 后立即打字，都能送达原子进程。
- [远程 DPI 检查](https://github.com/xiongnemo/nemoterm/actions/runs/44472521397/artifacts/14505606980)通过，保留了英文和简体中文设置在 100%、125%、150%、175%、200% 的托管桌面记录。
- [WSL Vim](wsl-vim-split-30304bc.zip) 的两种渲染器 × 两种 TERM 均通过。每种组合检查普通鼠标、Shift 选择不改变 Vim 缓冲区、两次缩放、矩形选区，以及实际粘贴、保存和退出后的画面还原。
- [连续两次粘贴长文本](paste-split-30304bc.zip)：接口操作 4/4，系统 Ctrl+Shift+V 4/4。[Unicode 投递](unicode-split-30304bc.zip)本轮 5/5，覆盖 GDI、DirectX 和三个独立对照；[上一轮原始 WinPTY 的失败](interaction-preview-810a26f.md)仍保留。
- 完整回归中的三个 ReGIS 核心作业继续报告失败。[历史原图、重绘与差异说明](regis-first-expose.md)；不能据此版本宣称 ReGIS 像素全部一致。

## 回复后的前端占用

[10 次冷启动原始采样](pterm-split-memory-30304bc.zip)（[远程工作流](https://github.com/xiongnemo/nemoterm/actions/runs/44473385411)）。同一台 Windows runner、同一版 Codex、160×48 和 SarasaTermSC Nerd Light。每种配置正、反序各一次，每次取回复后约 3 秒的中位数。以下仅列单标签与 pterm；独立窗口也保存在原始记录里。只计前端进程；单位为十进制 MB。

| 前端 | 私有工作集 | 总工作集 |
|---|---:|---:|
| pterm 0.85 | 3.744–3.797 | 21.869–22.684 |
| Nemoterm GDI 单标签 | 5.112–5.157 | 33.198–34.103 |
| Nemoterm DirectX 单标签 | 9.679–9.683 | 44.675–44.687 |

## 160×48 压力峰值

[GDI 原始记录](memory-gdi-split-30304bc.zip)和[DirectX 原始记录](memory-directx-split-30304bc.zip)各 6/6。每列分别取六种负载中所有采样的最大值，以字节为单位。两个渲染器的私有工作集峰值均来自密集 Unicode 和 Kitty 图像同屏。目标分别为 GDI <20,000,000、DirectX <30,000,000 字节，仅按前端私有工作集验收。

| 前端 | 私有工作集峰值 | 总工作集峰值 | 私有提交量峰值 |
|---|---:|---:|---:|
| GDI | 19,185,664 | 53,960,704 | 22,106,112 |
| DirectX | 29,564,928 | 72,839,168 | 32,792,576 |
