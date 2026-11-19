# 历史单文件预览与验证记录

下文保留当时的记录。每条数字都对应所列提交；当前测试版请从 [README 下载](../README.md#下载)。

## 开发快照

[下载 Windows x64 单文件测试版 `6a2dc83`](https://github.com/xiongnemo/nemoterm/actions/runs/44523229386/artifacts/14528333115)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `39c3b368061f104858dff466dd5a2416887c76dfc94481be68f9d7b79841d450`。

按住 Shift 和鼠标左键拖选时切换标签，再松开鼠标，目标标签已有的选区现在会保留，可以立即复制。真实键鼠的标签组从 8/9 改善到 9/9；GDI 与 DirectX 之间两个切换方向均已验证。160×48 压力测试各 6/6，前端私有工作集峰值分别为 19.579 MB 和 29.061 MB。[对照截图和原始记录](../research/tab-drag-release.md)。

这是开发测试版。[严格 XTerm 412 宽字对照](../research/column-edge-integrity.md)和 [ReGIS 历史画面对照](../research/regis-presented-pairs.md)仍有差异。Codex 正常编辑器可贴图。[这一版的完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44523229386) · [同一 EXE 的交互回放：81/81](https://github.com/xiongnemo/nemoterm/actions/runs/44525718005)。

[下载 Windows x64 单文件测试版 `0d8f731`](https://github.com/xiongnemo/nemoterm/actions/runs/44515756392/artifacts/14525912387)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `8e8fdd89176d0204d72c05fd62b8bb62754eba052fab2c8e399bc8bc8fa7af12`。

按住 Shift 双击混排英文和从右向左书写的文字时，会选中屏幕上相邻的词，不再隔着标点选中远处的字。38 项高亮与剪贴板检查在旧版通过 14 项、新版全部通过。普通双击沿用 profile 里的选词规则。另在 tmux 内的 Vim 验证了 Shift 拖选和矩形复制，Codex、OpenCode、Claude Code 的 10 项默认网格交互也已通过。[对照截图、交互记录与内存](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/bidi-word-selection.md)。

同一 EXE 的[交互回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/bidi-words-exact-interaction-0d8f731.zip)为 78/80，两项未过的是 Codex 启动草稿立即贴图。

[下载 Windows x64 单文件测试版 `2c63154`](https://github.com/xiongnemo/nemoterm/actions/runs/44510289348/artifacts/14523910915)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `22e5cc72fee4c1f157468b29c5af8b2eaccbcbda1c90637467e74fb1309e739f`。

按住 Shift 和鼠标左键选字时，如果应用在拖动前擦掉了按住的字，松手会取消这次选择，不改剪贴板。如果只擦了邻字，或按住的字符受保护，则仍能正常复制。52 项擦除手势在 GDI 和 DirectX 上全部通过；同一 EXE 的 10 项默认网格真实客户端选区回放也已通过。[高亮截图、原始记录及内存样本](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-erase.md)。

这份 EXE 的[原始完整交互回执](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-erase-aggregate-2c63154.zip)为 78/80；两项均为 Codex 启动即贴图。GDI 和 DirectX 的压力私有工作集峰值分别是 19.562 MB 和 28.705 MB。

[下载 Windows x64 单文件测试版 `2c0152c`](https://github.com/xiongnemo/nemoterm/actions/runs/44503310589/artifacts/14519395078)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `79e504be64bfc37c2fdfaa79ae179b9a5e9da4ca08ebae29cc8782e3a28ec663`。

按住 Shift 和鼠标左键时，如果应用把 `K` 改成了 `Z`，松手不会误复制 `ZLM`；原字没变或只因双向排版而移动时，仍可继续选中它。宽字、组合附标、emoji 变宽和换行均已回放：112 项窗口消息检查和 10 项系统键鼠检查通过。[修复前后的高亮截图和剪贴板记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-repaint.md)。

同一 EXE 的交互回归为 **78/80**：两项未通过的都是 Codex 刚启动时贴纯位图。真实客户端的 24 项选区和复制回放通过。六种 160×48 压力负载中，前端私有工作集最高 GDI **19.362 MB**、DirectX **28.828 MB**。严格 XTerm 宽字对照有[三处差异](../research/column-edge-integrity.md)，ReGIS 历史画面对照也未全过。[交互汇总和原始内存记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-repaint-aggregate-2c0152c.zip) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44503310589)。

[下载 Windows x64 单文件测试版 `b7bf0fd`](https://github.com/xiongnemo/nemoterm/actions/runs/44496986357/artifacts/14516475194)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `30de4cef81033fb47cc1dffce629bf7cfa22542f53dd5d158874efe51b6c44e9`。

本版修复了按住 Shift 从屏幕选字时，应用插入或删除字符导致复制错字的问题。按住 `K` 时即使它被挪动两格，再拖到 `M`，复制的仍是 `KLM`。GDI、DirectX 上新增的 66 项选区检查通过；关闭确认点“取消”后直接输入、中英文渲染设置在 100%–200% 缩放下的排版也已复测。[截图与修复前后对照](../research/selection-column-edits.md)。

同一 EXE 的完整交互回归 **78/80**，两项未通过的都是 Codex 刚启动时贴纯位图。六种 160×48 压力负载中，前端私有工作集最高 GDI **19.120 MB**、DirectX **28.881 MB**。另有三个 XTerm 宽字边界单元格仍有差异，ReGIS 的历史对照也未全过。[原始交互与内存记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-aggregate-b7bf0fd.zip) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44496986357) · [历史测试版](#开发快照)。

[下载 Windows x64 单文件测试版 `bec4002`](https://github.com/xiongnemo/nemoterm/actions/runs/44491317295/artifacts/14512847979)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `9f43a0ddc23219f3ac3974fee73b3b6f8de8f45c63adf3e668d7eef99984275e`。

本版修复了同时复制到位图和空文本时 Ctrl+Shift+V 没有反应的问题。非空文本和文件列表仍然优先。已就绪的真实 Codex 四项贴图全部通过，原生子进程十项输入全部通过；OpenCode 的正文及标题请求另外记录。[贴图动作与逐像素验证](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/clipboard-empty-text.md)。同一 EXE 的 13 份交互分组记录共 78/80，未通过的两项均为 Codex 启动即贴纯位图。六种 160×48 压力负载，前端私有工作集峰值为 GDI **19.137 MB**、DirectX **28.750 MB**。[原始内存与交互记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/clipboard-aggregate-bec4002.zip) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44491317295) · [历史测试版](#开发快照)。

[下载 Windows x64 单文件测试版 `6bed777`](https://github.com/xiongnemo/nemoterm/actions/runs/44486109121/artifacts/14511425344)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `e50c888b1933893896de9889492b886a160f157ed3c4cd3ebbcd8c7d685019de`。

新终端第一次显示 Sixel 图像时，尚未定义的共享颜色现在和 XTerm 一样是黑色。七个启动、复位和私有色表场景从 2/7 改善到 7/7。[实际窗口与 XTerm 对照](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-bank-start.md)。同一 EXE 的 [交互测试](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-bank-aggregate-6bed777.zip)通过 78/80；未通过的两项都是在 Codex 刚启动时贴图，等待编辑器就绪后两种贴图方式均通过。六种 160×48 压力负载的前端私有工作集最高为 GDI **18.678 MB**、DirectX **29.200 MB**。[完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44486109121) · [历史测试版](#开发快照)。

[下载 Windows x64 单文件测试版 `e02f0d0`](https://github.com/xiongnemo/nemoterm/actions/runs/44477059678/artifacts/14507241831)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `be28e4e503383070855dac42d679c5427e224a68c3fb13195f7d2b820d0f2120`。

按住 Shift 和鼠标左键之后，如果原来的字被滚出缓冲区或被分栏边界截断，松手会取消选择，右键也不会复制顶上来的文字。原字还在屏幕或滚动历史里时仍然能选。保持应用鼠标跟踪的 32 项丢字用例和 4 项实际键鼠均通过。同一 EXE 两轮六种 160×48 压力负载的前端私有工作集最高为 GDI **19.337 MB**、DirectX **29.372 MB**。[全组交互回放 79/80](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-all-discard-e02f0d0.zip)，未通过的是 Codex 启动时的真实键盘贴图。[选区前后截图](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-discarded-scroll.md) · [本版交互、内存与未通过项](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-preview-e02f0d0.md) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44477059678) · [历史测试版](#开发快照)。

[下载 Windows x64 单文件测试版 `30304bc`](https://github.com/xiongnemo/nemoterm/actions/runs/44472521397/artifacts/14505341500)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `712ed73e131f6498a354aac6eae77e31dd95a703f952a14189504486384b449a`。

当应用只滚动部分列、而你已按下 Shift 和鼠标左键时，现在拖选能从原先按住的字开始，即使这段混排文字在屏幕上换了行或列。普通和矩形选择在两种字体、GDI 和 DirectX 上的 32 项都通过；实际键鼠也验证了右键只复制、Ctrl+Shift+V 才粘贴。整套交互 **78/80**；六种 160×48 压力负载的前端私有工作集峰值：GDI **19.186 MB**、DirectX **29.565 MB**。[选区前后截图](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-split-scroll.md) · [本版交互、内存与未通过项](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-preview-30304bc.md) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44472521397)。

[下载 Windows x64 单文件测试版 `810a26f`](https://github.com/xiongnemo/nemoterm/actions/runs/44468952910/artifacts/14503279012)。解压后只需 `nemoterm.exe`；EXE 的 SHA-256 为 `24deed2cdaa8a3743793c014048ce057333c7f9bc77c4b59de545e5b7bbd27d3`。

按住 Shift 后若应用先整行滚屏再拖动，现在能选中原先按住的字，不会多复制相邻的一行。部分列单独滚动时，此测试版仍可能多选邻字或邻行。普通和矩形选择在两种字体、GDI 和 DirectX 上的 16 项均通过。连续两次粘贴长文本也通过。整套交互 **78/80**；160×48 六种压力负载的前端私有工作集峰值为 GDI **18.907 MB**、DirectX **29.630 MB**。[选区前后对照](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-during-scroll.md) · [本版交互、内存与未通过项](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-preview-810a26f.md) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44468952910)。

[下载 Windows x64 单文件测试版 `2ca68df`](https://github.com/xiongnemo/nemoterm/actions/runs/44464971332/artifacts/14501593009)。解压后只需 `nemoterm.exe`，压缩包中的 `SOURCE-HOST.json` 用于核验来源。EXE 的 SHA-256 为 `f2cb4fbae5a52ba3be8e4abb979a363e2b279591269b43838ee1da40957f7ca0`。

这个版本修复了连续粘贴多行文本时第一段被截断的问题。GDI、DirectX 的系统剪贴板回放均逐字通过，包含中文、emoji 和括号粘贴标记。整套交互 **78/80**；160×48 压力测试的前端私有工作集峰值为 GDI **19.268 MB**、DirectX **28.848 MB**。[修复前后原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/consecutive-paste.md) · [本版交互与内存](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/paste-preview-2ca68df.md) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44464971332)。

[测试版 `7ec651d`](https://github.com/xiongnemo/nemoterm/actions/runs/44457337912/artifacts/14497589034) 修复了默认配置下 Claude Code 2.1.322.0 的希伯来文被排两次、拖选复制到相邻字符的问题。直接启动和经 PowerShell 启动均已用实际窗口和系统剪贴板验证；三种客户端的选区回放 **10/10**。160×48 压力测试前端私有工作集峰值为 GDI **19.964 MB**、DirectX **29.467 MB**。整套交互 **76/78**；Codex 启动时立即贴图的两项未通过，待编辑器报告就绪后通过。[截图、原始数据与已知限制](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/claude-writer-order.md)。

[上一版 `6ee2996`](https://github.com/xiongnemo/nemoterm/actions/runs/44411510449/artifacts/14477886358) 修复了应用能画 ReGIS 图、却查询不到这项能力的问题。程序现在可在绘图前读到 800×480 的默认画布。GDI 与 DirectX 都验证了根据返回尺寸绘图、重绘后仍可见；同一文件通过选区与关闭确认回放。12 项 160×48 压力测试中，前端私有工作集最高 GDI **18.84 MB**、DirectX **28.86 MB**。整套交互为 **76/78**，剩余两项是默认 Claude 的混排字序。[前后截图、文件校验与未通过的画面对照](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-discovery.md)。

[单文件测试版 `b7f4bfa`](https://github.com/xiongnemo/nemoterm/actions/runs/44404296808/artifacts/14474875134) 修复了应用只移动光标就导致 Shift 选区消失、右键被应用接管的问题。现在应用可以继续更新旁边的文字，仍能右键复制原来高亮的内容；真正改写所选字形时才取消旧选区。同一版本六种 160×48 压力负载的最高前端私有工作集为 GDI **19.10 MB**、DirectX **29.13 MB**。[修复前后截图与 32 项窗口检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-cursor-traffic.md) · [同机运行 Codex 的前端内存对照](../research/pterm-findings.md) · [上一版的全屏与关闭确认检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/xtwinops-fullscreen.md) · [混排选区与客户端已知问题](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-3da2fc3.md)。

在 Codex 0.167.0 里贴图，请等编辑器就绪，按一次 `Ctrl+Shift+V`，看到输入框中出现图片附件再发送。窗口标题变成项目名并不能保证第一次贴图会成功：本版复查时两种实按快捷键只有一种成功，编辑器报告就绪后两种均成功。[三个时点的远程回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/claude-writer-order.md#codex-贴图时机)。 从资源管理器复制 PNG 也一样：启动草稿会把文件路径当文字，不能代替图片附件。[文件列表与真实提交对照](../research/codex-file-draft-order.md)。

[较早的单文件测试版 `f564927`](https://github.com/xiongnemo/nemoterm/actions/runs/44374468391/artifacts/14460047904)：修复“窗口 → 外观 → 字体访问”的快捷键与“取消”冲突。在 GDI 和 DirectX 上均已验证：应用改变当前标签的字体不会修改 profile；撤销权限后立即恢复原字体。[同一 EXE 的交互验收](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-f564927.md)为 72/74，两个未通过项均为 Codex 启动阶段立即贴图；编辑器就绪后通过。160×48 压力测试私有工作集峰值为 GDI **18.89 MB**、DirectX **28.75 MB**。

新版 38de2ad 已验证 WSL 子程序能收到终端类型、真彩色提示和终端名称；见[两种 TERM 的真实 less 回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/wsl-terminal-identity.md)。

[单文件预览 `a9c8150`](https://github.com/xiongnemo/nemoterm/actions/runs/44338343977/artifacts/14443251390) 修复了调试接口把方向键当作数字小键盘的问题。以 `TERM=xterm` 和 `xterm-256color` 运行真实 WSL `less`，用系统键盘和调试接口都能向下滚动、翻页、搜索并在退出后恢复原屏。真实 WSL Vim 也验证了应用接管鼠标、Shift 复制中文、窗口缩放和粘贴保存。[原始交互报告](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-a9c8150.md)：72/74 项通过；首次出现输入框时立即给 Codex 贴图的两项未通过，编辑器就绪后贴图通过。160×48 压力测试前端私有工作集峰值为 GDI **19.79 MB**、DirectX **28.49 MB**。以下较早版本的内存和汇总成绩只对应各自的 EXE。

[单文件预览 `823d8e4`](https://github.com/xiongnemo/nemoterm/actions/runs/44326592417/artifacts/14436873149)：同一 EXE 的 **74/74 项交互验收通过**，160×48 压力测试私有工作集峰值为 GDI **19.41 MB**、DirectX **29.69 MB**。真实 WSL 应用已按 `TERM=xterm` 和 `xterm-256color` 两种条目完成光标回读。见[交互、内存与终端能力记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-823d8e4.md)；历史 ReGIS 逐帧对照仍有五帧不同。

[中文选区修复预览 `a985632`](https://github.com/xiongnemo/nemoterm/actions/runs/44314169646/artifacts/14431328444)：Shift 拖选从汉字的右半格开始也会复制完整的字，矩形选区按每行实际字宽处理。Codex、Claude Code、OpenCode 均已在 GDI 和 DirectX 上用系统鼠标与剪贴板验证；见[修复前后截图、实测与内存](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/wide-selection-boundaries.md)。同时修复了[重复切入备用屏时文字和图形被清空](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/alternate-1047.md)。本版交互验收 72/74；12 项满屏压力测试全部通过（GDI 私有工作集最高 19.26 MB，DirectX 28.95 MB）。剩余两项是 Codex 刚出现输入框时贴图。

[松开时按最终字符格复制的预览 `6cf4387`](https://github.com/xiongnemo/nemoterm/actions/runs/44306179760/artifacts/14427942582)：应用接管鼠标时，Shift 拖选和矩形选区都能复制到松开鼠标的那一格。GDI、DirectX 已核对[高亮与剪贴板](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-release-cell.md)。同一 EXE 的交互验收为 72/74；两项未通过都是 Codex 刚启动时贴图，等待就绪后两种输入方式均通过。满屏压力测试私有工作集峰值为 GDI **19.50 MB**、DirectX **28.77 MB**。

[右键修复预览 `f628d89`](https://github.com/xiongnemo/nemoterm/actions/runs/44298297621/artifacts/14424658437)：如果右键复制后在另一个窗口松开，接管鼠标的程序仍能收到下一次右键的按下和松开。同一份 EXE 在 GitHub 托管 Windows 上通过 [74/74 项交互验收](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/right-button-release.md#complete-interaction-replay)，包括 36 项真实客户端交互；[仅含该 EXE 的验证包](https://github.com/xiongnemo/nemoterm/actions/runs/44298297621/artifacts/14427902321)另通过 170 项单文件检查。160×48 满屏压力测试的前端私有工作集峰值为 GDI **19.71 MB**、DirectX **29.37 MB**。

[下载 `fa6f10f` 单文件开发版](https://github.com/xiongnemo/nemoterm/actions/runs/44260021672/artifacts/14411616276)：修复了默认私有调色板在 Sixel 图片结束时意外改色。同一个 EXE 在一次远程回放中通过 [50/50 项交互与内存检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-fa6f10f-50.json)，包括真实 OpenCode 在 GDI 和 DirectX 下的右键仅复制、复制并粘贴。发布包仅含 `nemoterm.exe`，已通过[同一 EXE 的 170 项单文件检查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/single-image-fa6f10f-validation.json)。该轮满屏负载私有工作集峰值：GDI **19.45 MB**、DirectX **29.67 MB**。[窗口截图与测量说明](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/opencode-right-click.md) · [图片修复前后对比](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/private-sixel-terminator.md)。

[调色板修复预览 `9ece5e0`](https://github.com/xiongnemo/nemoterm/actions/runs/44256389198/artifacts/14406012996) 修复了 Sixel 在颜色定义尚未结束时把其他图形改色的问题。该 EXE 在同一次托管 Windows 回归中通过 46 项交互与内存检查；六项满屏负载的私有工作集峰值是 GDI **19.67 MB**、DirectX **29.29 MB**。[实际窗口截图、仍有差异的 6 帧和原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-register-terminator.md)。

要试越界拖选，可下载[交互预览 `1b24e72`](https://github.com/xiongnemo/nemoterm/actions/runs/44248020960/artifacts/14402433348)。按住 Shift 将鼠标拖出窗口上下沿，指针停住时选区也会继续滚动；先按住左键、中途才按 Shift 也能从程序接过选区。GitHub 托管 Windows 上，同一个 EXE 通过 **44/44 项交互与内存检查**及 **24 项中英文单显示器 DPI 检查**。六种 160×48 满屏负载的前端私有工作集峰值为 **GDI 18.89 MB、DirectX 28.55 MB**。另用系统鼠标和键盘在真实 OpenCode 里通过两种渲染器的选区、粘贴提交和正常退出，同一 EXE 累计通过 46 个不同用例。见[选区截图与原始记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-history.md#opencode-with-system-mouse-and-keyboard)。

[下载已通过 170 项单文件检查的 `9ece5e0`](https://github.com/xiongnemo/nemoterm/actions/runs/44256389198/artifacts/14409553339)。压缩包中只有 `nemoterm.exe`；同一个 EXE 通过了该版本的 46 项交互检查。[单文件检查回执](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/single-image-9ece5e0-validation.json) · [此前鼠标颜色版的验证记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/pointer-colours.md#candidate-you-can-try) · [更早的 `85fe9b1` 截图与实测](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-85fe9b1.md) · [ReGIS 已知差异](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-history-limit.md)。

历史构建 `329019d` 的原完整 CI 为 **21/22**：170 组单 EXE 检查、MinGW 完整套件、26 项交互、24 个中英文真实 DPI 场景及六项完整网格 GDI 负载通过。新增 Terminfo 键盘的 1,293 条原生输入流零差异。唯一失败是当时的 DirectX 25 MB 门槛。用户改为 **30 MB** 后，同一 EXE 的[六项远程 DirectX 回放全部通过](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/directx-30mb.md)，私有工作集峰值为 **29.42 MB**；GDI 原峰值为 **18.82 MB**。原 CI 记录保持不变。
[下载 `329019d` 单文件开发构建](https://github.com/xiongnemo/nemoterm/actions/runs/44083541137/artifacts/14332971661) · [完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44083541137) · [产物与验证记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-product-regression.md)。

当时所有自动测试已配置到 GitHub-hosted runner：完整 CI 统一调用协议、单 EXE、DPI、42 项交互（含 12 项完整 Sarasa 网格负载），保留截图与原始日志，不依赖开发电脑的桌面或剪贴板。入口、依赖和验证边界见 [远程测试操作单](INTERACTION_ACCEPTANCE.md)；实际运行结果见 [迁移记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/remote-test-migration.md)。

较早的 `85fe9b1` 的[单文件产物](https://github.com/xiongnemo/nemoterm/actions/runs/44236147822/artifacts/14397786086)为 4,853,760 字节；SHA-256 及验证范围见[本版记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-85fe9b1.md)。

历史开发构建 `329019d` 的单 EXE 为 4,800,000 字节；来源与 SHA-256 见 [本轮记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-product-regression.md)，新的 DirectX 30 MB 验收见[专项回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/directx-30mb.md)。此前迁移基线 `2312edd` 为 19/19 全绿，但尚未包含后来新增的完整 Sarasa 网格门槛，见 [迁移基线](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/remote-test-migration.md)。历史语言预览保留在 [语言预览记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/i18n.md)，不将旧版本结果套用于新 EXE。

## 内存

在同一台 GitHub Windows runner 上，用 Sarasa Light、160×48 和同一个 Codex 客户端运行 `6bed777`。收到回复后，单标签 GDI 前端的稳定私有工作集为 **5.075–5.091 MB**，DirectX 为 **9.699–9.728 MB**；同机 pterm 0.85 对照为 **3.744–3.781 MB**。每种配置分别按正序、反序冷启动。这些数值只统计前端进程；满屏图文的峰值另行验收。[完整采样与测试条件](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-bank-start.md)。

在同一台 GitHub Windows runner 上，用 Sarasa Light、160×48 和同一个 Codex 客户端运行 `e02f0d0`。收到回复后，单标签 GDI 前端的稳定私有工作集为 **5.362–5.419 MB**，DirectX 为 **10.027–10.031 MB**；同机 pterm 0.85 对照为 **3.748–3.781 MB**。每种配置分别按正序、反序冷启动。这些数值只统计前端进程；满屏图文的峰值另行验收。[完整采样与测试条件](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/interaction-preview-e02f0d0.md)。

同一测试版本 `ba91594` 以默认 160×48、Sarasa Light 分别运行真实 Codex、OpenCode、Claude Code，实际 Shift 拖选并回贴。六个场景均通过；前端私有工作集最高为 GDI **13.90 MB**、DirectX **17.58 MB**。密集 Unicode 加图像压力测试另为 **19.14 MB / 28.86 MB**。[逐客户端原始记录与采样范围](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/memory-budget.md#default-grid-with-real-clients)
DirectX 的上限由用户于 2026-11-18 调整为 30 MB；历史测试仍保留当时的门槛与结果。
2026-11-15 用户进一步确认：原来的内存目标针对 GDI，DX 已足够，无需继续追求约 50 MB 总工作集。
控制台宿主、shell 和终端内应用是独立进程，量测时分别记录；这是优化目标，不是任意负载下的内存保证。
历史版本 `752f3be` 在本机 Sarasa、实际 160×48、双标签的 Sixel、PNG、GIF、Kitty 和压缩 Kitty 十组负载中，
GDI 私有工作集最高 **17.32 MB**，DX 最高 **24.11 MB**。
GDI 总工作集最高 **40.05 MB**，DX 最高 **59.69 MB**；约 50 MB 的总工作集目标仅用于 GDI。
测试等待临时标签的两条 I/O 工作线程实际退出，并观察短暂 GUI 活动回落；启动和回落期间的内存样本均计入峰值。句柄和窗口资源的数值门槛保持不变，没有裁剪工作集。
完整 CI 与下载成品复核均通过；其他显卡与长时间运行仍需验证。精确镜像、像素比较和样本见 [成品验证记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-query-transaction-product.md)；此前故障恢复记录见 [D3D11 验证](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/d3d11-ci.md)。
常规内存回归与 Sarasa 交互矩阵的字体和负载不同，分别记录；历史本机内存样本不能套用于新构建。
新增的完整 160×48 Sarasa 远程负载及其内存超限、后续修复结果见 [完整网格记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/full-grid-memory-ci.md)；较小网格的绿色 CI 不能替代这项验收。
后续候选 `6247818` 合并了不可见图片定位符的绘制片段，六组完整网格 GDI 负载全部通过，密集图片私有工作集峰值为 19.32 MB，29,072 个像素比较完整通过。DX 内存超限和一次 shell 退出失败仍单独保留，具体见 [绘制修复与回归记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-placeholder-runs.md)。
旧 Direct2D 版本的 30.63 MB 失败结果保留在 [此前验证记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/relative-cursor.md)；
[分配诊断](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/local-directx-heap.md)、[初始化探针](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/graphics-initialization.md)、
[Direct3D 11 实验](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/d3d11-copy.md) 和 [句柄调查](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/handle-lifetime.md) 保留了改动依据与未解决问题。
[按需加载实验](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/delay-load.md) 收益不足，未合入；其中出现的初始化和 USER 对象计数失败仍保留，后续计时器观测与检查方法见 [资源回落记录](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/resource-settle.md)。
