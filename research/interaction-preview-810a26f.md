# 单文件交互验收 `810a26f`

[Windows x64 原始制品](https://github.com/xiongnemo/nemoterm/actions/runs/44468952910/artifacts/14503279012)的 `nemoterm.exe` 为 4,871,168 字节，SHA-256 `24deed2cdaa8a3743793c014048ce057333c7f9bc77c4b59de545e5b7bbd27d3`。源码 `810a26f45ec9bf9585ca9d78479b9dd2d4159037`。[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44468952910)与使用该制品的专项回放分别计分。

[同一 EXE 的完整交互汇总](interaction-report-810a26f.zip)：13 个分组、80 个用例中 78 个通过。以下独立重放和其他 CI 作业不并入此分数。

- [滚屏时的选区](selection-during-scroll.md)：旧 EXE 在向下滚屏时 0/8；此 EXE 向下 8/8，向上 8/8。普通与矩形选择都核对了系统剪贴板、实际高亮及应用收到的字节。
- [默认 160×48 真实客户端](agent-grid-810a26f.zip)：10/10，包括 Codex、OpenCode、Claude；GDI 和 DirectX 均验证实际字格、系统鼠标键盘、复制回贴和服务端收件。[连续长粘贴](paste-810a26f.zip)：接口和真实 Ctrl+Shift+V 各 4/4，不丢第二次粘贴前的第一段内容。
- [WSL Vim 首轮](wsl-vim-first-810a26f.zip)3/4，DirectX + `TERM=xterm` 的测试请求文件在跨 WSL 替换时返回 WinError 5。测试改成每次创建独立的编号请求，Vim 应答必须带同一编号；没有改变产品、用户输入或等待时限。[同一 EXE 的重放](wsl-vim-replay-810a26f.zip)4/4（[工作流](https://github.com/xiongnemo/nemoterm/actions/runs/44470601311)），每个窗口都验证了普通鼠标归 Vim、Shift 选择及剪贴板、两次窗口缩放、矩形选择、实际粘贴和退出还原。
- [真实客户端 30 个场景](agent-cases-810a26f.zip)中 28 个通过。两项失败都是 Codex 在启动草稿阶段立即贴图；编辑器就绪后的窗口接口与系统键盘贴图均通过。[客户端输入阶段说明](codex-file-draft-order.md)。
- [Unicode 投递](unicode-first-810a26f.zip)：Nemoterm GDI、DirectX、独立系统 ConPTY 和串行 WinPTY 4 项通过，原始 WinPTY 驱动 1 项失败；后者在 2.594 秒已到服务端，但正常视图未及时读到回复，进程也未自然结束。两个独立 WinPTY 驱动均未启动 Nemoterm。[ReGIS 七个差异](regis-first-expose.md)解释了原始像素、同一历史的第一次强制重绘和组件之间的区别，保留原始失败。

## 内存口径

[同一托管机器的 10 次冷启动记录](pterm-memory-810a26f.zip)（[工作流](https://github.com/xiongnemo/nemoterm/actions/runs/44470176039)）：固定 SarasaTermSC Nerd Light 与同版真实 Codex、160×48。每种配置正反次序各一次。以下数值为回复出现后约 3 秒内的前端进程中位数范围，十进制 MB，shell、控制台宿主和 Codex 均不计入。8 次 Nemoterm 冷启动各自记录了回复后的前端模块和作业进程清单，均未命中受检 WebView、Chromium 或 Electron 名称；这是这些快照的观察。

| 前端 | 私有工作集 | 总工作集 |
|---|---:|---:|
| pterm 0.85 | 3.74–3.78 MB | 21.82–22.58 MB |
| Nemoterm GDI 单标签 | 5.09–5.12 MB | 33.11–34.01 MB |
| Nemoterm DirectX 单标签 | 9.69–9.71 MB | 44.63–44.64 MB |

[六种 GDI 负载](memory-gdi-810a26f.zip)和[六种 DirectX 负载](memory-directx-810a26f.zip)都通过；两个私有工作集峰值均来自密集 Unicode 与 Kitty 图像同屏。每列独立取整个采样期间的最大值（单位：字节）。阈值看前端私有工作集，并非总工作集或整个进程树。

| 前端 | 私有工作集峰值 | 总工作集峰值 | 私有提交量峰值 |
|---|---:|---:|---:|
| GDI | 18,907,136 | 53,682,176 | 21,848,064 |
| DirectX | 29,630,464 | 74,842,112 | 33,107,968 |
