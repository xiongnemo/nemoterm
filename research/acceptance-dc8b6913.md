# Windows x64 试用版 `dc8b6913`：主屏折行选区

[单文件 Actions 产物](https://github.com/xiongnemo/nemoterm/actions/runs/44632752976/artifacts/14583162547)内的 `nemoterm.exe` 为 4,923,904 字节，SHA-256 `d6780333dcf89afa73659e490523aef36f948537df456d9d06da7dc6c775c6a2`。新行为是：窗口变窄或再次加宽时，Shift 选区跟随发生软折行的字形。[之前/之后的窗口截图、右键与剪贴板](selection-reflow.md)。以下均使用这份 EXE 或明确列出的原版 pterm，不启动开发电脑上的终端。

| 160×48，SarasaTermSC Nerd Light | 前端私有工作集峰值 | 总工作集峰值 | 私有提交峰值 |
| --- | ---: | ---: | ---: |
| 原版 pterm：首次输入和 24 轮 Codex 追问 | 3,788,800 | 22,773,760 | 4,460,544 |
| Nemoterm GDI：同一对话 | 5,681,152 | 37,015,552 | 7,053,312 |
| Nemoterm DirectX：同一对话 | 9,986,048 | 47,374,336 | 11,591,680 |
| GDI：六种满屏负载 | **19,087,360** | 53,948,416 | 22,855,680 |
| DirectX：六种满屏负载 | **29,151,232** | 74,485,760 | 32,649,216 |

单位为字节，每列独立取峰值。前两种 Nemoterm 渲染器在六种压力负载下均符合各自的私有工作集门槛；总工作集单列。[同机对话](https://github.com/xiongnemo/nemoterm/actions/runs/44633969913/artifacts/14581799174)中每个窗口处理 25 条请求并自然退出，所抽查的模块和子进程中未观察到 WebView 运行时。REA 静态检查该 EXE 为 x86-64 PE32+、没有 CLI 数据目录（证据 `ev_dd699ee4d318281e228b41d9a320a384cf32332061e002dc0554db2e9b1357c7`）；这本身不能证明未加载 WebView。

[原始完整交互](https://github.com/xiongnemo/nemoterm/actions/runs/44632752976/artifacts/14584635604) **79/81**。Codex 刚显示输入文字时，窗口按键和真实键盘两组都没有在规定时间内显示附件。等正式输入框就绪，同样两种按键途径各自的 Ctrl+V、Ctrl+Shift+V 均通过。两组首次失败仍按失败计分。[原版 pterm 的独立对照](codex-bitmap-requests.md)。同一份 EXE 在两个 TERM 和两个渲染器上的真实 Vim 与 tmux 内 Vim 是 8/8；WSL 的颜色及 Sixel 窗口检查各为 2/2。

首轮 agent 及满屏 agent 作业记录 `fixture_dirty=true`。这两个工作区没有记录具体路径。已逐项核对，两组各 507 个冻结文件、运行器和辅助脚本的 SHA-256 与同一提交的干净内存作业全部相同，三个客户端也分别记录了可执行文件摘要。原始 10 个满屏选区用例均通过；此处保留原工作区状态。后续回放把 npm 安装移入 runner 临时目录，在冻结前强制工作区干净，并保存两个依赖清单的摘要。

[本次完整交互汇总、内存、agent 和 WSL 原始制品](acceptance-dc8b6913.zip)内含未修改的 GitHub 下载 ZIP，来源与散列见 `sources.json`，逐场景峰值见 `memory.json`。用[离线核对脚本](../scripts/review-frontend-memory.py)可从每个样本重算压力峰值。协议差异仍单列：[ReGIS 的首次呈现](regis-presented-pairs.md)、[XTerm 412 的三处宽字符单元格](column-edge-integrity.md)和 [WSL1 的行读取、退出期限](wsl-profile.md)。

[干净工作区回放](https://github.com/xiongnemo/nemoterm/actions/runs/44637214779)另外运行 40 项：真实 Codex、Claude Code 和 OpenCode 满屏拖选 **10/10**；普通 agent 交互 **28/30**。窗口和真实键盘的就绪贴图各有两种绑定，四次都通过。启动时真实键盘的 Ctrl+Shift+V 首次成功，而 Ctrl+V 仍失败；窗口按键的两个首次手势也都失败，故这两个用例在原分组定义下仍为失败。两份身份记录均为干净状态，三个客户端 EXE 的散列与首轮相同，六份包清单的原始散列均符合该提交 Windows 工作副本的 CRLF 字节。[冻结身份、逐项回执与小计](agent-clean-dc8b6913.zip)。本次 38/40 是子集回放，不覆盖或替换原始 79/81。[最初一次新夹具调度](https://github.com/xiongnemo/nemoterm/actions/runs/44637024721)因为协调器的测试对象缺少新选项而停止，未运行真实客户端；修正后的协调器也验证了工作区有改动时拒绝启动并留下原因。
