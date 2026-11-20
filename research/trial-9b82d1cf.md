# Windows x64 试用验收：`9b82d1cf`

[单文件 EXE](https://github.com/xiongnemo/nemoterm/actions/runs/44837714426/artifacts/14679302876) · [原始完整运行](https://github.com/xiongnemo/nemoterm/actions/runs/44837714426)
文件：4,947,968 字节，SHA-256 `ab3fc6ef207bcc5ef121bc8ad6f1d2992bacea2a6333b421c78a606f6cd8a3bc`。

严格交互：**80/81**。未通过：agent-image-system-codex。未执行：无。
全文按原始结果计分；完整运行还包括此报告未覆盖的协议和平台测试。

| 前端 / 负载 | 私有工作集峰值（字节） | 总工作集峰值（字节） | 私有提交峰值（字节） |
|---|---:|---:|---:|
| pterm / 24 轮 Codex | 3,788,800 | 22,728,704 | 4,476,928 |
| GDI / 24 轮 Codex | 5,459,968 | 34,537,472 | 6,762,496 |
| DirectX / 24 轮 Codex | 9,682,944 | 44,822,528 | 11,124,736 |
| GDI / 六种满屏负载 | 19,075,072 | 56,033,280 | 22,515,712 |
| DirectX / 六种满屏负载 | 28,753,920 | 72,101,888 | 32,759,808 |

Codex、Claude Code、OpenCode：18/18 项快捷键和右键行为通过。10 个窗口的实际 Shift 选区都复制出「中文」；选区及相邻字格见[原始验收包](trial-9b82d1cf.zip)内的 `windows-trial.zip → report/selection/selected.png`。
双向混排：20/20 次拖选与原始画面及剪贴板一致；10/10 个窗口完成反向复制、粘贴并提交到应用服务。见同包 `report/bidi.json`。
10 个真实 agent 窗口的启动、提交后共 20 次采样：前端已加载模块和测试作业进程均未发现已知 WebView/浏览器标记。此项只覆盖采样时刻。
GDI 和 DirectX 的 8 帧 Sixel 与参考像素相符。两种渲染器在 `TERM=xterm` 和 `TERM=xterm-256color` 下还分别验证了 [Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44837714426/artifacts/14679467490) 和 [tmux 内的 Vim](https://github.com/xiongnemo/nemoterm/actions/runs/44837714426/artifacts/14678554193) 的中文矩形选区。字体为 SarasaTermSC Nerd Light。

| Codex 粘贴时机 | 输入方式 | Ctrl+V 首次提交 | Ctrl+Shift+V 首次提交 | 原始用例结果 |
|---|---|---|---|---|
| first visible input | window API | exact-image | exact-image | passed |
| first visible input | physical | text-only | text-only | failed |
| after idle redraw | window API | exact-image | exact-image | passed |
| after idle redraw | physical | exact-image | exact-image | passed |

真实应用窗口的前端私有工作集（十进制 MB）

| 客户端 | GDI | DirectX |
| --- | ---: | ---: |
| codex | 7.10 | 17.58 |
| claude | 11.85 | 17.70 |
| opencode | 11.79 | 17.63 |

从发现窗口到提交回复：1425 次定时采样，另有 50 次操作节点采样。只计终端前端，不含 agent 和控制台宿主。取所有对应窗口的实测最大值；采样之间的瞬时峰值未知。

[已知问题与原始失败](../docs/KNOWN_ISSUES.md) · [现代协议范围](../docs/MODERN_VT.md)。
