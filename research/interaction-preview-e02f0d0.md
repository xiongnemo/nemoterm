# 单文件交互记录 `e02f0d0`

[GitHub 托管构建](https://github.com/xiongnemo/nemoterm/actions/runs/44477059678/artifacts/14507241831)的 `nemoterm.exe` 为 4,855,808 字节，SHA-256 `be28e4e503383070855dac42d679c5427e224a68c3fb13195f7d2b820d0f2120`。源码 `e02f0d05638778ea3ea0881de5225c3dfa085523`。[完整回归](https://github.com/xiongnemo/nemoterm/actions/runs/44477059678)与[真实鼠标回放](https://github.com/xiongnemo/nemoterm/actions/runs/44477769731)分别保留。

[保持鼠标跟踪的独立回放](https://github.com/xiongnemo/nemoterm/actions/runs/44479519855)的六个交互用例全部通过。字被分栏截断或被滚走时的窗口用例 32/32、真实鼠标 4/4；保留字原有的 32+4 项也通过。[同图对照和原始记录](selection-discarded-scroll.md)。最初的整套回归使用了在切换阶段会关闭鼠标跟踪的测试脚本，其选区分组不能充当这一场景的验收。[修正后对同一 EXE 的全组重放](https://github.com/xiongnemo/nemoterm/actions/runs/44480195510)单独计分。本版仍有 [ReGIS 参考画面](regis-first-expose.md)的既有差异。

## pterm 与本版的 Win32 渲染和内存

[REA 对两个原始 PE 的解析](native-imports-pterm-e02f0d0.zip)：本机 Scoop pterm 0.85（SHA-256 `8580a3df4afe7696758c1cef43d0e88e3db5fd41c35c60166241aee72dd3ba3b`）的普通导入有 8 个 DLL、319 个入口，无延迟导入；可以看到 `CreateWindowExW` 和 GDI `ExtTextOutW`。本版单文件普通表有 81 个 DLL、672 个入口，延迟表为 `icu.dll` 的 11 个入口；还直接声明 `DWriteCreateFactory` 和 `D3D11CreateDevice`。两份表均完整解析，未见 WebView、Chromium、CEF 或 Electron 的导入。文件声明本身不能排除在运行中加载其他模块。

[同台 runner 的 10 次冷启动](pterm-discard-memory-e02f0d0.zip)（[工作流](https://github.com/xiongnemo/nemoterm/actions/runs/44477824923)）均成功。固定同一份 Codex、160×48、SarasaTermSC Nerd Light，配置按正序、反序各启动一次。下表取客户端回复后约三秒内各自前端工作集或提交量的中位数，单位为十进制 MB，只列 pterm 和默认单标签；独立窗口也有原始样本。

| 前端 | 私有工作集 | 总工作集 | 私有提交 |
|---|---:|---:|---:|
| pterm 0.85 | 3.748–3.781 | 21.811–22.606 | 4.444–4.481 |
| Nemoterm GDI 单标签 | 5.362–5.419 | 35.697–36.639 | 6.865–6.939 |
| Nemoterm DirectX 单标签 | 10.027–10.031 | 47.231–47.251 | 11.608–11.641 |

8 次 Nemoterm 快照都记录了前端模块和作业进程，受检的 WebView、Chromium 或 Electron 名称均未命中。GDI 模式的前端也映射了 `d3d11.dll` 和 `dxgi.dll`，模式标记仍为 GDI；不能仅凭 DLL 存在认定用了 GPU 渲染。DirectX 的两次单标签快照另有 `d3d10warp.dll`，这些托管测量不能直接预测另一台电脑的显卡驱动占用。源代码和压缩滚动历史等机制见 [pterm 研究记录](pterm-findings.md)。

## 客户端和交互

- [默认网格的 Codex、OpenCode、Claude](agent-grid-discard-e02f0d0.zip) 10/10；[30 项客户端检查](agent-cases-discard-e02f0d0.zip) 28/30。失败的是 Codex 在启动时通过窗口接口或真实键盘立即贴图，编辑器就绪后这两种输入都通过。[同一 EXE 的独立诊断](codex-bitmap-requests.md)记录了按键、Windows 索取位图和服务端收到正确像素的时点。
- [连续粘贴](paste-discard-e02f0d0.zip)中，接口和 Ctrl+Shift+V 均 4/4。[Unicode 投递](unicode-discard-e02f0d0.zip)本轮 5/5，包括独立对照。
- [WSL Vim](wsl-vim-discard-e02f0d0.zip)在两种 TERM 和 GDI、DirectX 的四种组合均完成普通应用鼠标、Shift 本地拖选、两次缩放、矩形选择和实际粘贴保存等六项检查。
- 原生测试覆盖了与[被丢弃的字](selection-discarded-scroll.md)相反的情形：屏幕上第一行滚入仍然存在的那一个历史槽后可以复制 `KEEP`。第二次滚动覆盖该槽才丢弃起点。中间提交 `209ad34` 的测试把视口移到了当前屏幕（实测 `disptop=0`），因此错误地取了 8 个字符；[原始失败日志](https://github.com/xiongnemo/nemoterm/actions/runs/44476801522/artifacts/14507645616)保留。本次定位到历史顶端并要求 `disptop=-1` 后，GitHub Windows 原生测试通过。

## 160×48 压力峰值

[GDI 六项](memory-gdi-discard-e02f0d0.zip)与[DirectX 六项](memory-directx-discard-e02f0d0.zip)均通过。每列独立取全部采样的最大值，单位为字节。两个渲染器的私有工作集最高值都出现在密集 Unicode 和 Kitty 图像同屏。20 MB 和 30 MB 目标按前端私有工作集验收，不含 shell、控制台宿主和客户端。

| 前端 | 私有工作集峰值 | 总工作集峰值 | 私有提交量峰值 |
|---|---:|---:|---:|
| GDI | 19,337,216 | 54,083,584 | 22,515,712 |
| DirectX | 28,749,824 | 71,933,952 | 32,055,296 |
