# 同一段输入：XTerm 和实际 Windows 窗口在重绘前后显示什么

[Windows 托管回放](https://github.com/xiongnemo/nemoterm/actions/runs/44484314787)的 10 个终点各用一个新进程。受测程序是 `e02f0d0`，EXE SHA-256 `be28e4e503383070855dac42d679c5427e224a68c3fb13195f7d2b820d0f2120`。固定 40×12 字符、每格 6×13 像素（先问实际终端确认），装载 SarasaTermSC Nerd Light。向子进程送出[原始 XTerm 参考](regis-first-expose.md)中的完整字节，验证每一步的回复，再用窗口自己的 DC 采集 160×120 图像区域，不从桌面取图或要求窗口为截图重新绘制。每步记录应答后约 250 毫秒内的像素采样，最后一次才强制重绘。这里的“重绘前”是重绘请求之前已经显示的画面，不是对显示刷新周期的测量。

| 终点 | 两个程序重绘前画面的差异（像素） | 都重绘后画面的差异（像素） |
| --- | ---: | ---: |
| 向上滚屏，随后查询画笔位置 | 101 | 0 |
| 向下滚屏；以及滚屏后再查询（两个终点） | 各 303 | 各 0 |
| 换行滚屏后查询 | 202 | 0 |
| 共享 Sixel；ReGIS 将色号 3 改为红色 | 600 | 0 |
| 擦行；以及擦行后再查询（两个终点） | 各 0 | 各 101 |

Windows 在以上七个终点的重绘前后自身均为零差异。XTerm 在两个擦行场景重绘后又显示了已擦掉的线。另有两个几何对照全像素相同；文字对照在各自窗口确实可见且重绘后不变。两种字体的文字像素有 235 个不同，记录保留，不以字形相同作为跨字体判据。10 个进程全部自然退出，没有截图或收敛错误。**三项对照通过、七项历史像素比较失败**，这些结果不替代原有组件回归。

**发现另一处启动差异。** 在共享色表场景的上一步，两端都没有收到过硬重置，也没有给色号 3 赋过值。Windows 画出 100×6 的绿色块 `#33CC33`，XTerm 同一区域全黑。固定组件测试原先人为预填了黑色，因此没暴露这一差别。[首次修复](https://github.com/xiongnemo/nemoterm/commit/da302b9)让新终端的共享色表从不透明黑色开始；模型色表继续用于私有图片及硬重置后的首次共享图片。不能用这个更正宣称滚屏、擦行或后续调色的历史画面也已一致。

[10 份原始制品](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-presented-pairs-e02f0d0.zip)包含未修改的 GitHub 下载 ZIP、每份的 ID 和 SHA-256、窗口完整截图和每次采集的裁剪摘要。外层 ZIP SHA-256 为 `0bce69d2d7216f6840eb37316760aaa162167db445c43aacc60c04988afc5114`。仅覆盖实际 GDI 与整段写入，不能外推到 GPU 或逐字节输入的 Windows 呈现。

[相同输入在修复后 `6bed777` 的回放](https://github.com/xiongnemo/nemoterm/actions/runs/44486931747)中，这个首次取色步骤由 600 个像素不同变为 0，而同一场景的改红步骤仍是 600。其余九个终点的逐步差异数全部未变，历史回放仍只有三项对照通过。[新 EXE 的十份制品](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-presented-pairs-6bed777.zip)，SHA-256 `3441313638664e463973be65081fede985133a084a1dade32ebcb1629d51b5bf`。

[共享图形色表的七组完整前后对照](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-bank-start.md)列出初始、软重置及硬重置时的实际色值。
