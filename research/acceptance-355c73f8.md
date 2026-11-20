# Windows x64 单文件试用版 `355c73f8`

[下载本次 EXE](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334/artifacts/14653593498)，4,942,336 字节，SHA-256 `12b0ba38581401d4e2a858c0c5d644fa2abe057e8cbe306dc3b0babd43b14e50`。保留四边的 Win32 风格标签；应用现在可以用 `CSI > Ps p` 设置打字时的鼠标显示方式。两种 profile 下 32 个按键/移动场景均与 XTerm 412 的可见状态和回执相符，详见[隐藏指针后拖选中文的对照图](pointer-hiding-355c73f8.md)。

[合并报告](https://github.com/xiongnemo/nemoterm/actions/runs/44790406809/artifacts/14654669422)从同一 EXE 的原始记录复核。严格交互为 **79/81**，全部执行。两项未通过是 Codex 输入框就绪前的粘贴：四种按键与送入路径在首次提交时均只有文字。编辑器就绪后，Ctrl+V、Ctrl+Shift+V 各按两种输入路径验证，**4/4** 首次提交带有且只有一张正确原图。合并报告保留原来的失败状态。

在 160×48、SarasaTermSC Nerd Light 的窗口里，Codex、Claude Code、OpenCode 的 [18/18 项真实快捷键及右键行为](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334/artifacts/14656586522)通过，覆盖默认右键仅复制、选配复制并粘贴。十个真实客户端窗口都正确高亮并复制了宽字符「中文」；关闭确认选「取消」后，键入的编辑和提交也都到达原客户端。窗口启动和提交后的 20 次采样都未发现已知浏览器模块或浏览器子进程。[查看实际 Shift 高亮截图](agent-grid-355c73f8.png)。

| 前端进程负载 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| pterm，24 轮 Codex | 3.75 MB | 22.70 MB | 4.44 MB |
| GDI，24 轮 Codex | 5.50 MB | 34.59 MB | 6.92 MB |
| DirectX，24 轮 Codex | 9.70 MB | 44.83 MB | 11.25 MB |
| GDI，六种满屏负载 | 19.40 MB | 54.16 MB | 23.18 MB |
| DirectX，六种满屏负载 | 28.82 MB | 74.10 MB | 32.68 MB |

MB 按十进制；[独立字节级复核](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334/artifacts/14655269606)得到 GDI **19,402,752 字节**、DirectX **28,823,552 字节**。这些数字只计前端进程。pterm 的[轻量化调查](pterm-findings.md)区分了系统共享页、私有页以及子进程。

英、中各 [12/12 个实际 DPI 场景](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334/artifacts/14653549437)均通过；两个渲染器共 [8 帧 Sixel](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334/artifacts/14653958420)与参考像素相符。完整回归另有 ReGIS 重绘前像素、宽字符边界、发行版 terminfo、WSL1 几何和粘贴等差异。[协议覆盖表](../docs/PROTOCOL_COVERAGE.md)；[该提交的所有原始作业](https://github.com/xiongnemo/nemoterm/actions/runs/44785665334)。

右侧标签 DirectX 选区：另一份 MinGW 便携构建（SHA-256 `21ccda742785c82ae5d40a61d4c7445226a3898eb2ec7a45b33c6fbc680fabb0`）曾在进入备用屏后 8 秒没有读到查询应答。[同一便携 EXE 和本次交付单文件的专项回放](https://github.com/xiongnemo/nemoterm/actions/runs/44790691905)均完成了整个右侧标签选区用例，各自 7/7 项屏幕切换检查通过。原超时原因未确定，不能据此宣称它已经修复。

[保留的原始失败、两份回放、合并报告、内存采样与静态 PE 记录](acceptance-355c73f8.zip)。
