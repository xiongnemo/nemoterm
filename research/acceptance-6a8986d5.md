# Windows x64 试用版 6a8986d5：应用可以只拉高或只拉宽窗口

[下载单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44680462961/artifacts/14604052453)（4,946,944 字节），SHA-256：`8081fb38fe3c22bc3f0e3ebf2eca7239b568878d2623940871be59a1a44da8c2`。

应用请求纵向最大化时，窗口保留左右边界；横向最大化时，窗口保留上下边界。禁止远程调整大小时，两种请求都不会改变窗口。独立窗口与标签窗口从 12/36 提高到 36/36，另有 11/11 项双标签检查通过。[窗口几何记录以及与 XTerm 412 的差异](window-maximise.md)。

| 同机前端，字节 | 私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm，24 轮 Codex | 3,772,416 | 22,679,552 | 4,468,736 |
| Nemoterm GDI，24 轮 Codex | 5,693,440 | 37,040,128 | 7,114,752 |
| Nemoterm DirectX，24 轮 Codex | 9,949,184 | 47,280,128 | 11,603,968 |
| Nemoterm GDI，六种满屏负载 | 18,898,944 | 53,329,920 | 22,736,896 |
| Nemoterm DirectX，六种满屏负载 | 28,995,584 | 74,260,480 | 32,702,464 |

[24 轮 Codex 会话](https://github.com/xiongnemo/nemoterm/actions/runs/44681201406)固定 160×48、SarasaTermSC Nerd Light。三组均正常退出，采样时未观察到 WebView 模块或进程。压力测试的每一栏取六种满屏负载的最高值，内存上限按前端私有工作集核对。

[本版交互回归](https://github.com/xiongnemo/nemoterm/actions/runs/44680462961)验证 **79/81**。仍未通过：`agent-image-codex`、`agent-image-system-codex`。启动早期两种输入方式下的 Ctrl+V 和 Ctrl+Shift+V 均未提交图片（0/4）；输入框就绪后的四组全部收到与原图逐像素一致的位图（4/4）。[pterm 和 Windows Terminal 的独立启动对照](codex-bitmap-requests.md)。鼠标按住时改变行宽的选择操作复核通过 34/34。另有十项满屏客户端交互、八个 WSL Vim/tmux 场景和两种渲染器的 WSL Sixel 通过。[交互和内存原始记录](acceptance-6a8986d5.zip)。

四侧标签预览首次通过三侧，修正测试的按键同步后，同一份 EXE 四侧全部通过。原始截图清楚记录隐藏标签更新，且键盘输入送往前台标签。托管机实际使用 GDI 回退。[首次失败与四侧复测原始记录](tab-hover-6a8986d5.zip)。全量 CI 仍保留[宽字符编辑边界](column-edge-integrity.md)、[ReGIS 历史画面](regis-presented-pairs.md)和 [WSL1](wsl-relay-window.md) 的严格差异。

上述 81 项使用本版构建时的测试清单。后来增加的「按住 Shift 时应用填充或复制矩形」实际窗口[单独回放](https://github.com/xiongnemo/nemoterm/actions/runs/44682932298)只有 [20/56 个手势符合预期](selection-rectangle-redraw.md)，不在上述 81 项里；正在验证的修复 `78b18ac0` 不在这个下载文件中。
