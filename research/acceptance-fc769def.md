# `fc769def`：Windows 单文件试用版

[下载本次 GitHub Actions 产物](https://github.com/xiongnemo/nemoterm/actions/runs/44619850611/artifacts/14576329075)。解压后运行 `nemoterm.exe`，4,937,728 字节，SHA-256 `03bd5cb5be895898df77e397df49ec4de702f284a8c667f59b1a4adb816d0575`。本次主要修复[粘贴后立刻按回车时，回车抢在文字之前送达](paste-key-order.md)。以下结果来自 GitHub 托管 Windows；不同二进制的结果分开记录。

## Shift 选区、右键与贴图

[完整交互报告](https://github.com/xiongnemo/nemoterm/actions/runs/44619850611/artifacts/14577922963)验收了 **80/81** 项。真实 Codex、Claude Code、OpenCode 的 160×48 选区组 **10/10**；常规客户端组 **29/30**。用例包括应用接管鼠标时按 Shift 选择可见字符、Ctrl+Shift+C/V、默认右键仅复制、改为右键复制并粘贴后由接收端核对实际文字。其余窗口、设置、鼠标、响铃、剪贴板、shell 和内存组均通过。

唯一未过的是 Codex 0.167.0 刚显示输入文字时实按 Ctrl+V，没有在 20 秒内出现附件。同一早期实按组的 Ctrl+Shift+V 成功；等正式编辑器就绪后的两种按键途径 × 两种快捷键全部成功，OpenCode 的两种途径也都通过。原版 pterm 的[真实窗口对照](codex-bitmap-requests.md)同样能复现过早粘贴，只能据此说明是启动时序，不能保证任何一次早期操作必定失败。原作业仍记失败。

## 内存：前端进程的采样峰值

同一份 EXE，SarasaTermSC Nerd Light，实际网格 160×48。下表为**字节**，各列独立取峰值；不把 shell、Codex 或控制台宿主的内存算进终端前端。

| 工作负载 | 私有工作集 | 总工作集 | 私有提交量 |
| --- | ---: | ---: | ---: |
| 原版 pterm 0.85，24 轮 Codex 追问 | 3,751,936 | 22,700,032 | 4,431,872 |
| Nemoterm GDI，24 轮 Codex 追问 | 5,529,600 | 34,578,432 | 6,828,032 |
| Nemoterm DirectX，24 轮 Codex 追问 | 9,773,056 | 44,859,392 | 11,317,248 |
| Nemoterm GDI，六种满屏图文负载 | **19,206,144** | 53,870,592 | 22,560,768 |
| Nemoterm DirectX，六种满屏图文负载 | **28,819,456** | 71,688,192 | 32,260,096 |

[24 轮对照](https://github.com/xiongnemo/nemoterm/actions/runs/44620580278)在同一台 runner 上分别运行三个前端。每个都收到首条回复与 24 条追问的回复，正常退出；模块和子进程采样未发现受检的 WebView 运行时。pterm 的 SHA-256 与指定的安装版一致。满屏负载分别覆盖密集文本、内嵌图像、动画和三种 Kitty 图形；每个渲染器六项都使用实际选定的后端、未经注入采样。[GDI 原始采样](https://github.com/xiongnemo/nemoterm/actions/runs/44619850611/artifacts/14578497041) · [DirectX 原始采样](https://github.com/xiongnemo/nemoterm/actions/runs/44619850611/artifacts/14577982507)。

## 关窗口或重启 shell 时，迟到的剪贴板去了哪里？

独立剪贴板所有者在收到 Windows 的取数请求后先不交付文字。GDI、DirectX 各关掉发起请求的窗口，再放行旧文字：两个仍运行的 shell 都没收到旧文字；随后粘贴新文字，只有目标 shell 收到，而且恰好一次。在 GDI 原生断开对话框上，又让原窗口连续四次重启 shell：窗口句柄不变、会话身份和子 PID 改变，四次均先重启再释放，旧文字均未混入新会话。全部正常退出。[同一单文件的原始回放](https://github.com/xiongnemo/nemoterm/actions/runs/44623358170)。

原始完整 CI 中，**另一份 MinGW 便携 EXE**（`9e983320…`）的旧测试直接构造内部完成消息，已经不是一次有效的剪贴板请求。原失败记录保留；同一便携 EXE 改用真实剪贴板后，[关闭](https://github.com/xiongnemo/nemoterm/actions/runs/44623358941)通过，[同窗重启](https://github.com/xiongnemo/nemoterm/actions/runs/44623817309)在对话框观察器和原生对话框两种模式下各通过四次。这些结果不会改写之前的 CI 状态。

**仍未通过的协议对照。** 原版 XTerm 的[ReGIS 滚屏、擦除和调色时机](regis-presented-pairs.md)、[宽字跨列边界的三处单元格](column-edge-integrity.md)仍有差异。使用内嵌 WSL PTY 时，原始 UTF-8 粘贴 **12/12** 组字节与参考匹配，WSL1 的规范行读取仍把预期的两次读取分成五次；[同文件真实 Vim/tmux 和粘贴记录](paste-key-order.md)。默认 WSL 路径仍使用 ConPTY。这是开发试用版，完整回归没有全绿。

[本页原始证据包](acceptance-fc769def.zip)包括 GitHub 原始 ZIP、每份制品的 ID/摘要、核对结果和原 MinGW 失败；外层 ZIP SHA-256 `ccc74e459b062af5d93a1d2b4c5dc88fe743156f4bac3a70b8b955b4a4c3d25e`。
