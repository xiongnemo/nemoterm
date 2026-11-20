# 关闭确认框：界面语言与取消后的输入

中文界面原来会显示标题“Nemoterm 退出确认”，正文却是英文 `Are you sure you want to close this session?`。修正只把会话确认文案接入程序内置的英汉词表，继续单独显示后端附加的警告。关闭整个标签窗口时仍提示会关闭其中的所有标签；系统按钮使用 Windows 的语言。

GitHub 托管 Windows 上用英文、简体中文分别启动四种场景：关闭当前标签、关闭后台标签、关闭整个标签窗口和关闭独立窗口。用实际中键请求关闭第二个（未选中）标签；其余场景向对应窗口发送关闭请求。从已显示的原生对话框读取标题和正文。点“取消”、按 Esc 后直接输入下一个字母，不重新聚焦；检查原标签收到 `ab`、`abc`，模态期间的 `X` 没有漏给终端，子程序这时输出的新行仍在。后台标签确认关闭时，还检查第一个标签仍能接收 `d`。

[原版 `c55cca64` 的完整回放](https://github.com/xiongnemo/nemoterm/actions/runs/44820371254/artifacts/14671452941)：**5/8**。三处中文会话确认的正文仍是英文；两种语言的整窗确认和四种场景的取消、确认及输入行为正确。[首次回放](https://github.com/xiongnemo/nemoterm/actions/runs/44820052253/artifacts/14671865988)因 runner 的日志编码无法打印中文失败消息，只留下四项英文回执。后一次回放先写 JSON，再输出兼容该代码页的日志，使用相同的原版 EXE。

[修正版 `fe5f98f9` 的窗口回执](https://github.com/xiongnemo/nemoterm/actions/runs/44820130857/artifacts/14671553748)：**8/8**。中文会话提示为“确定要关闭此会话吗？”，整窗提示为“关闭此窗口及其中的所有终端标签页？”。16 次取消后都没有再点终端，原子进程收到的字节依次是 `61 62`、`61 62 63`；确认关闭后台标签后，原标签还收到 `64`。同一作业的 Profile 保存、模态窗口、响铃布局和字号快捷键步骤也通过。[三次测试的原始对话框记录、身份及散列](close-dialog-language.zip)可离线复核。

[单文件开发构建](https://github.com/xiongnemo/nemoterm/actions/runs/44820130857/artifacts/14672630186)内的 `nemoterm.exe` 为 4,943,360 字节，SHA-256 `16611c7653efc06b42c42a492d12b14b077d4c934e6bc4e55e4531eedb7411d5`。对话框验收不代替[本版完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44820130857)及本版内存采样。
