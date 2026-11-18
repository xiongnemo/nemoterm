# 单文件预览 83ee8a5

Windows x64 [源构建制品](https://github.com/xiongnemo/nemoterm/actions/runs/44383008947/artifacts/14464623447)，4,850,176 字节，SHA-256 `3822bf211f3030f6da0af78ff7349a6e1af2cd1635537811a36fe02dbfade594`。提交 `83ee8a50ba43ba02b1747f5211c399cb0f77a79f`。下面的每项均核对了这份 EXE；先前预览的成绩见[上一版记录](interaction-f564927.md)。

- [跨普通行与双倍字宽行框选](selection-scaled-rows.md)：GDI、DirectX 各四种拖选均通过。复制中间行从 `defg` 纠正为屏幕选区中的 `bcd`，两侧字符的高亮与剪贴板一致。其余现有选区检查也通过。
- [真实客户端复制、取消、粘贴](agents-grid-83ee8a5.zip)：在实际 GDI 和 DirectX 上分别启动 Codex、Claude Code、OpenCode，160×48、SarasaTermSC Nerd Light。六个窗口均用系统按键和鼠标完成；右键独立场景不属于这组六项。
- [后台继续输出时的关闭确认框](profile-close-83ee8a5.zip)：点“取消”或按 Esc 后，原标签、整窗和无标签窗口均接收到了下一次输入，也都保留了确认框打开期间写入的标记。
- [文件与目录拖放](wsl-file-drop-83ee8a5.zip)：独立回放 `44383863104` 的两个渲染配置均通过。cmd 和 WSL Bash 实际打开了同一对包含空格和中文的测试路径，并读回了文件及目录内各自的标记。pwsh、Windows PowerShell、BusyBox ash 和 Git Bash 均验证了传给 shell 的实际参数。两个窗口的所有终端子树自然退出；只在清点专用 Ubuntu 中仅余 init、SessionLeader 和 ps 后才停止该发行版。外层 Job 均无剩余进程。此前[两个外层 Job 超时的原始结果](wsl-file-drop-f564927.zip)保留。

真实客户端选择和粘贴过程中，按约 100 毫秒定时取样，并合并各个操作时点的读数。下表是这一轮每个前端进程测得的最高私有工作集，不含后台客户端或控制台宿主。它和长历史、密集 Unicode 及图片的压力测试是不同负载。

| 客户端 | GDI | DirectX |
| --- | ---: | ---: |
| Codex | 16,285,696 B | 17,432,576 B |
| Claude Code | 6,901,760 B | 19,914,752 B |
| OpenCode | 6,901,760 B | 17,289,216 B |
