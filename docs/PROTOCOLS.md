# NemoTerm 协议范围与缺口清单

核对日期：2026-11-12。这是初始覆盖账本，目标仍是用户要求的现代终端完整能力；不是“基本 ANSI 已经够用”的验收结论。支持状态针对本工作区，而非原版 PuTTY 的宣传描述。后续实现必须更新相应行，并补充精确测试和端到端证据。

## 状态及证据口径

- **已证（有限范围）**：有实际通过的测试，范围只到该测试覆盖的参数和行为。
- **源码已见**：已定位处理分支，但没有相应完整语义或真实应用验证。
- **缺失**：本次检查的终端解析、状态、回复和输入路径中没有实现，或显式忽略；“能吞掉未知序列”不算支持。
- **待核实**：证据不足，不算完成。
- **集成中**：有独立开发任务，合入和验收之前不算支持。

当前脚本包含三十组核心测试；scripts/test.ps1 包含全部目标。单 EXE 脚本有三十五项基础及变体检查，提供 CodexExecutable 时另测默认与内嵌界面，共三十七项。常规 CI 保留 MinGW 对照和 Linux ASan/UBSan。核心测试不代替 GDI 像素、系统剪贴板和真实 ConPTY 验证；各项证据仅证明对应参数与场景，不能代表完整兼容认证。

