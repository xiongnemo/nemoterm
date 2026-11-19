# `6072ebc9` 候选：选区、粘贴与内存

[这次完整 CI](https://github.com/xiongnemo/nemoterm/actions/runs/44595195309)的交互汇总为 **80/81**。精确 EXE 的 SHA-256 为 `375390d0c4fbc1acdd2e60fca087800b46a97f1898a4105aeb1155bd4265ad1c`，4,862,976 字节。[单文件构建制品](https://github.com/xiongnemo/nemoterm/actions/runs/44595195309/artifacts/14564444271)含 EXE 和构建清单。此候选与 README 首选测试版分别列出。

| 前端进程的采样峰值，十进制 MB | 私有工作集 | 总工作集 | 私有提交量 |
| --- | ---: | ---: | ---: |
| 原版 pterm 0.85，24 轮 Codex | 3.77 | 22.68 | 4.46 |
| Nemoterm GDI，24 轮 Codex | 5.73 | 37.09 | 7.11 |
| Nemoterm DirectX，24 轮 Codex | 10.03 | 47.39 | 11.67 |
| Nemoterm GDI，六种 160×48 满屏压力场景 | 19.28 | 54.08 | 23.01 |
| Nemoterm DirectX，同样六种场景 | 28.98 | 74.27 | 33.46 |

[同机多轮对照](https://github.com/xiongnemo/nemoterm/actions/runs/44596590521)：三份窗口分别收到首次回复及 24 个不同提示的回复，逐轮核对屏幕，每份均收到 25 个聊天请求并自然退出。pterm 的散列与本机 Scoop 0.85 相同。加载模块和子进程采样中均没有检测到浏览器运行时；[REA 的普通及延迟导入表](selection-height-after-6072ebc9.zip)与上一测试版的 684 项声明相同。上述内存数字只统计前端，不把 shell、Codex 或控制台宿主加进来。

只改变窗口高度时，[GDI / DirectX 的选区从 2/8 提高到 8/8](selection-height.md)。唯一未通过的交互项是 `agents/agent-image-codex` 的窗口接口 `Ctrl+V`：发键前确实还没有 Codex idle 信号，20 秒内没有看见附件，因而没有发送这一条，不能称作服务端收到了零图提交。就绪后，窗口接口和实际键盘的两种快捷键都在聊天请求中送到了正确图片；同一轮的实际键盘早发两种快捷键也都成功。[该候选的记录、实际模块采样、位图按键独立对照和失败窗口](acceptance-6072ebc9.zip)。先前对原版 pterm 的[真实窗口测试](codex-bitmap-requests.md)也曾复现早发失效。

**Windows 引用粘贴和窗口退出是两个结果。** 原 CI 中 GDI 的自定义 `^]` 窗口超出原定 10 秒退出期限。离线读取两种 renderer 的原始管道记录，与固定 XTerm 412 参考及实际 `ReadConsoleW` 输入独立比对，六组共 114/114 个阶段正确；原作业仍然失败。带有退出里程碑的[首次回放](https://github.com/xiongnemo/nemoterm/actions/runs/44598533410)在另一个 GDI 窗口再次超时：子程序约 32 毫秒内已完成控制台设置还原，超过 10 秒后其作业只剩前端；查询到一个未退出的线程及隐藏窗口。快照给出了线程入口，没有给出当时的执行栈，不能据此推定阻塞函数或原因。

[分别使用和不使用管道观察器的成对回放](https://github.com/xiongnemo/nemoterm/actions/runs/44599360475)为每种 renderer 和三种剪贴板设置各开两个窗口：12/12 自然退出，发出停止请求到观测到退出为 53–500 毫秒。带观察器的 114 个阶段核对了原始管道和子程序输入，不带观察器的另外 114 个阶段只核对子程序输入和模式回复。本轮没有超时，所以没有采集到超时调用栈，**尚未定位两次早期超时的原因**。[三次运行的原始制品](quoted-paste-exit-6072ebc9.zip)。测试期限、原始失败以及对启动早期粘贴的要求均未更改。
