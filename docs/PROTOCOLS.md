# NemoTerm 协议范围与缺口清单

核对日期：2026-11-12。这是初始覆盖账本，目标仍是用户要求的现代终端完整能力；不是“基本 ANSI 已经够用”的验收结论。支持状态针对本工作区，而非原版 PuTTY 的宣传描述。后续实现必须更新相应行，并补充精确测试和端到端证据。

## 状态及证据口径

- **已证（有限范围）**：有实际通过的测试，范围只到该测试覆盖的参数和行为。
- **源码已见**：已定位处理分支，但没有相应完整语义或真实应用验证。
- **缺失**：本次检查的终端解析、状态、回复和输入路径中没有实现，或显式忽略；“能吞掉未知序列”不算支持。
- **待核实**：证据不足，不算完成。
- **集成中**：有独立开发任务，合入和验收之前不算支持。

本次核心验证命令为 `tools/python/cmake/data/bin/cmake.exe --build build --target test_terminal --parallel 8` 和 `build/test_terminal.exe`，在Sixel集成前运行结果为 `Test suite passed`；集成后须重新运行。测试在 `vendor/putty-0.85/test/test_terminal.c`。它验证内存中的字符格和输出字节，**不代替** GDI 像素、字体、Win32 快捷键、系统剪贴板和 ConPTY 链路测试。

下表源码简称：**T**=`vendor/putty-0.85/terminal/terminal.c`，**H**=`terminal/terminal.h`，**W**=`windows/window.c`（后两者同一 vendor 根目录）。使用函数/分支名称定位，避免后续 Sixel 合入导致行号失效。序列中的 `CSI=ESC [`、`OSC=ESC ]`、`DCS=ESC P`、`APC=ESC _`，`ST=ESC \`；OSC 的 BEL 终止另测，不能把所有字符串协议一律当成 OSC。

## 核心字符、状态、绘制

| 家族 / 具体范围 | 状态 | 工作区证据与尚需证明的内容 |
| --- | --- | --- |
| C0：BEL、BS、HT、LF/VT/FF、CR、SO/SI、CAN/SUB、ESC；C1 及 7/8-bit 控制形式 | 源码已见，完整一致性待核实 | T `term_out`、UTF-8 解码与控制字符分支。应逐项测中断、取消、错误恢复、截断、UTF-8/C1 歧义及每个字节切分；不能仅测正常字符串。 |
| ESC：`D/E/M/H`、`7/8`、`=`、`>`、`c`、`#3/#4/#5/#6/#8`、字符集 G0/G1 等 | 源码已见 | T ESC 分派含索引、制表、保存恢复、键盘模式、RIS、行属性/字符集；仍需各参数、组合状态和 reset 测试。 |
| CSI 光标和编辑：`A/B/C/D/E/F/G/H/f/d/a/e`、`@/P/L/M/X/J/K`、`S/T`、`I/Z/g`、`b` | 源码已见，局部已证 | T `SEEN_CSI`；已有 `test_wrap/test_nonwrap` 覆盖换行、退格与宽字符边界。移动/插删/擦除/重复/制表仍需系统测试，尤其空参数、0、超大参数和滚动边界。 |
| 标准模式 4/12/20；DEC 模式 1/2/3/5/6/7/8/25 | 源码已见 | T `toggle_mode`。需验证插入、回显、换行、应用光标、VT52、80/132列、反色、origin、wrap、重复键及光标状态之间的交互。 |
| 滚动区域 `CSI top;bottom r`、备用屏 `?47/1047/1048/1049 h/l` | 1049局部已证；其余源码已见 | `test_colour_and_alternate_screen` 证明1049恢复主屏文字、颜色和光标；`test_shift_selection` 在备用屏复制当前内容。滚动历史、resize、嵌套及47/1047差异未认证。 |
| 左右边距 `?69 h/l`、`CSI left;right s`；选择性擦除/受保护属性；矩形操作（如 `$r/$t/$v/$x/$z/${`） | 缺失或待逐项核实 | 当前 `CSI s/u` 是保存/恢复光标，不能当成 DECSLRM。需从 xterm/DEC 清单拆分每条并确定模式冲突；没有以整体“兼容”覆盖它们。 |
| SGR基础、16/256色、`;` 形式 RGB：`38;5;n`、`48;5;n`、`38;2;r;g;b`、`48;2;r;g;b` | 颜色局部已证；样式部分源码已见 | `test_colour_and_alternate_screen` 覆盖FG/BG真彩色、索引色和0重置；T SGR有bold/dim/underline/blink/reverse/strike。渲染效果和每种重置仍需验证。 |
| SGR冒号子参数：`38:2::r:g:b`、`48:2::r:g:b`、`4:0..5`；下划线色58/59；italic 3/23、conceal 8/28 | 缺失 | 当前 `SEEN_CSI` 没有子参数数组；SGR21与4共用一个underline位，不证明双下划线。需补解析、存储、压缩、渲染、复制样式及reset。 |
| 光标形状 `CSI Ps SP q`（DECSCUSR）和软复位 `CSI ! p` | 缺失/待逐项核实 | 未见对应现代分派；现有PuTTY设置和SCO私有光标指令不是这些序列。 |
| Unicode：UTF-8、宽字符、组合字符；emoji/ZWJ/variation selectors/区域旗帜、bidi、grapheme | 前三项局部已证；其余待核实 | 测试包含跨读取边界中文和组合音标、选择复制。完整grapheme宽度、重排后的物理选择、字体fallback、Nerd Font、IME需专项测试。 |

