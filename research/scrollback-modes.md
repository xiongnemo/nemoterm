# 应用有新输出时，能否留在正在阅读的历史行？

终端原来只认本地 profile 上的两个滚动开关。即使应用明确请求“新输出时留在历史里，真正键入时回到提示符”，`b3274ed` 仍按旧设置处理。新实现把 `CSI ? 1010 h/l` 接到“输出时回到底部”，把 `CSI ? 1011 h/l` 接到“键入时回到底部”。两项独立，可用 `CSI ? Ps $ p` 查询，用 `CSI ? Ps s/r` 保存和恢复。它们只改变这个终端的运行状态，不写入 profile，也不改变别的标签。

[固定的 XTerm 412](../testdata/upstream/xterm412-scrollback-modes.zip)在四种启动设置中给出了 72 段应答。首次保存之前恢复，两个模式都是关闭；备用屏切换、软重置和硬重置保留运行中的设置。这些行为取自原始回复。Nemoterm 打开窗口时仍读取用户选的两项初值；本地重新配置时，改变哪一项，就更新哪一项，应用对另一项的覆盖保留。

在 [GitHub Windows 对旧 EXE 的回放](https://github.com/xiongnemo/nemoterm/actions/runs/44552352165)中，GDI 和 DirectX 各有 72/72 段回复与 XTerm 不同；32 项实际滚动中，各有 16 项不符合应用要求。测试在历史顶部让子程序输出一个可见字符，或让 Windows 输入一个数字，直接读取原生滚动条位置。旧版只在 profile 恰好与应用要求相同时表现一致。[两份未修改的原始制品](scrollback-modes-before-b3274ed.zip)。

首个实现 `d0f1b12b` 在两种渲染器均通过 72 段应答及 32 项窗口行为，但是已有的固定存储检查发现模式表从 112 字节涨到了 120 字节。`a29abfa6` 改用 30 个有符号 16 位槽，共 60 字节，足以保存鼠标模式 -1 以及最大编码 1016；原有空间上限和精确新大小均检查。[首版窗口回执、失败日志及修正后完整 sanitizer 日志](scrollback-modes-storage.zip)。这些字节是每个终端的模式表，并非进程工作集测量。

修正版 `a29abfa6` 在[同一份 EXE 的 GitHub Windows 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44553596113)中，GDI、DirectX 各通过 **72/72 段应答、32/32 项窗口滚动**。应用已接管鼠标时，两种渲染器也都成功在 Shift 拖选期间接收新输出：历史位置保持在第 0 行，复制得到 `HISTORY 03 中`；真正键入 `7` 后才回到底部第 49 行。子进程只收到状态回复和一个 `7`。这两组共十个终端进程组均自行退出。[两份原始制品和 EXE 摘要](scrollback-modes-after-a29abfa.zip)。
