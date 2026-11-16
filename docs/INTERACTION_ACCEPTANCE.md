# v0 交互验收操作单

本操作单供下一次集中测试前审阅。**本轮只整理脚本，不启动桌面测试。**
脚本结果与实际键鼠操作分别记录；自动检查通过不能代替真实输入法候选窗、
物理滚轮、屏幕缩放和用户听感。协议完整性仍以 `PROTOCOL_COVERAGE.md` 为准。

## 固定待测产物与已完成检查

以下是 profile 改动之前的已验产物；新的 profile 候选必须重新 prepare，不能复用此哈希的通过记录。

候选源提交：`f3b5b6539fede4f13dfb2ef12c1ec9e1657a8fd8`。
单文件：4,549,120 字节，SHA-256：
`de2f9e105e9186cb99fd925f8824e0573ae144ff62954b63ab3cda7c15ff0d28`。
普通 CI 四任务、单文件 CI 167 组，以及本机六组检查已通过。
Sarasa 160×48、双标签密集图像的前端私有工作集峰值 19,947,520 字节，
总工作集 47,030,272 字节；29,072 图像单元与十项标签生命周期检查通过。
这部分不列入默认交互套件，不重复做内存优化。完整记录见
[本机检查记录](../research/d3d11-local-f3b5b65.md)。

已知待复查：第二次前台 `input-byte` 在模拟 144 DPI 时，IMM 组合窗位置
为 `(1,1)`，可见光标原点为 `(4,11)`；字体高度已变为 `-24`。原始断言失败保留在
`research/interaction-input-dpi-f3b5b65.zip`。当时用户正在使用电脑，是否受焦点/
重绘时序影响尚未确定，不能据此宣称已修复或只属于测试问题。输入组首先单独跑；
复现后检查焦点、客户区偏移和重绘时序，不移除位置断言。

## 准备：不会启动终端、读取剪贴板或切换窗口

在本开发分支目录运行。Python 需带 Frida 17.24.3 与 Pillow，正式执行还需要
Windows PowerShell 及本机安装的 SarasaTermSC Nerd Font Light。`plan` 不依赖这些原生组件。

```powershell
python scripts/interaction_acceptance.py plan
$stage = Join-Path $PWD 'build/interaction-review-01'
$exe = 'C:\Users\nemo\Documents\Projects\nemoterm\build\ci-d3d11-f3b5b65-full\product\nemoterm.exe'
python scripts/interaction_acceptance.py prepare --stage $stage --exe $exe --sha256 de2f9e105e9186cb99fd925f8824e0573ae144ff62954b63ab3cda7c15ff0d28 --codex 'C:\Users\nemo\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe' --opencode 'C:\Users\nemo\scoop\apps\opencode\current\opencode.exe'
```

准备目录固定 exe、测试脚本、客户端路径/哈希、字体、命令清单和手工记录模板。
同一目录不覆盖创建。换 exe、脚本或客户端时用新目录；`identity.json` 中的
`fixture_commit` 与文件哈希区分候选源码和验收脚本版本。准备本身只复制文件和查询 Git。

## 自动检查顺序

预留桌面期间保持解锁，停止其他键盘、鼠标和剪贴板操作。执行会打开原生窗口，
部分用例改变焦点、播放声音、临时修改剪贴板；前台检测不是桌面独占锁。
所有测试只操作新建测试进程和临时配置。

