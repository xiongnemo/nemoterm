# pterm 0.85：轻量化证据与 NemoTerm 设计依据

调查日期：2026-11-12（Australia/Sydney）。仅查询已运行进程，不输入命令、不读取终端画面、不修改 PuTTY 配置、不清空工作集、不终止用户进程。

## 已回答的问题

| 问题 | 当前结论 | 证据种类 |
| --- | --- | --- |
| 指定程序是谁 | 官方 PuTTY 0.85 Windows pterm，amd64 原生 PE；不是 Unix GTK pterm，也不是同名 Go 包 | 本机 SHA-256、版本资源、Scoop manifest、官方校验表、REA |
| 8 MB 是否真实 | 既有 5 个窗口的私有工作集约 7.13–7.85 MiB；总工作集约 29.38–34.49 MiB | 当前 Windows 性能计数器 |
| 为什么能轻量 | 小型 C/Win32 程序、GDI 字符绘制、压缩并限制回滚行、复用行对象、按变化合并重绘、ConPTY 与子进程分开计费 | 发布源码与导入表；具体节省多少是推论 |
| 是否可以合法复用 | MIT 许可允许修改、分发、商业使用，需保留版权与许可 | 官方许可与发布包 LICENCE |
| 是否天然满足全部现代协议 | 否。已有 xterm 鼠标和 bracketed paste；Sixel、OSC 8、同步更新等仍需专项实现和测试 | 源码检查，非完整协议认证 |

## 制品身份

