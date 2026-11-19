# 当前测试版与待审阅材料

本目录只留当前工作的记录。测试所读取的固定输入另存于 [testdata/upstream](../testdata/upstream)；旧版截图、运行日志和原始失败均可从[清理前的提交](https://github.com/xiongnemo/nemoterm/tree/fca0e61388f99dd460811c231950d5d7c19a775e/research)查阅。

- [当前测试版的跨标签修复、画面和内存记录](tab-drag-release.md)。`dist/nemoterm.exe` 对应 `6a2dc83`。其[完整交互回执](interaction-report-44525718005.zip)覆盖 13 组、81/81；报告只对所列交互负责。
- [pterm 为什么轻量](pterm-findings.md)：指定的本机 0.85 二进制、REA 静态导入、私有工作集与总工作集的区别，以及该推论的边界。
- 待审阅的兼容性取舍：[Codex 启动草稿和图片粘贴](codex-bitmap-requests.md)、[宽字在行尾移动时的三个 XTerm 差异](column-edge-integrity.md)、[ReGIS 图形重绘前后的实际画面](regis-presented-pairs.md)。
