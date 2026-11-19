# 拖放文件时使用当前会话的 shell 和 WSL 发行版

测试版 `9b5e1111` 有两个独立问题。资源管理器中 `\\wsl.localhost\Ubuntu-24.04\tmp\…` 拖入同一个 Ubuntu 时，Bash 收到的路径仍以 `//wsl.localhost/Ubuntu-24.04/` 开头。另外，把 profile 的默认 shell 从 Windows PowerShell 改为 cmd 并保存后，旧 PowerShell 会话也开始使用 cmd 引号。实测文件名里的 `$nemoDropPath` 被 PowerShell 当作变量展开，`Get-Content` 找不到已存在的文件；同一 profile 新开的 cmd 反而可以正常读取。[旧版回放和实际错误输出](drop-shell-reference-9b5e1111.zip)。

候选 `cf091974` 在启动会话时记录用了哪个 shell。收到资源管理器的文件列表时，识别同一发行版的共享路径并传入 Linux 绝对路径；混入其他发行版就整批拒绝。普通网络共享仍按原有规则处理。[同一组输入的修复后回放](https://github.com/xiongnemo/nemoterm/actions/runs/44589237971)使用一个 EXE、两种实际渲染器和 SarasaTermSC Nerd Light。两端的测试脚本相同；以下结果累计 GDI、DirectX 两次运行。

| GitHub 托管 Windows 的实际操作 | 旧版 | `cf091974` |
| --- | ---: | ---: |
| Windows 拖放或粘贴当前发行版的文件及目录，经三个共享路径写法交给 Bash 读取两个对象的随机内容 | 0/6 | 6/6 |
| 发行版根目录，混入其他发行版，和貌似 WSL 的普通服务器 | 2/6 | 6/6 |
| 改设置前，在 Windows PowerShell 读取拖入的文件 | 2/2 | 2/2 |
| 保存 cmd 为默认后，在同一个 PowerShell 读取另一个拖入的文件 | 0/2 | 2/2 |
| 用此 profile 重新启动，在真实 cmd 中用 `type` 读文件 | 2/2 | 2/2 |

[新版本的原始制品和 REA 导入表](drop-shell-after-cf091974.zip)保留了窗口文本、Linux 端原始输入和随机文件内容，以及作业退出记录。Win32 测试发送 `WM_DROPFILES` 或提供资源管理器的 `CF_HDROP` 剪贴板格式，没有模拟用户在 Explorer 中按住鼠标拖动的全过程。对照使用 `Ubuntu-24.04`、托管 WSL1、显式或默认发行版；没有测试自定义挂载点和 WSL2。EXE SHA-256：`9df8365b9e32444f24d279c114750090122f8550c1aa53dffa2972c448aa4788`。

两轮早期失败另外保留：[第一轮旧版 WSL](wsl-share-drop-before-9b5e1111.zip)还观测到 WSL 宿主进程在产品作业中未自然退出；让测试自己启动并持有 Ubuntu 后，旧版的路径错误仍复现，产品作业已自然退出。[旧版的首轮 PowerShell 测试](drop-profile-before-9b5e1111.zip)和[候选的首轮完整 CI 制品](drop-profile-initial-cf091974.zip)都没等到回显条件，未执行到保存。后续用每次唯一的文件后缀识别可能折行的回显，并保存最后一屏。成败仍取决于命令能否读到文件里的完整随机标记；两份早期记录不补算成功。
