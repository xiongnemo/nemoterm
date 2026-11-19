# 从资源管理器贴图片，以及启动时的一次字符错位

受测产品是 `dist/nemoterm.exe` 对应的 `7ec651d`，SHA-256 `c149c2bc3a3a2e0d2594ae2a239520af15a47bbb5c4d49c4daae3dc998bf64ba`；真实客户端是 Codex 0.167.0，SHA-256 `edfdd48f8b458af0906e507b4cb05217b326c3d6e515e9f024e05e3b8d650f70`。使用 SarasaTermSC Nerd Light、隔离配置与回环服务。以下都是 GitHub-hosted Windows 记录。

## 复制文件不等于复制位图

这次生成 32×16 PNG，文件名含中文和空格。剪贴板只提供资源管理器的文件列表 `CF_HDROP`，没有位图或备用文本。检查依次要求：应用显示附件、服务端收到一张图、所有像素正确。屏幕上只有路径不算成功。普通 Ctrl+V 和默认的终端粘贴 Ctrl+Shift+V 分别记录。

| 时点／输入途径 | [第一次（d457d34）](../testdata/upstream/codex-file-clipboard-d457d34.zip) | [修正重绘判定后（22ed829）](../testdata/upstream/codex-file-clipboard-22ed829.zip) |
| --- | --- | --- |
| 首次看到输入文字，窗口接口 | 0/2 | 0/2 |
| 首次看到输入文字，Windows 实按 | 0/2 | 0/2 |
| 客户端报告 idle 后，窗口接口 | 2/2 | 2/2 |
| 客户端报告 idle 后，Windows 实按 | Ctrl+Shift+V 通过；Ctrl+V 未到发键步骤 | Ctrl+V 通过；Ctrl+Shift+V 未到发键步骤 |

两个启动回放中，Ctrl+Shift+V 均把带引号的路径完整粘入，未出现附件。[实际窗口](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/file-paste-literal-7ec651d.png)。就绪阶段的已通过场景确实收到了 PNG；两次实按分组的未到达场景仍计为失败，没有拼成一次 2/2。位图单独计分，见[同一 EXE 的位图回放](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/claude-writer-order.md#codex-贴图时机)。

这与固定版本的客户端实现吻合：启动窗格[显式选择纯文本配置](https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/tui/src/startup_draft.rs#L526-L530)，其中 [image_paste_enabled 为 false](https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/tui/src/bottom_pane/chat_composer.rs#L614-L622)。[图片路径转换](https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/tui/src/bottom_pane/chat_composer/paste_input.rs#L195-L205)也检查该开关。把剪贴板位图另存成文件再重发路径，并不能让这个启动窗格附图。

## 一个测量错误，一次真实错位

- **第一次，未发 Ctrl+V。** 客户端在第 27 行写出 `NEMOTERM`，报告 idle 后从第 11 列接着画 `_CODEX_IMAGE_CTRL_V`。屏幕上的完整标记正确；测试要求第二次写出整串，错误地报告了就绪超时。现在保留原整串判定，也接受经验证的分段绘制：原始输出中的前缀和后缀必须写在同一行的准确列，最终可见的完整提示必须唯一。新回放的四台 runner 均通过旧记录和错误行、列、后缀、过期状态等反例；新实按场景确实走到了该分支。
- **第二次，未发 Ctrl+Shift+V。** 此次不是重绘判定错误：屏幕上真的成了 `NEMEOTERM_CODEX_IMAG_CTRL_SHIFT_V`；原文是 `NEMOTERM_CODEX_IMAGE_CTRL_SHIFT_V`。两串都是 33 字符，`IMAGE` 末尾的 `E` 跑到了第四位。[原始截图](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/draft-transposed-7ec651d.png)与客户端输出一致。图片粘贴手势还没有发出，也没有提交这一稿，不能把这个截图描述成服务端已经收到了错序文本。

## 输入次序在哪一层发生变化？

| 检查 | 方法 | 结果 |
| --- | --- | --- |
| [Nemoterm → 原生控制台接收器](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/console-draft-order-7ec651d.zip) | [远程回放](https://github.com/xiongnemo/nemoterm/actions/runs/44462423613)使用错位现场在 OSC 10/11 前的原始 VT。在无查询、查询前、同时启动和读到两项回复后粘贴，读取完整 `ReadConsoleInputW` 记录和结尾屏障。GDI、DirectX 各四项。 | **8/8**。每项收到 33 个原样字符，无多余输入；六项有查询的场景各收到两份完整颜色回复。并发场景只证明本次调度。 |
| [Nemoterm → 真实 Codex → 服务端](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/codex-draft-product-b79c417.zip) | [远程回放](https://github.com/xiongnemo/nemoterm/actions/runs/44463065855)在 GDI、DirectX 的首次提示及完成一个回复后，各开三次新会话。其中两次用窗口接口粘贴，一次真实按 Ctrl+Shift+V 粘贴 Unicode 文本。 | **12/12**。提交前截图有原文，服务端均恰好收到一份正确的 33 字符文本。六次首次输入前的输出快照都没有 idle。 |
| [独立控制台 → 同版 Codex → 服务端](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/codex-draft-reference-75248bb.zip) | [远程对照](https://github.com/xiongnemo/nemoterm/actions/runs/44462812906)不启动 Nemoterm；系统 ConPTY、WinPTY 的首次提示及完成一轮回复后，各开三次新会话。对本会话的控制台一次写入整段原生按键记录。 | **12/12**。原生屏幕和服务端消息均为原文。这条输入路径与 Nemoterm 管道不同，不能单凭它归因。 |

两个真实客户端回放均在给定观察时间后直接提交，没有以“已经显示正确字符串”为提交前提。原始错位仍未定位；以上阴性对照不意味着它已修复。测试入口见[远程交互说明](../docs/INTERACTION_ACCEPTANCE.md)。