| 组 | 用例 | 覆盖与通过条件 | 影响 |
| --- | --- | --- | --- |
| input | input-byte / input-wide | UTF-8 与 ReadConsoleW、中文/emoji、IMM 提交、144/192/120/96 模拟 DPI；字节、字形和组合窗坐标一致 | 前台、输入法；已知失败优先复查 |
| selection | bindings、selection-gdi/directx | 16 种矩形方向/主备用屏、中文组合字符、Shift 越过应用捕获、默认和自定义复制粘贴、旧绑定交还应用 | 剪贴板 |
| clipboard | drop-gdi/directx | 文件/目录、空格引号中文、可用 shell 的路径引用、标签目标、文本与图片优先级、括号粘贴 | 剪贴板、临时文件、shell 解析 |
| agents | agent-image-codex/opencode | 两款真实客户端接收 Ctrl+V / Ctrl+Shift+V；本地服务核对生成的 32×16 图片像素；自然退出 | 隔离配置、剪贴板、本地回环服务 |
| rendering | unicode-presented-gdi、renderers、font-zoom | 实际呈现、三种渲染器像素、字号变化/恢复及应用鼠标优先级 | 窗口与部分前台捕获 |
| mouse | mouse-wire | 鼠标上报字节、按键、滚轮及坐标；不包含物理设备操作 | 自有窗口消息；默认字体只做输入字节测试 |
| tabs | tabs/resize 的 top/bottom/left/right | 四侧栏、独立会话、预览刷新、切换、全屏恢复、缩放、关闭及进程回收 | 原生窗口；含有限资源检查 |
| settings | settings / settings-tabs | 原生设置对话框、保存/重载、bindings、选择颜色及标签宿主 | 对话框、临时注册表配置 |
| shells | shells | 已安装 shell 的检测与启动；缺少的 shell 记录缺少，不冒充通过 | 启动可用的测试 shell |
| bell | bell-api / bell-visual | BEL 调用与视觉恢复、关闭模式；OSC 的 BEL 终止符不响铃 | 可能响铃和闪烁；听感另记 |

共 26 个原生用例。先分组执行，第一组尤其需要查看失败内容：

```powershell
python "$stage/runner.py" run --stage $stage --group input --desktop-ready
python "$stage/runner.py" run --stage $stage --group selection --group clipboard --desktop-ready
python "$stage/runner.py" run --stage $stage --group agents --desktop-ready
python "$stage/runner.py" run --stage $stage --group rendering --group mouse --desktop-ready
python "$stage/runner.py" run --stage $stage --group tabs --group settings --group shells --group bell --desktop-ready
python "$stage/runner.py" status --stage $stage
```

每次失败立即停止该命令的后续用例。已通过且证据哈希未变的用例自动跳过；
确认失败原因后，可用 `--case input-byte --retry-failed --desktop-ready` 新建下一次尝试。
不要把新一轮成功覆盖成旧失败不存在。`run --desktop-ready` 不带组名会执行全部 26 组。
客户端能力已关闭，模型服务只有本地固定文本响应，不使用个人会话或账号。

如果需要收回电脑，在另一控制台执行：

```powershell
python "$stage/runner.py" stop --stage $stage
```

这会在**当前用例结束后**停止，当前窗口/剪贴板操作可能继续。等待运行命令退出后再用电脑。
要续跑，确认没有运行中的用例，再删除该目录内的 `STOP` 文件并执行选定组。
紧急中断可在启动控制台按 Ctrl+C；超时/中断只回收本轮 Job 的进程树，并记为失败。
强制终止可能妨碍剪贴板恢复，必须人工核对，不能将这种退出计为通过。

## 实际键鼠检查：用可见画面和输入记录核对

提供一个只显示生成文本、记录输入字节的测试窗口；贴入的文本不会被执行。
启动控制台保持运行，在第二个控制台切换场景和查看回执。每轮最多 30 分钟。

```powershell
python "$stage/interaction_manual.py" start --stage $stage --renderer gdi --side top --desktop-ready
# 以下命令在第二个控制台运行；重新设置相同的 $stage 路径。
python "$stage/interaction_manual.py" scene --stage $stage --name text
python "$stage/interaction_manual.py" show --stage $stage
python "$stage/interaction_manual.py" stop --stage $stage
```

`scene` 可选 `text`、`mouse`、`alternate`、`paste`、`history`、`bell`、`link`。
每次切换先保留上一阶段输入回执。当前 `report.json` 有原始 hex、解码文本和实际行列数。
场景切换会清屏；先观察再切换。测试配置不修改个人默认设置；手工保存配置时使用
`nemoterm-review-*` 名称，用完从设置界面删除该测试配置。

