# a9c8150 的交互验证

远程构建的四舍五入大小约 4.86 MB（4,860,928 字节）；SHA-256 `a1b2e279d105575649ffc73a913129085d931200d53a2036409891cd8a5764a4`。[源构建](https://github.com/xiongnemo/nemoterm/actions/runs/44338343977)的制品 ID 为 `14443251390`。以下结论仅针对这一份可执行文件。

[WSL 原始回放](wsl-less-verified-a9c8150.zip)来自 [44339705048](https://github.com/xiongnemo/nemoterm/actions/runs/44339705048)，制品 ID `14441894634`，ZIP SHA-256 `02517c08f057abdc43527a24b147aabb99a815b2bbb40e87d46725ad393225bf`。Ubuntu 24.04 `less` 590、SarasaTermSC Nerd Light。`TERM=xterm` 和继承的 `xterm-256color`，分别使用调试接口按键与 runner 系统键盘、分别直接运行与在 `script(1)` 中运行，共 **8/8**。每次都从第 1 行开始，向下后首行为 2，翻页后为 34，搜索后为 220；按 `q` 恢复了打开前的可见文本，子程序自然退出，WSL 清理记录确认 shell 已退出。已核对八组共 48 张截图的哈希。

四份原始 PTY 输入日志均为 `1b 4f 42`（下）、`1b 5b 36 7e`（下一页）、`/ZEBRA_NEEDLE`、回车、`q`，前两项和 WSL 的 `tput kcud1`、`tput knp` 一致。修复前 API 错发 `1b 4f 72` 的[同组对照](wsl-less-diagnostic-1fef0e3.zip)仍保留。这验证了上述交互，不等于全部键盘协议或全部 terminfo 行为都已验证。
