# 右键复制后，从同一位置重新 Shift 拖选

对照手势在托管 Windows 的右侧标签、DirectX 和 SarasaTermSC Nerd Light 下进行。子程序启用了鼠标跟踪。在 `|ABCDE|` 上按住 Shift 从 B 拖到 C，右键复制，再回到 B 开始第二次选择。整个过程落在 Windows 的 500 毫秒双击间隔内。独立的第二次拖选应该仍然只复制 `BC`；没有中间右键的真正双击应该选中单词 `ABCDE`。

| 原始可执行文件 | 首次右键复制 | 回到原处再次拖选 | 两次左键按下间隔上界 | 按住不动时的模式查询 |
| --- | --- | --- | ---: | --- |
| [旧单文件 `355c73f8`](https://github.com/xiongnemo/nemoterm/actions/runs/44793137815/artifacts/14657368194) | `BC` | `ABCDE`（错误） | 63 ms | 松手后才收到应答 |
| [原超时的 MinGW 文件](https://github.com/xiongnemo/nemoterm/actions/runs/44794111685/artifacts/14657038538) | `BC` | `ABCDE`（错误） | 62 ms | 松手后才收到应答 |
| [修复后单文件 `ba16d56b`](https://github.com/xiongnemo/nemoterm/actions/runs/44793711901/artifacts/14657243031) | `BC` | `BC`（正确） | 62 ms | 按住不动时已收到完整应答 |

两份旧 EXE 都通过了真正双击的对照。以前，终端在右键复制时直接返回，没有清掉上一次左键记录，于是第二次独立按下被当成双击选词。选词期间冻结屏幕是已有行为；它也会推迟应用查询的应答。`ba16d56b` 在消耗右键复制或菜单动作时结束上一次点击计数。

早期完整回归中的一次 8 秒超时发生在同类手势后，但当时未保存足以确定点击类型的记录。以上两次复现证明该缺陷存在，不能倒推当时一定只有这个原因。以后发生超时时，测试会分别保存松手前后的应用回执和终端解析日志。

新版真正的双击间隔上界为 63 ms，仍选中 `ABCDE`。四边标签各两张的轮廓截图与旧版逐像素一致；四边的鼠标预览、切换、复制，以及 20 项中键手势均通过。

[这份 EXE 的右侧 DirectX 完整选区回放](https://github.com/xiongnemo/nemoterm/actions/runs/44794676564/artifacts/14657638014)通过：7 个屏幕切换和 4 个拖动中切换场景均通过，对原始 15 张截图另行逐格核对了高亮。

[下载 `ba16d56b` 单文件](https://github.com/xiongnemo/nemoterm/actions/runs/44793711901/artifacts/14657592423)，4,942,336 字节，SHA-256 `b0b03507848b437aced6a326be2f2452035af53e16104234ba59e5ef984e3db8`。[保留的三份实际手势回执、15 张原图与构建身份](right-copy-ba16d56b.zip)。[此提交的全量测试](https://github.com/xiongnemo/nemoterm/actions/runs/44793711901)与这次专项验收分开记录。
