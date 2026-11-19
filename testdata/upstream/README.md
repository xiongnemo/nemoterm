# 固定回放输入

这里是远程 CI 和参考数据生成器实际读取的输入。保留原始归档、上游输出与校验清单；其中写有 `research/` 的历史路径属于采集记录，不能随目录迁移而改写。产生的新截图与回执仍由各作业写入其工作目录并上传为 GitHub Actions 产物。

`xterm412-scrollback-modes.zip` 是[远程采集 44551898895](https://github.com/xiongnemo/nemoterm/actions/runs/44551898895)的原始制品 `14542253715`，SHA-256 `c36021bb9f8a597e6fe8f7eb0fadea0f9a444c75a58d03682006d97130d53895`。XTerm 源码固定为 `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`。四个独立窗口分别设置 `scrollTtyOutput` 和 `scrollKey`，各自保留启动后的 18 段输入和逐字节应答；每段都查询 1010、1011 两个模式。Windows 回放按输入内容核对，不从产品结果反推参考值。