| 编号 | 操作 | 预期与证据 |
| --- | --- | --- |
| M01 | 以 Sarasa 默认尺寸启动，观察中文、emoji、组合字符；查看实际格数 | 正常字体 160×48；放不下则不超工作区。记录系统缩放、屏幕、实际渲染器与截图 |
| M02 | `text` 中拖选 `01234`，Ctrl+Shift+C；切到 `paste`，Ctrl+Shift+V；右键复制；再将右键改为复制并粘贴 | 复制内容精确；默认右键不向子程序发送粘贴。括号粘贴记录 `ESC[200~...ESC[201~`；更改模式后的行为分别记录 |
| M03 | `mouse` 中移动/点击/滚轮；再按 Shift 拖选并 Ctrl+Shift+C；也在 `alternate` 重复 | 普通操作产生 SGR 鼠标记录；Shift 选择本地可见字符，不被应用抢走；对应时间段无鼠标输入误送 |
| M04 | 在前三行，从第 2 列至第 6 列 Ctrl 拖出矩形，从四个方向各做一次；应用捕获时加 Shift | 三行复制为 `12345`、`b中éF`、`lmnop`，中间 CRLF；选择高亮只在矩形内，中文与组合字符完整 |
| M05 | 拖入生成的文件和目录，文件名包含空格、中文、单引号；检查当前/后台标签目标 | 引用后的路径落在正确标签。手工原生拖放与自动 WM_DROPFILES 证据分别记；应用接管行为单独观察 |
| M06 | 不带 `--tabs` 启动普通测试终端，用 Ctrl+Shift+T 新建两个不同内容的标签，标签栏四侧依次设置；悬停后台标签并让其输出 | 预览属于所指标签，能刷新，不切走当前标签；Ctrl+Tab/反向、中键关闭、关闭首标签不影响另一个。记录四侧画面 |
| M07 | 拖窗口边缘，最大化/恢复、全屏往返；输出中调整尺寸 | 行列随客户区变化；应用收到新尺寸；内容、滚动和光标位置正确；最后关闭无后台测试进程残留 |
| M08 | 用本机中文输入法实际输入、选择候选、取消、提交中文和 emoji；输入中调整字号；有第二屏则跨屏 | 候选/组合窗跟随光标；提交一次、不丢字；实际 DPI 与模拟 DPI 分别记录。不具备多屏条件就填未验证 |
| M09 | `text` 中 Ctrl+滚轮缩放；`mouse` 中普通滚轮、Ctrl+滚轮、Ctrl+Shift+滚轮对比；设置恢复字号键 | 本地缩放只在应触发时发生；应用捕获下需 Shift 强制缩放；恢复后字形和布局正确 |
| M10 | 设置声音模式，运行 `bell`；视觉模式再试；关闭响铃后再试 | 听到/看到预期提示；关闭后不响不闪。人工填写听感，API 成功不能代替听到 |
| M11 | Profile 中 Add 测试 profile；Edit 选择后更改字体、颜色、绑定与 Profile / Shell；Save & Apply 后用 `--profile` 重启；检查 Cancel；最后 Delete | 设置保存到当前 profile；临时 `-e` 不保存；Default 不可删除。pwsh / Windows PowerShell / BusyBox ash / Git Bash / WSL Bash 分别记录可用性与实际启动；缺装只记缺装 |
| M12 | 审阅两款隔离客户端图片测试回执和画面；需要物理键确认时在相同隔离 fixture 内重复 | Ctrl+V 与 Ctrl+Shift+V 的附件、生成图片 SHA/像素、关闭结果对应同一客户端。禁止把已有个人会话当测试对象 |

M06/M11 的普通 shell 窗口应单独从 `snapshot/dist/nemoterm.exe` 打开，使用测试目录与测试配置。
生成文本窗口内的新标签可能继承测试命令，不能共用同一个记录文件做独立标签证据。
真实客户端长期输出/滚动还需单独记录持续时间、应用版本、场景与峰值；短贴图用例不能证明长期负载。

先做 GDI；DX 做选择、缩放、标签、图片与候选窗复查，OpenGL 做切换/降级与关键画面观察。
DX 当前内存策略按用户已接受的范围记录；不把它重新塞回 GDI 的 20 MB 门槛。

## 交付记录与停止条件

`results.json` 保存自动结果；`attempts/<用例>-<次数>/output.log` 与 `research/`、`build/`
保留每次成功/失败的原始证据及哈希。`manual-results.json` 默认全部 `not_run`，实际操作后
填写 `passed` / `failed` / `not_run`、操作者、时间、观察和截图路径，不由脚本自动签字。
手工表面退出只记录 `needs-review`，不会自动生成“交互全部通过”的结论。

验收时核对精确 exe、实际字体/渲染器、原始输入/像素/退出证据和手工操作记录。
出现崩溃、漏字、错误粘贴、窗口失去响应、候选位置偏移即保留记录并停止相关组。
本套件准备阶段只做离线命令/快照/哈希验证；原生运行调度与手工表面还需要下次桌面测试验证。