- 本机路径：`C:\Users\nemo\scoop\apps\pterm\0.85\pterm.exe`。
- 大小：1,060,008 bytes（约 1.01 MiB）。
- SHA-256：`8580a3df4afe7696758c1cef43d0e88e3db5fd41c35c60166241aee72dd3ba3b`。
- 版本资源：`Release 0.85 (with embedded help)`；产品 `PuTTY suite`；描述 `PuTTY-style wrapper for Windows command prompts`。
- `current\pterm.exe` 的散列与指定 0.85 文件相同。
- [官方 SHA-256 清单](https://the.earth.li/~sgtatham/putty/0.85/sha256sums) 中 `w64/pterm.exe` 与本机散列完全一致。
- [官方发布源码](https://the.earth.li/~sgtatham/putty/0.85/putty-0.85.tar.gz) SHA-256：`13fd4db2936d03b73812a7bcc2a658e4dd29cc776a56c3670a7fc6f1a0ee8af8`，与下载文件和官方清单一致。工作区源码见 `vendor/putty-0.85/`。

这建立发布版本关联；没有进行可复现编译来证明该源码每个字节与二进制对应，也没有做 Authenticode 信任链验证。

## REA 证据

`rea-pterm-evidence.json` 是 REA `inspect_pe_imports` 的完整 Evidence bundle。

Evidence ID：`ev_580d5500e9863e85ce7e2692fb641d356d62a8a35c47b714b88b2ad855b6422a`。

REA 完整解析了 8 个 DLL、319 个导入、0 个延迟导入：GDI32（51）、IMM32（5）、ole32（3）、USER32（116）、KERNEL32（126）、SHELL32（1）、COMDLG32（6）、ADVAPI32（11）。可见 `ExtTextOutW`、`CreateFontA`、`BeginPaint`、`CreateWindowExW`、`HeapAlloc`、`CreateProcessW`、`GetProcAddress` 等。

这个静态证据支持原生 Win32/GDI 架构；导入表不证明某函数实际执行，也不能排除动态加载。对既有真实 pterm PID 22668 的模块快照另见 `pterm-loaded-modules.json`：没有发现 Chromium/WebView2/Node/CLR 模块；存在系统输入法和 UI 引入的 `dwrite.dll`、`d3d11.dll` 等，不能据此宣称它绝不加载任何 GPU 相关组件。

REA session 报告 Ghidra 未配置，故没有伪装成已完成反编译或调用栈/分配栈分析。此次使用无需深层 provider 的 PE 解析，配合同版源码与只读运行证据，不需要安装额外反编译器。没有开启需要关闭的原生分析 session。

## 内存：三个数必须分开

原始采样见 `pterm-memory-snapshot.json`；进程身份和直接子进程见 `pterm-process-tree.json`。采样约 2026-11-12 01:40–01:42 +11:00；各接口顺序查询，非原子快照。

| 真实 pterm PID | 私有工作集 bytes | 总工作集 bytes | 私有提交 bytes |
| --- | ---: | ---: | ---: |
| 47016 | 7,471,104 | 31,756,288 | 9,502,720 |
| 25396 | 7,655,424 | 33,775,616 | 9,527,296 |
| 45236 | 8,228,864 | 31,772,672 | 10,113,024 |
| 46392 | 7,573,504 | 30,806,016 | 9,428,992 |
| 22668 | 7,737,344 | 36,163,584 | 9,740,288 |

用户看到约 8 MB 的现象与私有工作集一致；不需要假定是误读。另有 5 个同名 Scoop shim，路径是 `scoop\shims\pterm.exe`，它们仅是启动器，也有约 6.9–7.2 MiB 总工作集，不能误计为终端本体。

每个真实 pterm 都有独立 `conhost.exe` 和 `cmd.exe` 子进程。此表仅统计窗口前端，不包括 ConPTY 控制台宿主、shell 或 agent。若要求整个 agent 会话低于 20 MB，这张表不能证明它。

[Microsoft 的工作集定义](https://learn.microsoft.com/en-us/windows/win32/memory/working-set) 指当前驻留物理内存的页，其中可能包含可共享页；[PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex) 的 PrivateUsage 则是私有提交，不等于当前实际驻留内存。测试 NemoTerm 时应同时记录三项，不能通过 `EmptyWorkingSet` 或最小化窗口人为压低验收值。

可重复执行 `pwsh -File research/measure-pterm.ps1`，会产生带时间和路径的 `pterm-memory-latest.json`，不会覆盖初始快照。

## 源码中的节省机制

以下路径相对于官方 0.85 源码根目录。代码在此处是同版源代码观测，具体内存贡献未做分配剖析。

1. **紧凑的本机前端。** `windows/CMakeLists.txt:155–174` 的 pterm 目标由 C 源文件组成，链接终端、GUI、事件循环、设置、网络和工具库；不链接 PuTTY SSH 的 crypto/keygen 部分，并使用 no-gss/no-rand 等桩。没有浏览器布局引擎、DOM 或脚本 VM。
2. **保留字符单元而不是富文档对象树。** `terminal/terminal.h:26–58` 以 `termchar`、`termline` 保存字符、属性、真彩色和组合字符链；主屏、备用屏、回滚分别存储。组合字符只在需要时占用额外单元。
3. **回滚内容压缩。** `terminal/terminal.c:403–414` 明确采用 RLE；`:700–755` 分别对字符、属性、真彩色和组合字符流编码。`:2636–2655` 达到回滚行上限就释放旧行，并复用当前行作为底部新行。`:1211–1214` 在访问回滚时解压，避免所有历史行都常驻展开结构。
4. **按变化绘制与更新合并。** `terminal/terminal.c:40` 默认约 50 Hz 更新冷却；`:1323–1341` 合并待更新请求，`:6100` 起对比显示缓存并只绘制 dirty run。`windows/window.c:2784` 的 WM_PAINT 处理与 `:3823` 的 `ExtTextOutW` 路径说明其主要终端文字由 GDI 绘制。
5. **ConPTY 把会话任务分到独立进程。** `windows/conpty.c:29–47` 动态加载 Create/Close/ResizePseudoConsole，`:202` 起创建伪控制台与管道，后续创建子进程。终端窗口不承担 agent 的解析、模型客户端或 shell 本身的堆。

因此它的秘诀主要是架构和数据生命周期，而不是某个神秘的内存优化开关。压缩/有界历史、按需数据、直接 Win32 绘制和模块裁剪适合继承；单靠选 C 语言不足以保证相同结果。

## 对 NemoTerm 的含义与未完成验证

- 以此 MIT C/Win32/ConPTY 基础构建能复用成熟 xterm/Unicode/输入法/设置代码，保留 [PuTTY 许可](https://www.chiark.greenend.org.uk/~sgtatham/putty/licence.html)。改名和功能补齐应有独立配置命名空间，避免污染用户原 PuTTY 设置。
- “所有转义序列”需要协议清单和逐项测试，不是 `TERM=xterm-256color` 环境变量就能证明。原版 `terminal/terminal.c:3135` 支持 SGR 鼠标 1006，`:3165` 支持 bracketed paste 2004；此检查并未认证完整 xterm、Windows Terminal 或 Alacritty 行为。
- 在官方 `terminal/` 范围搜索 Sixel、OSC 8、kitty、同步更新等未找到对应实现；这是后续开发线索，不是严格的全程序不可达证明。
- Sixel 解码图像和大窗口会改变预算：例如一张 1024×1024 RGBA 位图就需要 4 MiB。应对图像总量、尺寸和回滚存储设明确有界策略，并测试滚动、覆盖与释放。
- 需要实际 Sarasa 字体、真实 agent、活动窗口、长输出、resize、回滚和图片组合负载；本报告仅证明 pterm 的基线，不证明新终端的 20 MB 验收。
- 未完成：分配栈剖析、特性逐项协议一致性测试、相同内容与窗口尺寸的跨终端受控比较。没有把这些未知项说成已验证。
