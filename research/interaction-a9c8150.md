# a9c8150 的交互验证

远程构建的四舍五入大小约 4.86 MB（4,860,928 字节）；SHA-256 `a1b2e279d105575649ffc73a913129085d931200d53a2036409891cd8a5764a4`。[源构建](https://github.com/xiongnemo/nemoterm/actions/runs/44338343977)的制品 ID 为 `14443251390`。以下结论仅针对这一份可执行文件。

[WSL 原始回放](wsl-less-verified-a9c8150.zip)来自 [44339705048](https://github.com/xiongnemo/nemoterm/actions/runs/44339705048)，制品 ID `14441894634`，ZIP SHA-256 `02517c08f057abdc43527a24b147aabb99a815b2bbb40e87d46725ad393225bf`。Ubuntu 24.04 `less` 590、SarasaTermSC Nerd Light。`TERM=xterm` 和继承的 `xterm-256color`，分别使用调试接口按键与 runner 系统键盘、分别直接运行与在 `script(1)` 中运行，共 **8/8**。每次都从第 1 行开始，向下后首行为 2，翻页后为 34，搜索后为 220；按 `q` 恢复了打开前的可见文本，子程序自然退出，WSL 清理记录确认 shell 已退出。已核对八组共 48 张截图的哈希。

四份原始 PTY 输入日志均为 `1b 4f 42`（下）、`1b 5b 36 7e`（下一页）、`/ZEBRA_NEEDLE`、回车、`q`，前两项和 WSL 的 `tput kcud1`、`tput knp` 一致。修复前 API 错发 `1b 4f 72` 的[同组对照](wsl-less-diagnostic-1fef0e3.zip)仍保留。这验证了上述交互，不等于全部键盘协议或全部 terminfo 行为都已验证。

[同一 EXE 的六组真实客户端窗口报告](agent-grid-a9c8150.zip)：正式网格 160×48，字体 SarasaTermSC Nerd Light。Claude Code、Codex、OpenCode 分别在实际 GDI 和 DirectX 下，从汉字后半格开始的系统鼠标拖选均复制出完整的 `中文`，六组回环服务都收到了选区。原始 Actions 制品 `14443536380`。

[WSL `img2sixel` 首次尝试](wsl-sixel-first-a9c8150.zip)，运行 `44339704723`，制品 `14443925929`：两种渲染器的显示前黑底检查均通过。Ubuntu 的 `libsixel-bin 1.10.3-3build1` 默认量化只定义了四个 Sixel 颜色寄存器，`sixel2png` 将原 PNG 的 36 个黑点全部解成 `(247,0,0)`。测试在独立解码与原 PNG 的比对处失败，尚未测到两个渲染器画图后的像素。保留了两个原始 PNG、实际 Sixel 字节、上游工具身份及错误。后续回放使用同像素的 RGB PNG 和明确的 xterm256 调色板，仍要求检查原图、独立解码及实际终端像素。

[WSL Sixel 回放的原始字节和截图](wsl-sixel-verified-a9c8150.zip)来自 [运行 44340989668](https://github.com/xiongnemo/nemoterm/actions/runs/44340989668)，制品 `14444296324`，ZIP SHA-256 `132a304f394ecb5e63f8bf81f2a72bcf45ea527e33fd1fa269318e4baaa1592e`。编码后 3,855 字节，独立解码出的 24×18 像素与原始图完全相同。实际 GDI 和实际 DirectX 的显示前、显示后、重绘、清除四个阶段，图像和四边外一像素组成的 26×20 区域均为零像素差异。原始图、独立解码图和两个渲染器保存的八张窗口截图均已离线复核；这是对真实应用这条输出路径的验证。

[同一产品的 30 项客户端交互结果](agent-interaction-a9c8150.zip)来自 `14443806686`。28 项通过，包括三个客户端、两种渲染器各自的默认右键仅复制与可选复制并粘贴。未通过的两项为 Codex 刚出现首次输入标记时贴图（系统输入及调试接口）；正式输入框就绪后两种方式均通过，OpenCode 贴图也通过。此前的[独立宿主与客户端源码对照](agent-unicode-boundary.md)区分了 Codex 启动草稿与正式输入框。这些失败未被覆盖。六个默认网格窗口的启动和提交阶段共有十二份进程和模块记录，均没有匹配测试所检查的浏览器引擎模块或进程。

真实客户端操作期间的前端私有工作集（字节）：每个单窗口、单标签在启动、回复、复制、编辑和提交五个时刻分别采样，取这五点的最大值。未计入 shell 或 agent 进程。它们不是整个运行期间的连续峰值，也不是六种压力负载的结果。

| 客户端 | GDI | DirectX |
|---|---:|---:|
| Codex | 6,733,824 | 12,787,712 |
| Claude Code | 6,938,624 | 12,922,880 |
| OpenCode | 6,995,968 | 12,828,672 |

[完整交互汇总和十二组内存采样](interaction-full-a9c8150.zip)核对通过 72/74，未通过项：`agent-image-codex`、`agent-image-system-codex`。六种 160×48 负载每种渲染器均通过；前端进程的采样峰值（字节）如下。

| 渲染器 | 私有工作集 | 总工作集 | 私有提交 |
|---|---:|---:|---:|
| gdi | 19,791,872 | 56,586,240 | 22,753,280 |
| directx | 28,491,776 | 71,376,896 | 32,264,192 |
