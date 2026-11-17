# 远程测试与交互验收

所有自动测试在 GitHub-hosted runner 上执行。开发电脑只编辑源码、提交、调度 Actions 和下载证据；不需要启动测试终端、接管焦点或修改本机剪贴板。

## 入口

完整回归（包含重新构建）：

```powershell
gh workflow run ci.yml --ref <branch> -f scope=full
```

`Test and build` 汇总 Linux ASan/UBSan、C/C++ 单元测试、MSVC 渲染诊断、MinGW 原生协议和像素测试、单 EXE 完整套件、profile 持久化、DPI/双语界面，以及下表的 38 项检查（26 项交互、12 项完整 Sarasa 网格负载）。单 EXE、DPI 和交互任务共用这次 source-host 构建的准确 EXE，并校验来源提交、大小及 SHA-256。

只回放测试脚本，不重复编译：

```powershell
gh workflow run font-zoom-replay.yml --ref <branch> -f suite=interaction -f source_run=<run-id> -f source_commit=<40-character-sha>
```

`interaction` 可额外传 `-f 'groups=["shells","clipboard"]'` 只重跑指定组；留空执行全部。

`suite` 还可选 `single`、`dpi`、`font-bell`、`ui-regression`、`shell-lifetime`。交互、single、DPI 和 shell-lifetime 回放允许源 run 的其他测试失败，但要求 source-host 构建成功；生产代码或构建配方与该产物不一致就拒绝回放。查看结果用 `gh run view <run-id>`；下载证据用 `gh run download <run-id> --dir <new-directory>`。

`shell-lifetime` 在同一个准确 EXE 上交替执行 12 次普通 Git Bash 复制/关闭和 12 次带进程观察的复制/关闭，随后执行 2 次正常连接对照和 4 次受控的延迟客户端检查。完整 CI 也会自动调用此工作流。每次保留独立结果；原先的 3 秒回收门槛不变。失败后额外观察 12 秒并采集遗留进程的命令行、线程和转储，只用于诊断，不能把失败改成通过。已发现的关闭残留及修复验证见 [Git Bash 关闭调查](../research/git-bash-close-race.md) 和 [关闭后连接检查](../research/closed-console-connections.md)。

`single-exe.yml` 保留独立手动入口，正常 push/PR 由完整 CI 调用，避免重复构建。上游协议对照与内存/句柄诊断继续使用仓库中已有的专用远程工作流，不需要本机补跑。

## 交互矩阵

每组使用独立 Windows 2025 runner，最多同时运行五组；组内顺序执行并保留各自失败，不因另一组失败取消测试。`scripts/interaction_acceptance.py run` 拒绝本机及 self-hosted runner；`plan` 和 `prepare` 只处理清单和文件。

| 组 | 用例数 | 覆盖 |
| --- | ---: | --- |
| input | 2 | byte/ReadConsoleW、中文/emoji、IMM、模拟 DPI 与组合窗位置 |
| selection | 3 | 默认/自定义 bindings，GDI/DX 矩形、宽字符、Shift 选择 |
| clipboard | 2 | GDI/DX 文件/目录拖放，路径引用、应用接管与文本/图片优先级 |
| agents | 2 | 固定版本 Codex/OpenCode 的 Ctrl+V、Ctrl+Shift+V 图片附件与精确像素 |
| rendering | 3 | 实际 GDI 客户区捕获、三种渲染器、字号缩放/恢复 |
| mouse | 1 | 鼠标协议字节、按键、滚轮和坐标 |
| tabs | 8 | 四侧标签栏/预览及四侧窗口缩放、会话与关闭回收 |
| settings | 2 | 独立窗口和标签宿主的 profile CRUD、设置保存/重载 |
| shells | 1 | pwsh、Windows PowerShell、BusyBox ash、Git Bash、WSL Bash、cmd |
| bell | 2 | 声音 API、视觉响铃/恢复及关闭模式 |
| memory-gdi | 6 | 完整 160×48 Sarasa 网格：文本、PNG、GIF、Kitty、压缩 Kitty、Unicode 图片的内存/像素/关闭回收 |
| memory-directx | 6 | 相同六类负载，要求实际使用 DirectX，拒绝静默回退 |

Sarasa Light 从固定 v2.3.1 压缩包安装，校验下载及实际字体名称，禁止静默换成替代字体。BusyBox 从固定源码提交交叉编译，记录成品 SHA-256 并附源码和许可证；Codex/OpenCode 使用 npm lock 文件固定实际原生客户端，保存客户端 EXE 哈希。WSL 在需要的组内安装 Ubuntu 24.04/WSL 1。shell 组要求六种 shell 全部检测成功并实际启动，不把“未安装”当通过。

客户端 fixture 使用临时 HOME/配置、权限拒绝、关闭工具/插件/更新及固定回环响应服务；不使用个人账号、历史会话或真实模型调用。图片验证使用生成的 32×16 棋盘图，核对请求中的图片像素。

## 证据与判定

每组总会尝试上传 `interaction-<group>-<run>-<attempt>`，内容包括：

- `SOURCE-HOST.json`：待测 EXE 来源与哈希。
- `environment.json`：runner 镜像、字体和下载依赖的身份。
- `identity.json`、`plan.json`、`results.json`：脚本提交、客户端/文件哈希、用例及状态。
- 每次尝试的 `output.log`、`research/`、`build/`：截图、输入回执、像素/资源数据和失败证据。

超时、断言失败或强制回收遗留进程均判失败。重跑创建新的 run/attempt，不覆盖旧失败。内存目标沿用既有 GDI 与可选 GPU 模式约定，不为了 runner 通过而放宽。

`memory-*` 组只在托管 Runner 上选择其显卡驱动列出的较大显示模式，使用实际 100% DPI、固定 Sarasa Light 和显式 `--require-grid`。初始终端必须确实为 160×48 字符；被屏幕裁小就失败。记录实际工作区、字体、渲染器、网格和三项内存指标；先采样内存，再执行截图/注入检查，并在结束后恢复显示模式。可用 `-f 'groups=["memory-gdi","memory-directx"]'` 单独回放。原有 Consolas 小网格回归仍保留，不能替代这些完整网格负载。

真实 Windows DPI 的 100/125/150/175/200% 冷启动和动态切换由独立 [DPI 工作流](DPI-CI.md) 覆盖；交互组的模拟 DPI 不替代它。

自动测试可以验证系统声音 API，但不能证明用户听到声音；注入输入不能证明某款物理鼠标、真实第三方输入法候选窗或多显示器驱动表现。报告如实记录这些边界与 runner 上可用的 IME，不自动签署人工验收。它们不构成本机测试前置条件。

## 历史证据

迁移前的内存、桌面中断和输入法问题保留在 [历史本机记录](../research/d3d11-local-f3b5b65.md) 及 `research/interaction-input-dpi-f3b5b65.zip`。旧版的通过记录不能套用到新 EXE；本轮迁移结果见 [远程迁移记录](../research/remote-test-migration.md)。