下表源码简称：**T**=`vendor/putty-0.85/terminal/terminal.c`，**H**=`terminal/terminal.h`，**W**=`windows/window.c`（后两者同一 vendor 根目录）。使用函数/分支名称定位，避免后续 Sixel 合入导致行号失效。序列中的 `CSI=ESC [`、`OSC=ESC ]`、`DCS=ESC P`、`APC=ESC _`，`ST=ESC \`；OSC 的 BEL 终止另测，不能把所有字符串协议一律当成 OSC。

## 核心字符、状态、绘制

| 家族 / 具体范围 | 状态 | 工作区证据与尚需证明的内容 |
| --- | --- | --- |
| C0：BEL、BS、HT、LF/VT/FF、CR、SO/SI、CAN/SUB、ESC；C1 及 7/8-bit 控制形式 | 源码已见，完整一致性待核实 | T `term_out`、UTF-8 解码与控制字符分支。应逐项测中断、取消、错误恢复、截断、UTF-8/C1 歧义及每个字节切分；不能仅测正常字符串。 |
| ESC：`D/E/M/H`、`7/8`、`=`、`>`、`c`、`#3/#4/#5/#6/#8`、字符集 G0/G1 等 | 源码已见 | T ESC 分派含索引、制表、保存恢复、键盘模式、RIS、行属性/字符集；仍需各参数、组合状态和 reset 测试。 |
| CSI 光标和编辑：`A/B/C/D/E/F/G/H/f/d/a/e`、`@/P/L/M/X/J/K`、`S/T`、`I/Z/g`、`b` | 源码已见，局部已证 | T `SEEN_CSI`；已有 `test_wrap/test_nonwrap` 覆盖换行、退格与宽字符边界。移动/插删/擦除/重复/制表仍需系统测试，尤其空参数、0、超大参数和滚动边界。 |
| 标准模式 4/12/20；DEC 模式 1/2/3/5/6/7/8/25 | 源码已见 | T `toggle_mode`。需验证插入、回显、换行、应用光标、VT52、80/132列、反色、origin、wrap、重复键及光标状态之间的交互。 |
| 滚动区域 `CSI top;bottom r`、备用屏 `?47/1047/1048/1049 h/l` | 1049局部已证；其余源码已见 | `test_colour_and_alternate_screen` 证明1049恢复主屏文字、颜色和光标；`test_shift_selection` 在备用屏复制当前内容。滚动历史、resize、嵌套及47/1047差异未认证。 |
| 左右边距 `?69 h/l`、`CSI left;right s` | 已证（有限范围） | 支持查询/保存/复位、origin、移动/换行/制表、IL/DL/ICH/DCH、SU/SD及矩形坐标；69关闭时保留ANSI光标保存。Sixel按列分割视图并共用位图，维持4MiB总预算。114项独立XTerm对照、宽字符/组合链/历史/选择及ASan/UBSan已测；真实ConPTY像素、Shift复制、字体和网格缩放见[边距记录](../research/horizontal-margins.md)。 |
| 矩形复制/填充/属性：DECCRA `$v`、DECFRA `$x`、DECCARA `$r`、DECRARA `$t`、DECSACE `*x` | 已证（有限范围） | 共用有界坐标解析；一行临时存储处理重叠复制，保留组合字符/颜色/保护/链接；支持流式与矩形属性、Unicode填充、DECRQSS `*x`。独立XTerm单元/属性对照、ASan/UBSan、真实ConPTY像素/Shift复制/Sixel/缩放及3000次复制压力已测，见[矩形记录](../research/rectangle-editing.md)。页号按xterm处理为当前页；复制字符而不复制Sixel像素。DECSCA、DECSEL/DECSED、DECERA/DECSERA 见[擦除记录](../research/selective-erase.md)。 |
| SGR基础、16/256色、`;` 形式 RGB：`38;5;n`、`48;5;n`、`38;2;r;g;b`、`48;2;r;g;b` | 颜色局部已证；样式部分源码已见 | `test_colour_and_alternate_screen` 覆盖FG/BG真彩色、索引色和0重置；T SGR有bold/dim/underline/blink/reverse/strike。渲染效果和每种重置仍需验证。 |
| SGR冒号子参数：`38:2::r:g:b`、`48:2::r:g:b`、`4:0..5`；下划线色58/59；italic 3/23、conceal 8/28 | 已证（有限范围） | `test_sgr`验证冒号/分号RGB与索引颜色、样式/颜色独立复位、21双下划线、压缩历史、备用屏、resize、普通文本复制和CAN/SUB恢复；`sgr_window_smoke.py`经真实ConPTY检查五种下划线像素、反色不改显式下划线色、动态调色板、隐藏装饰、斜体及同步快照。每格新增4字节装饰字段；每CSI上限32主参数、每参数8子参数，溢出整条拒绝。隐藏仅影响呈现；RTF的扩展样式导出尚未补齐。 |
| 光标形状 `CSI Ps SP q`（DECSCUSR），DEC12闪烁 | 已证（有限范围） | 0/1闪烁方块、2常亮方块、3/4下划线、5/6竖线、7恢复配置；未知/溢出/子参数拒绝。查询反映当前形状与闪烁，25可见性独立；普通重配不覆盖应用样式，显式光标设置/RIS恢复配置。`test_queries`和真实窗口像素/闪烁/同步冻结测试通过。 |
| 软复位 `CSI ! p`（DECSTR） | 已证（有限范围） | 重置SGR、origin/insert、边距、字符集、当前屏保存光标；按配置恢复wrap、应用光标/小键盘、光标样式和modifyOtherKeys。保留当前文字/历史/位置/待换行、另一屏保存光标、UTF-8、制表、鼠标/粘贴/kitty/9001、Sixel和2026冻结。核心与真实ConPTY像素、输入和屏切换测试通过；对照及差异见[状态记录](../research/state-control.md)。 |
| 私有模式保存/恢复 `CSI ? Pm s/r`（XTSAVE/XTRESTORE），DECNKM66，DECOM/DECSC | 已证（有限范围） | 为现有22类模式建立88字节全局缓存；鼠标跟踪、坐标编码和备用屏别名按组保存，1048使用光标槽，未知模式忽略、本地禁用优先；初始缓存0、重复保存覆盖、RIS/DECSTR保留。补齐DECOM设置/清除归位、相对CPR和DECSC origin恢复。原生测试验证恢复1016后缩放和Shift复制；其余未实现模式仍不支持保存，G2/G3完整保存尚未补齐。 |
| Unicode：UTF-8、宽字符、组合字符；emoji/ZWJ/variation selectors/区域旗帜、bidi、grapheme | 前三项局部已证；其余待核实 | 测试包含跨读取边界中文和组合音标、选择复制。Nerd 图标回退现已验证 BMP/补充平面、变体选择符、格宽、Shift复制和缩放，见[字体验证](../research/font-fallback.md)。RTL绘制缓冲泄漏已用旧/新二进制的5000次重绘对照验证修复。IMM 提交、补充平面字节输入和合成 DPI 已有[专项证据](../research/input-methods.md)。完整grapheme、emoji整形、通用字体fallback和物理IME候选操作仍需专项测试。 |

