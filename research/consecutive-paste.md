# 连续粘贴的输入边界

第一段包含从 `A0000` 到 `A4095` 的 4096 行，末尾还有 `FIRST-END:中`；第二段为 `SECOND:尾🙂:END`。Windows 原生程序通过 `ReadConsoleW` 保存收到的 UTF-16LE。期望值独立生成，包含规范化后的回车；开启 bracketed paste 时，两段各自应有一对 `CSI 200~` / `CSI 201~`。看到第二段完整结尾后才发送独立的退出串。比较覆盖整个字节流，包括退出串；中文和代理项均不做额外规范化。

旧版 [`7ec651d` 的远程重放](https://github.com/xiongnemo/nemoterm/actions/runs/44464659813) 使用了与当时 `dist/nemoterm.exe` 相同的镜像（SHA-256 `c149c2bc3a3a2e0d2594ae2a239520af15a47bbb5c4d49c4daae3dc998bf64ba`）。控制器连续提交两段，等待每次请求被终端接收的回执，但不等待第一段发完。四个子进程都正常退出。[原始制品，含完整期望及实收字节](paste-order-before-7ec651d.zip)。

| 旧版输入场景 | 第一段实收行数 / 4096 | 开始 / 结束标记 | 总计实收 / 期望字节 |
|---|---:|---:|---:|
| GDI，普通 | 8 | 0 / 0 | 150 / 49,228 |
| GDI，括号 | 20 | 2 / 1 | 330 / 49,276 |
| DirectX，普通 | 8 | 0 / 0 | 150 / 49,228 |
| DirectX，括号 | 8 | 2 / 1 | 186 / 49,276 |

两次长短粘贴重叠时，原来的终端核心会丢弃已开始的长文本。`2ca68df` 改为按会话保存已接收的粘贴，完成上一段再开始下一段；普通按键仍可中止未发部分。核心回归覆盖发送第一行前后、未开始的排队项、打断后再粘贴，以及等待队列超过容量。这个修复不解释 Codex 客户端首次输入期间的[另一项乱序记录](codex-file-draft-order.md)。

修复后的产品 EXE 是 `2ca68dff4d3285054693abf3c6f3e4d4c4dc70e1`，SHA-256 为 `f2cb4fbae5a52ba3be8e4abb979a363e2b279591269b43838ee1da40957f7ca0`。两台 GitHub 托管 Windows runner 独立下载并核对这份 EXE：

- [完整 CI 中的接口重放](https://github.com/xiongnemo/nemoterm/actions/runs/44464971332)：[四组原始记录](paste-order-after-2ca68df.zip)都与期望逐字节相同。
- [含系统键盘的独立重放](https://github.com/xiongnemo/nemoterm/actions/runs/44465584248)：[四组接口和四组真实剪贴板记录](paste-order-clipboard-2ca68df.zip)全部通过。第二次 `Ctrl+Shift+V` 前，接收器只收到 8,544–9,012 字节，第一段尚未收完。普通模式最终分别收到全部 49,228 字节；括号模式收到全部 49,276 字节，含两对独立标记。

这两轮比较只验证同一终端会话内的连续文本粘贴。完整 CI 的其他任务各自计分；位图粘贴与 ReGIS 画面不在此结论内。
