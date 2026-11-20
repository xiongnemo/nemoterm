# 程序要求改变行列数时，保留仍在屏幕上的选区

在程序已接管鼠标的窗口中，按住 Shift 选取 `A中Z`。旧版在收到三种 DEC 页面尺寸请求时会立即清除选区：即使程序要求的就是现有尺寸，或者 profile 已禁止程序改窗口大小，文字仍在，选区却消失。右键本该复制这些字，结果变成了发送鼠标事件给程序。`226ddd98` 让实际发生的尺寸变化决定选区结果；缩窄后原先按住的字真的消失时，仍然取消这次拖选。

| 同一组实际窗口操作 | GDI | DirectX |
| --- | ---: | ---: |
| [修复前 `78b18ac0`](https://github.com/xiongnemo/nemoterm/actions/runs/44686905612) | 2/14 | 2/14 |
| [修复后 `226ddd98`](https://github.com/xiongnemo/nemoterm/actions/runs/44687000276) | 14/14 | 14/14 |

两版所有用例的窗口尺寸、子程序读回的行列数和 `CSI 18 t` 应答都正确。区别在选区：旧版有 12 次仍应保留的高亮消失、复制未更新剪贴板、普通右键发给子程序。修复后，按住时与松手后、标签窗口与独立窗口、允许与拒绝改尺寸的结果均符合预期；右缘被裁掉的字符仍不高亮，子程序收到下一次右键的按下和松开。两种渲染器各有 14 个独立窗口，测试字体为 SarasaTermSC Nerd Light。

[完整原始制品及离线复核结果](selection-page-size.zip)内含两版各两份 Windows 制品、原版 XTerm 制品及 GitHub SHA-256、制品编号和运行身份。解包后可用 `python scripts/review-page-size-selection.py before-gdi.zip before-directx.zip` 复核旧版（预期 4/28，非零退出），将 `before` 换成 `after` 复核修复版（28/28）。脚本读取原始截图、两种复制操作和子进程收到的字节，不启动产品。修复版 EXE 为 4,947,456 字节，SHA-256 `bd8cf49fe772b29d9a22789c330ce57693d3a088e192532225af4d2f5f09e934`。更早的[第一次基线运行](https://github.com/xiongnemo/nemoterm/actions/runs/44686452058)因测试脚本缺少 Pillow 未进入这组操作，未计入分母。

[原版 XTerm 412 的六个独立窗口](https://github.com/xiongnemo/nemoterm/actions/runs/44687309026)回答了另一个问题：哪些请求会改变它的实际网格？起始均为 80×24。它接受本次测试的 28、32 行请求和 DECSNLS 的 18 行；DECSCPP 请求 86、72 列时保持 80 列，请求 132 列时才切换到 132 列，之后可以切回 80 列。六组中 `A中Z` 的四格校验值均保持一致。单独禁止其 `SetWinSizeChars` 没有改变上述 DEC 命令的结果。Nemoterm 当前允许这组 86、72 列请求，并遵守自己的禁止远程调整设置。这是实际协议差异，28/28 的选区测试不代表列宽策略与 XTerm 完全相同。
