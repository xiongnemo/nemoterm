# 新标签打开在哪个目录：OSC 7 的本地文件 URI

应用可以用 OSC 7 告诉终端当前工作目录。若已开启目录继承，实按 `Ctrl+Shift+T` 后，新标签应在这个目录启动。[RFC 8089 §2、附录 B](https://www.rfc-editor.org/rfc/rfc8089.html#section-2) 允许 `file:/absolute/path` 和 `file:///absolute/path` 两种写法；[RFC 3986 §3.1](https://www.rfc-editor.org/rfc/rfc3986.html#section-3.1) 规定 URI 的方案名不区分大小写。Windows 上的例子是 `file:/C:/work`、`file:///C:/work` 以及 `FILE:/C:/work`。

旧版 `b04ca12a` 只接受小写的 `file://` 开头。若应用之前报告的是另一个目录，复制目录 URI 和新标签的起点都会悄悄停在旧位置。候选 `c55cca64` 只改变方案和可选主机的解析；本机主机名检查、路径解码、长度限制及对无效输入的处理保持原样。不为每个标签增加常驻数据。

测试在 GitHub 托管 Windows 上运行，字体为 SarasaTermSC Nerd Light。每项先将原窗口的目录元数据置为 `previous`（不同于配置的 `start`），再让真实子进程发 OSC 7；目的目录名含空格、中文、分号、`#` 和 `%`。控制序列后跟一个状态查询，子进程读到回复后才复制目录 URI，并实按新标签快捷键。回执分别保留 Windows 剪贴板的 URI、同一前端中新子进程的 `getcwd()`、进程标识以及实际渲染器。

[旧单文件的 Windows 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44814111787/artifacts/14668213913)：GDI 和 DirectX 各 4/7；单斜线、混合大小写及大写单斜线均打开 `previous`。标准 URI 打开目标目录，远端主机保留在复制的 URI 中但新标签打开配置的 `start`；相对 URI 与含编码 NUL 的 URI 均保留 `previous`。没有把这些负对照改成有效路径。

[候选单文件的同一套 Windows 回放](https://github.com/xiongnemo/nemoterm/actions/runs/44814333692/artifacts/14669675584)：GDI **7/7**、DirectX **7/7**。三个原失败的写法均进入目标目录，复制的 URI 也正确。两个原窗口均自然退出，没有兜底终止。该作业还通过了四边标签切换、悬停预览和鼠标手势测试。[解析器地址和未定义行为检查](https://github.com/xiongnemo/nemoterm/actions/runs/44814333692/artifacts/14669420883)通过；[归档的原始窗口回执及解析器日志](osc7-tab-directory.zip)含 GitHub 制品编号、压缩包散列和受测 EXE 散列。

[试用版 `c55cca64` 的下载制品](https://github.com/xiongnemo/nemoterm/actions/runs/44814333692/artifacts/14669630337)中，`nemoterm.exe` 为 4,943,360 字节，SHA-256 `039723403523cc6c5d5de964b6d84f251f1bfc2b727b4a37f19ee3fbce584b7b`。本项 14 次实际新开标签不代替[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44814333692)或该 EXE 的满屏内存采样。