## 输入、鼠标、协商与同步

| 家族 / 具体范围 | 状态 | 工作区证据与缺口 |
| --- | --- | --- |
| 普通/应用光标键、数字键盘、F键、Alt/Ctrl/Shift修饰 | 源码已见 | T `format_arrow_key` 等与W键盘路径；真实Windows键盘布局、AltGr、IME和ConPTY传输尚需验证。 |
| xterm `modifyOtherKeys`：`CSI > 4;Ps m`，扩展键格式 | 缺失 | 未见协商状态及对应出站编码；不得以普通Ctrl组合代替。 |
| CSI-u / kitty keyboard：查询 `CSI ? u`，设置 `CSI = flags;mode u`，push `CSI > flags u`，pop `CSI < n u` | 缺失 | T现有 `CSI u` 只是光标恢复。须有主/备用屏独立模式栈及flags 1/2/4/8/16，处理按下/重复/释放、备用键码、修饰键和关联文本。以 [kitty键盘规范](https://sw.kovidgoyal.net/kitty/keyboard-protocol/) 为准。 |
| Win32 input mode `CSI ? 9001 h/l` | 缺失 | W已有Windows消息处理，不等于实现该协议的协商和出站记录格式。需要与ConPTY和现代Windows TUI共同验收。 |
| 鼠标1000/1002/1003；1006 SGR字符格；传统编码 | 已证（有限范围） | `test_shift_selection` 的12组模式×1006开关×备用屏矩阵：点击/拖动/释放精确回复；1003悬停回复；Shift强制本地选择并复制当前中文/组合字符，释放Shift后完成手势不泄漏事件。未测所有修饰键、滚轮、大坐标与窗口外拖动。 |
| 鼠标1015 urxvt | 源码已见 | T `toggle_mode/term_mouse`；仍需精确字节和边界测试。 |
| 鼠标9/1001/1005、1016 SGR像素、1007备用屏滚轮 | 缺失/待细分 | `1006`是字符格，**不是像素**；`1016`须从Win32保留像素坐标并处理DPI。不能拿1006测试证明1016。历史高亮/UTF-8模式也仍在清单中。 |
| 焦点1004：`CSI I` / `CSI O` | 缺失 | `term_set_focus` 目前维护焦点/光标，不发送应用焦点通知；需模式开关、真实焦点事件及无重复通知测试。 |
| bracketed paste 2004：`CSI 200~` / `CSI 201~` | 已证（有限范围） | `test_bracketed_paste` 验证UTF-8内容、开关和空粘贴；仍须测大段、多行、取消、内嵌结束符、系统剪贴板及真实ConPTY。 |
| synchronized output 2026：`CSI ? 2026 h/l` 与 `CSI ? 2026 $ p` 查询 | 缺失 | 合并普通重绘/50Hz冷却不等于同步输出。必须继续解析但暂缓呈现，复位/超时/退出后释放，且不冻结本地输入；需像素级“无中间帧”验证。 |
| DA/DA2、DSR/CPR：`CSI c`、`CSI > c`、`CSI 5n/6n` | 源码已见 | T已有回复，DA2沿用`>0;136;0c`。需核对实际能力再宣告，验证origin/边距和回包顺序；不能虚报Sixel或未实现功能。 |
| DECRQM/DECRPM：`CSI [ ? ] Ps $ p` → `... $ y`；DA3/XTVERSION等进一步查询 | 缺失/待细分 | 需逐项拆分普通/私有模式及0未知、1置位、2复位、3/4永久状态。单独回复2026不能冒称所有模式已支持。 |
| 窗口操作 `CSI Ps ... t`、像素/字符尺寸、标题栈22/23 | 部分源码已见 | T含窗口大小、位置、最小化等部分操作；每个子参数、权限设置、DPI和查询准确性都待核实，尤其标题栈。 |

## OSC、DCS、图像与shell语义

| 家族 / 具体范围 | 状态 | 工作区证据与缺口 |
| --- | --- | --- |
| OSC0/1/2、DECterm21标题 | 0/2局部已证；其余源码已见 | `test_wintitle`验证BEL/ST、逐字节UTF-8标题和DCS不能误当标题。长标题、取消、截断、query配置需补测。 |
| OSC4调色板查询/设置、多组；104重置 | 查询源码已见；设置/104缺失 | `do_osc`只有4的`?`查询；Linux `OSC P/R` 调色板分支不能证明标准OSC4设置/104已实现。 |
| OSC10/11/12及110/111/112：默认前景/背景/光标色，设置/查询/恢复 | 缺失 | 须测RGB格式和查询回复，不只实现颜色设置；常被应用用于识别背景主题。 |
| OSC8：`8;params;URI`，空URI关闭、`id=` | 缺失 | 需要字符格/历史中链接关联、覆盖与回收、鼠标命中、复制文本和显式打开动作。参照 [iTerm2扩展文档](https://iterm2.com/documentation-escape-codes.html)。 |
| OSC52：`52;Pc;Pd`，Base64设置、`?`查询 | 缺失 | 本地Ctrl+Shift+C/V已存在不等于OSC52。应明确可配置读/写策略、选择目标、上限与拒绝行为，并测试不会返回未授权的剪贴板内容。 |
| OSC7：`7;file://host/path` | 缺失 | 当前工作目录元数据及URI转义/主机处理；不要把终端自身cwd误当shell当前目录。 |
| OSC133：A/B/C/D（D可带退出码）；OSC633扩展 | 缺失 | prompt、command、output和结束标记需要状态/滚动历史绑定；单纯吞掉序列不实现命令选择、导航等语义。依据 [Windows Terminal shell集成](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration)。 |
| OSC1337非图像：CurrentDir、RemoteHost、SetMark、用户变量等 | 缺失，需按子命令拆分 | 1337是命名空间，不能只支持一个子命令就整体标绿。对照iTerm2文档逐项登记；扩展需要设置项的保留设置项。 |
| OSC1337图像：`File=...:base64`，MultipartFile/FilePart/FileEnd | 缺失 | 图像尺寸、分块、编码、滚动、擦除、备用屏、动画/静态差异和资源预算均需独立验证。参照 [iTerm2图像协议](https://iterm2.com/documentation-images.html)。 |
| DCS DECRQSS：`DCS $ q Pt ST`，如`m`、`r`、`SP q` | 缺失 | 需要根据当前状态返回有效/无效回复；不能把收到请求视为支持。 |
| DCS XTGETTCAP：`DCS + q hex-names ST`，如`Co/TN/RGB`及键能力 | 缺失 | 十六进制解码、多个能力、成功/失败回复、实际TERM/颜色/键绑定一致性。没有系统terminfo数据库也必须诚实回应。 |
| Sixel：`DCS P1;P2;P3 q ... ST`、repeat/color/raster指令；DECSDM80等 | 集成中，未认证 | 独立任务正在集成；本次文档不提前把它标为完成。需decode测试、实屏像素、滚动/擦除/resize/备用屏生命周期、查询/能力宣告、非法/巨大输入和20MB预算。 |
| kitty graphics：`APC G control;payload ST` | 缺失 | 按 [kitty图像协议](https://sw.kovidgoyal.net/kitty/graphics-protocol/) 细分传输/查询/placement/删除、分块、RGB/RGBA/PNG、缓存与回收；共享内存/文件路径/动画/Unicode占位等扩展单列，不以Sixel代替。 |
| 其他DCS/APC/PM/SOS、ReGIS、Tektronix、UDK/DRCS等历史家族 | 待逐项清点，未完成 | 当前原版`do_osc`默认忽略这些字符串；Sixel分支合入不会自动实现其余家族。保留xterm总清单作为完整性审计入口。 |

基础字符串缓冲原为 `OSC_STR_MAX=2048`。扩展不能粗暴地把所有OSC/DCS/APC都改成无限缓存；应分别确定流式处理、终止/取消语义、数量和内存上限，并验证被拒绝或截断后解析器能继续正确处理后续文本。设置上限不意味着可以无声地把功能缺失当作支持。

## 参考基线及追踪方法

本次读取的是以下官方资料/项目源码，**不是**在本机逐个运行这些终端得到的结论；开发分支也不等于某个已发布版本。它们的差异不能用来缩小用户目标。

- **xterm**：[作者官方镜像ctlseqs.txt，commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt)，文件注明Patch #411。用于C0/C1/ESC/CSI/OSC/DCS和历史扩展的总索引、DECRQSS/XTGETTCAP及1016定义。后续每个家族展开成参数级记录，不能仅凭本表行数宣称全覆盖。
- **Alacritty**：真实路径是 [extra/man/alacritty-escapes.7.scd，commit `aa5d942f46c40184a3f214830ff5f7989f4733a1`](https://github.com/alacritty/alacritty/blob/aa5d942f46c40184a3f214830ff5f7989f4733a1/extra/man/alacritty-escapes.7.scd)。该表列出OSC8/52、CSI-u协商族、2026、SGR58/59等；它也明确区分partial/rejected。其“Implemented”有时意味着其余子功能被拒绝，不能照搬为NemoTerm的完整支持承诺。旧猜测路径`docs/escape_support.md`无效。
- **Windows Terminal**：[OutputStateMachineEngine.cpp，commit `5f7dc283013152f89bfb76950515c33f45157ad7`](https://github.com/microsoft/terminal/blob/5f7dc283013152f89bfb76950515c33f45157ad7/src/terminal/parser/OutputStateMachineEngine.cpp) 与 [DispatchTypes.hpp](https://github.com/microsoft/terminal/blob/5f7dc283013152f89bfb76950515c33f45157ad7/src/terminal/adapter/DispatchTypes.hpp)。当前源码有Sixel、DECRQSS、OSC超链接/cwd/clipboard等分派以及1004/1006/2026/9001常量。存在分派不是完整运行证明；例如OSC52路径明确不处理clipboard查询，不能把“参考Windows Terminal”理解为任何扩展全功能。
- [Microsoft Console VT文档](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences)用于Win32/ConPTY交互语义；它不是Windows Terminal所有新增扩展的全集。还需对宿主可能翻译、吞掉或重编码的序列做端到端验证。

## 下一轮实现和验收顺序

1. **直接影响现代agent的缺口**：2026与模式查询、OSC10/11/12查询、OSC8、1004、冒号SGR及常见样式、kitty键盘协商；继续完成Sixel像素和资源生命周期。同步增加断片输入/错误恢复/准确回复测试，不宣告尚未实现的能力。
2. **交互和协商完整性**：DECRQSS/XTGETTCAP、OSC52设置与查询策略、1016像素鼠标、Windows输入模式、resize/DPI和大坐标、更多光标/边距/擦除行为；在真实Claude Code/Codex和shell里记录可复现输入及输出。
3. **剩余现代及历史范围**：OSC7/133/633/1337语义，kitty/iTerm图像扩展，完整xterm家族逐项拆解及测试。优先级表示先后次序，不是把后项从目标删除。

每一项完成至少需要：序列与参数定义 → 对应源码和状态生命周期 → 分块输入与回复测试 → 有界资源测试 → 必要的真实窗口/应用验证。图片、链接、历史和新样式加入后，应重跑代表性agent负载的私有工作集、总工作集和长时间峰值；本账本不证明内存门槛已经成立。