## 窗口与历史重排

主屏及压缩历史默认按软换行重排，显式换行保持分段；当前/保存光标和历史视口随内容移动。
`test_reflow` 和原生 ConPTY 测试覆盖宽字符、组合链、样式、OSC 8、Shift 跨行复制、
备用屏恢复、历史淘汰及长段落。备用屏、Sixel 覆盖行、DEC 双宽/双高及可信提示行保持网格，
图片像素不被拆分或重采样。可通过 Window 的重排选项恢复旧裁剪模式。
具体边界、内存与证据见 [重排记录](../research/reflow.md)。真实设备、多屏 DPI、
复杂 grapheme 与长时间 agent 会话仍待验收。

## 输入、鼠标、协商与同步

| 家族 / 具体范围 | 状态 | 工作区证据与缺口 |
| --- | --- | --- |
| 普通/应用光标键、数字键盘、F键、Alt/Ctrl/Shift修饰 | 源码已见 | T `format_arrow_key` 等与W键盘路径；真实Windows键盘布局、AltGr、IME和ConPTY传输尚需验证。 |
| xterm `modifyOtherKeys`：`CSI > 4;Ps m`，扩展键格式 | 已证（字符键与 Windows 映射） | 支持 0–3 级、`>4n` 禁用、`?4m` 查询、`>4;0/1f` 格式、`?4g`/`>4g` 查询及 DECRQSS。`>4;level:mask m` 按 X11 修饰位屏蔽字符查找；主/备用屏共用，RIS 回到配置初值，kitty 增强输入优先。8 字节协议状态，编码无堆分配；Windows 预览字符不消费死键，AltGr、俄语、Unicode 提交及本地快捷键有测试。20 组核心中的 `test_mok` 与真实 ConPTY 精确字节、两套初始配置、鼠标选择和缩放通过。独立 XTerm(412) 对照及 Shift-Tab、格式查询/DECRQSS 差异见 [研究记录](../research/modify-other-keys.md)。其他资源 P0/1/2/3/6/7 尚未实现；物理键盘和真实 IME/agent 仍需验收。 |
| CSI-u / kitty keyboard：查询 `CSI ? u`，设置 `CSI = flags;mode u`，push `CSI > flags u`，pop `CSI < n u` | 已证（有限范围） | `nemo_keyboard.c`实现flags 1/2/4/8/16，主/备用屏各32项栈、满栈淘汰最旧项、显式pop 0不操作、RIS清空、resize/光标保存不改模式。Win32接入按下/重复/释放、左右修饰键、锁状态、PC101基础键码、布局转换、死键/AltGr、UTF-16文本提交；本地快捷键优先。失焦补发已报告按键的释放并清状态。编码最多16个文本码点/256字节，无部分序列；栈66字节，按键跟踪按需分配约24KiB。`test_keyboard`及真实ConPTY精确字节、主备屏、冻结输出、Unicode提交、Ctrl+Shift+C/V和resize测试通过。Windows物理F键映射到F24，核心编码覆盖F35；Hyper/Meta无物理映射。真实IME候选/组合、Alt数字输入、更多布局和真实agent尚待验收；不以合成消息代替物理设备。参照 [kitty键盘规范](https://sw.kovidgoyal.net/kitty/keyboard-protocol/)；普通CSI u仍保留光标恢复。 |
| Windows Win32 input `?9001 h/l` | 可选路径已证（有限范围） | 默认关闭；Terminal/Keyboard/Extended可启用。48字节栈编码器，按需约24KiB按键表，UTF-16、左右修饰键、重复/释放、控制信号、真实控制台鼠标及resize记录有测试；kitty/modifyOtherKeys优先。当前ConPTY普通VT转换丢失F21–F24，且绕过传统自定义按键，不能视为完整键盘验收；见[记录](../research/win32-input.md)。 |
| 鼠标9/1000/1002/1003；传统编码、1005 UTF-8、1006 SGR字符格、1015 urxvt | 已证（有限范围） | `test_mouse` 精确字节覆盖三键、Alt/Ctrl、四向滚轮、坐标边界、最后SET编码/匹配RESET、tracking RESET、拖动去重、双宽行和历史独立坐标、Shift中途接管及取消。传统坐标最大223、UTF-8最大2015，越界不发；capture取消回最后合法点释放。 |
| 1016 SGR像素、1007备用屏滚轮 | 已证（有限范围） | 核心测同格内像素移动/resize裁剪，1007仅备用屏且服从DECCKM。真实Win32→ConPTY→Python验证像素移动与窗口缩放；多屏DPI、触控板/物理设备尚需验收。 |
| 鼠标侧键 XBUTTON1/2（xterm 按钮8/9） | 已证（有限范围） | 核心测试覆盖128/129按钮码、修饰键、各编码、拖动、取消、Shift隔离和无本地绑定。真实Win32→ConPTY验证两个侧键及左键/侧键混合捕获；重复获取自身捕获不再误释放全部按键。物理设备尚待验收。 |
| 鼠标1001 highlight tracking | 已证（有限范围） | 应用CSI五参数T握手、限制行范围（lastrow排除）、半开字符选区、正反向短/长回报、五种坐标编码、双击选词/三击选行、软换行与宽字符已测。使用独立视口高亮，不写剪贴板；Shift仍转入本地选择。等待握手最多1秒，期间输入/解析/绘制继续；取消、缩放、字体、焦点、屏幕/编码切换、配置与RIS均清理。核心精确字节与真实窗口像素/ConPTY测试通过；复杂bidi/历史边界、极端坐标与物理设备仍须更广验收。Ctrl+右键保留本地菜单。 |
| 焦点1004：`CSI I` / `CSI O` | 已证（有限范围） | 核心验证开关、重复通知抑制、焦点丢失先释放拖动及RIS。Win32 handler注入测试证明通知经过ConPTY抵达子进程；并非物理焦点/所有窗口管理器行为认证。 |
| bracketed paste 2004：`CSI 200~` / `CSI 201~` | 已证（有限范围） | `test_bracketed_paste` 验证UTF-8内容、开关和空粘贴；仍须测大段、多行、取消、内嵌结束符、系统剪贴板及真实ConPTY。 |
| synchronized output 2026：`CSI ? 2026 h/l` 与 `CSI ? 2026 $ p` 查询 | 已证（有限范围） | 解析/输入/查询继续，冻结的是呈现。`test_sync`用可控时钟证明重复SET不续期、单RESET结束、旧timer隔离和1秒超时；`sync_window_smoke.py`证明文本/Sixel/颜色期间像素不变、结束/超时更新、输入继续与resize释放。冻结按32行压缩，模块总预算8MiB；资源不足拒绝本次冻结并记录事件，不保留部分快照。 |
| DA/DA2/DA3/XTVERSION：`CSI c`、`CSI > c`、`CSI = c`、`CSI > q` | 集成中，核心测试已过 | DA3 不再触发默认模式的 SCO 隐藏光标，显式 SCO 模式保留旧行为；首参数零／省略才回复，额外普通参数忽略。XTVERSION 明确标识 Nemoterm(PuTTY 0.85)，DA2 保留旧兼容值。独立 XTerm、原生整流回复和像素验证待完成，见[身份查询记录](../research/identity-queries.md)。 |
| DSR/CPR：`CSI 5n/6n` | 源码已见，局部已证 | 状态／光标回复已有专项测试；完整 origin/边距组合与回包顺序仍须逐项证明。 |
| DECRQM/DECRPM：`CSI [ ? ] Ps $ p` → `... $ y` | 已证（有限范围） | `test_modes`验证标准4/12/20/34、DEC基础模式、备用屏别名、鼠标各组、Sixel模式、2004及2026，未知0；配置禁用的相关模式返回4。与xterm一致只处理首Ps。身份查询见上一行；不能由有限模式报告称所有查询已支持。 |
| 窗口操作 `CSI Ps ... t`、像素/字符尺寸、标题栈22/23 | 部分源码已见 | T含窗口大小、位置、最小化等部分操作；每个子参数、权限设置、DPI和查询准确性都待核实，尤其标题栈。 |

## OSC、DCS、图像与shell语义

| 家族 / 具体范围 | 状态 | 工作区证据与缺口 |
| --- | --- | --- |
| OSC0/1/2、DECterm21标题 | 0/2局部已证；其余源码已见 | `test_wintitle`验证BEL/ST、逐字节UTF-8标题和DCS不能误当标题。长标题、取消、截断、query配置需补测。 |
| CSI22/23 标题栈和指定槽位 | 核心与本机原生已测；单文件CI待验 | `test_titles`对照22组独立xterm结果，测试编码、权限、空字段、取消与2万次压栈；`titles_window_smoke.py`核对ConPTY回复及真实窗口标题。10个惰性分配槽位，每字段最多4096字节；溢出深度封顶，指定槽位共享存储。标题模式和其他窗口控制仍待实现，详见`research/window-controls.md`。 |
| OSC4调色板设置/查询、多组；104选择性/全部重置 | 已证（有限范围） | `test_colour`穷举数值精度；`test_osc_colour`逐字节验证多项设置/查询、BEL/ST、无效索引、取消、超长整条拒绝。104只清0..255会话覆盖；256..261不沿用PuTTY私有索引。原生ConPTY调色板往返已测。 |
| OSC10/11/12及110/111/112：默认前景/背景/光标色，设置/查询/恢复 | 已证（有限范围） | 设置/查询、10顺序参数、各自恢复、与104互不误清均已测；回复匹配BEL/ST。真实ConPTY验证10设置/查询。支持Xlib rgb:1..4位和#四种精度及8个固定色名，非完整X11色名库；rgbi需设备光强转换，当前明确拒绝。 |
| OSC8：`8;params;URI`，空URI关闭、`id=` | 已证（有限范围） | `test_hyperlink`验证逐字节BEL/ST、取消/非法/超长输入、同id+URI分组、SGR独立、保存恢复/1049/RIS、宽/组合字符、插删擦除、压缩历史、resize/字体变化、bidi、2026冻结/超时与已绘制画面的命中；Shift复制仅含标签。记录256KiB/1024条FIFO上限，URI2083字节、id250字节、OSC8载荷4096字节；超限旧编号失效且不复用。真实Win32/ConPTY测试验证完整地址悬停、分组下划线、Ctrl打开/菜单复制、默认与禁用设置、file主机匹配、应用鼠标/多键/Shift/缩放取消及冻结画面的目标。只接受ASCII/百分号编码URI；默认HTTP/HTTPS/FTP/mailto及本机Windows驱动器file，其他注册协议须显式启用。远程file只允许复制；不实现URI片段到文件行号跳转。ASan/UBSan及原生6000长链接+800Sixel压力测试覆盖有界资源。参照 [OSC8原始规范](https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda)。 |
| OSC52：`52;Pc;Pd`，Base64设置、`?`查询 | 已证（有界文本与Windows映射） | 流式解码，每次UTF-8文本256KiB；读写独立配置，默认允许写、禁止读。c=系统剪贴板，s别名c，p=本地选区，q/0..7共享1MiB辅助缓存；空Pc为s0，按请求顺序查询首个可用目标。BEL/ST、碎片/取消/非法输入、精确上限、缓存淘汰、复位/撤权后的迟到回复、输出积压均有核心测试。原生测试覆盖四种权限、真实中文/emoji剪贴板、保留本地选择、同步输出、锁竞争和延迟渲染期间UI响应；不代表X11选择所有权语义或所有应用验收。详见REQUIREMENTS中的策略。 |
| OSC7：`7;file://host/path`；OSC9;9；OSC633 P;Cwd | 已证（有限范围） | 有界 UTF-8 目录元数据、百分号/反斜杠转义、主机判断、复制 URI 与复制会话目录继承；支持 Windows、Git Bash 挂载路径和 WSL --cd。核心、真实子进程 OS cwd、中文路径、reset/resize、错误恢复和一万次更新已测；设置与单文件证据见[目录记录](../research/working-directory.md)。 |
| OSC133 A/B/C/D；OSC633 A/B/C/D/E、P IsWindows / HasRichCommandDetection | 已证（有限范围） | 有界命令标记、可选退出码和转义命令文本；主屏历史定位、重排、导航和命令／输出选择。核心、ASan/UBSan、云端及本机单文件验证通过，含原生菜单与可配置快捷键；不自动注入 shell 配置。属性目前仅记录，nonce 不用于认证。具体状态见[标记记录](../research/shell-marks-design.md)。 |
| OSC633 其余扩展 | 缺失 | Completions 等未实现；已支持的子命令不代表整个命名空间完成。 |
| OSC1337 CurrentDir / RemoteHost | 已证（有限范围） | 目录与主机分开更新；远端路径可复制但不用于本机启动。与 OSC7 共用有界存储；[目录记录](../research/working-directory.md)。 |
| OSC1337 SetMark | 已证（有限范围） | 独立位置书签，参与导航；不虚构未知命令或输出范围。[标记记录](../research/shell-marks-design.md)。 |
| OSC1337 用户变量及其余非图像命令 | 缺失 | 命名空间按子命令登记；已支持的子命令不代表支持其余命令。 |
| OSC1337图像：`File=...:base64`，MultipartFile/FilePart/FileEnd | 缺失 | 图像尺寸、分块、编码、滚动、擦除、备用屏、动画/静态差异和资源预算均需独立验证。参照 [iTerm2图像协议](https://iterm2.com/documentation-images.html)。 |
| DCS DECRQSS：`DCS $ q Pt ST`，如`m`、`r`、`SP q` | 已证（有限范围） | 支持现有SGR状态`m`、滚动边界`r`、光标`SP q`、列数`$|`、行数`*|`；成功1$r，未知/超长0$r且不回显请求。输入最多63字节；CAN/SUB/新ESC取消、ST结束和与Sixel共存已测。SGR回复可重放，包含RGB、索引色及下划线样式/颜色。另支持 DECSCA；DECSLRM左右边距`s`和DECSACE范围`*x`也已实现；DECSCL等其他状态字符串仍不支持；未实现的状态不虚报。 |
| DCS XTGETTCAP：`DCS + q hex-names ST`，如`Co/TN/RGB`及键能力 | 已证（有限范围） | 查询终端名、颜色能力及逻辑键编码，复用实际输入编码器。支持功能键1..63的termcap/terminfo名称、导航及扩展修饰键名称、数字小键盘与退格/反向Tab等；不是任意terminfo程序查询。多名称单回复，未知名称结束列表，已知不可用名称无值；最多2047字节输入，回复小于14KiB。核心测试覆盖断片、异常/取消、配置和模式切换；真实窗口15类无修饰键在普通/应用光标模式均与查询一致。物理键布局、本地快捷键、数字键盘完整修饰语义和剩余名称仍待验。 |
| Sixel：`DCS P1;P2;P3 q ... ST`、repeat/color/raster指令；DECSDM80等 | 解码、局部滚动、行列/字体resize保留及有限实屏已证，完整兼容未完成 | `test_sixel`、`test_sixel_terminal`和两组Sixel原生窗口测试覆盖跨滚动边界保留、横向裁剪/恢复、主屏临时历史、备用屏删除行、清历史不删可见部分及移动后擦除。图片保持原始像素尺寸，按扫描行记录字符单位的滚动位移；字体变化后孔洞不变，新擦除按当前格宽/格高精确换算。擦除位图按32行按需分配，位置/掩码/解码器同享4MiB预算。仍缺真实多屏DPI切换验收、完整调色板重染、更多像素擦除边界/查询验收。 |
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

1. **直接影响现代agent的缺口**：kitty键盘的真实应用/IME验收及剩余SGR（如overline等）；继续完成Sixel像素和资源生命周期。同步增加断片输入/错误恢复/准确回复测试，不宣告尚未实现的能力。
2. **交互和协商完整性**：剩余DECRQSS状态与XTGETTCAP名称、OSC52真实远程应用验收、1001边缘场景与物理设备验收、Windows输入模式、resize/DPI和大坐标、更多光标/边距/擦除行为；在真实Claude Code/Codex和shell里记录可复现输入及输出。
3. **剩余现代及历史范围**：OSC133及剩余633/1337语义，kitty/iTerm图像扩展，完整xterm家族逐项拆解及测试。优先级表示先后次序，不是把后项从目标删除。

每一项完成至少需要：序列与参数定义 → 对应源码和状态生命周期 → 分块输入与回复测试 → 有界资源测试 → 必要的真实窗口/应用验证。图片、链接、历史和新样式加入后，应重跑代表性agent负载的私有工作集、总工作集和长时间峰值；本账本不证明内存门槛已经成立。


2026参考：[Contour同步输出规范](https://contour-terminal.org/vt-extensions/synchronized-output/)。
本项目的1秒硬超时、重复SET不续期、resize/字体/DPI/reset/reconfig/退出和本地选择/滚动结束冻结，
是明确的恢复策略，不宣称规范规定唯一时限。8MiB预算含codec自定义分配和条带像素，
不含OS的句柄内部开销；进程WS须另测。`test_snapshot`离屏验证3840x2160；
本机真实窗口被显示器限制到1907x1061，不能把该进程内存记录冒称4K窗口实测。


DECSCA、DECSEL/DECSED、DECERA/DECSERA 已实现并通过核心、原生像素和剪贴板测试；独立 XTerm 对照及有意差异见 [选择性擦除记录](../research/selective-erase.md)。ISO SPA/EPA 仍待实现；左右边距和矩形填充/复制/属性操作已完成有限验收，见对应表格行。


### Windows 输入法、Unicode 字节流与 DPI

原生前端按 IMM 第二次读取的实际字节数提交文本，拒绝异常/奇数长度，临时
提交缓冲上限 64 KiB。新增 WM_UNICHAR 标量输入及能力探测；组合边界清理
待配对的 WM_CHAR 代理项。字体和 DPI 变化同步更新 IMM 组合字体。
源码构建的 OpenConsole 保留跨读取的 UTF-16 代理对，正确处理很小的 UTF-8
目标缓冲；内部流读取不再清掉解码状态。详见[实现、基线与验收范围](../research/input-methods.md)。

新增原生 CI 组覆盖 IMM 故障注入、Unicode/kitty 文本、合成 DPI 像素和
1–1024 字节的控制台原始/行输入。物理 IME 候选操作、真实多屏切换及完整
字素整形仍未验收，不能由合成消息测试替代。

### 真实 Codex 界面与原生控制台事件

实际 Codex 0.167.0 客户端已用于中文/emoji 输入、流式 Markdown、长回复、
缩放、Shift 网格选择及 Ctrl+Shift+C/V 的本地响应回归；默认/内嵌两种模式
均独立运行。宿主不再在 UTF-16 代理项之间插入携带字符的虚构释放事件。
快速跨位置选择按独立点击处理，同位置双/三击及 1001 高亮握手另有验证。
这不代表在线模型、Claude Code、物理输入设备或长期会话已完成验收；
具体证据和边界见[真实客户端记录](../research/real-agent.md)。
