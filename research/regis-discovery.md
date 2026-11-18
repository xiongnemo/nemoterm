# 让应用在绘制前发现 ReGIS

以前，应用即使在 Nemoterm 上能画图，也可能根本不尝试：主设备属性（DA1）的功能列表只含 Sixel（4）和 ANSI 颜色（22），而 `CSI ? 3 ; 1 ; 0 S` 会回应 `CSI ? 3 ; 1 S`（未知项目）。[修复前的实际会话](regis-discovery-before-b7f4bfa.zip)来自 GitHub 托管 Windows 的 [44410983727](https://github.com/xiongnemo/nemoterm/actions/runs/44410983727)。GDI、DirectX、直接采集 GDI 桌面像素和请求 OpenGL（实际回退 GDI）四组都记录到同样的原始回复。客户端见不到 ReGIS 功能位，因此没有发送绘图指令。文件与 `b7f4bfa` 手测版的 SHA-256 一致。

[独立 XTerm 查询记录](regis-discovery-xterm.zip)来自 [44410985831](https://github.com/xiongnemo/nemoterm/actions/runs/44410985831)，制品 `14477336288`，SHA-256 `873bcd56b1dd5ab0fff77b39185632c6686459b9b94af369d276fd8646e3c839`。Ubuntu Runner 从先前保留的原始制品取出启用 ReGIS 的 XTerm 412，校验 SHA-256 后用两种画布大小分别运行。两个进程都声明功能位 3 和 4；读几何尺寸分别返回 160×120 和 800×480。项目 3 的设置、重置、读最大值均返回状态 3，未知操作返回状态 2。原来的无 ReGIS 构建仍是其他图形项目的对照。Nemoterm 保留自己的终端型号和其他功能位，不伪装成具有 XTerm 的全部选件。

`6ee2996` 的查询直接读取绘图使用的页面尺寸；终端窗口的行列数、字体像素和 Sixel 图像上限是独立的。原生窗口验收中，客户端只有先读到 ReGIS、Sixel 和有效画布才会继续：它按返回尺寸计算起点，画一条 17 像素绿线，核对位置应答，再重绘并查询，检查颜色和坐标是否仍然正确。

## 重绘与原始画面的差别

[修复前单独的逐帧核对](regis-discovery-before-repaint.json)读取 MSVC 制品 `14474178116` 的实际 RGB 哈希及差异 PNG，仅在原始参考裁剪哈希与已记录的实际 RGB 哈希相等时才用参考像素重建无差异帧。用[比对脚本](../scripts/compare-regis-repaint-evidence.py)将相同输入按步骤对齐，并验证两份 XTerm 参考的回复字节一致；每个产品图像又与原始 RGB 哈希校验。这里只比较已保存的像素，不模拟桌面重绘。在 131 帧 × 两种分包方式中，5 帧与旧的首次显示不同：向上滚动、两次向下滚动、换行滚动和共享调色板改色。这 **5 帧均与另一份 XTerm 的强制重绘图像一致**。相反，`erase-line` 第 1、2 步均与最初画面相同，却各与强制重绘图相差 101 像素：Nemoterm 擦掉的线在 XTerm 重绘时重新出现。每种分包分别是原始对照 **126/131**、重绘对照 **129/131**。两套参考的呈现历史不同；原始失败保留。
