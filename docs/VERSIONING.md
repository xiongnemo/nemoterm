# 版本号与发布

格式：

```text
v{主版本}.{次版本}.{补丁}-{分支}-{提交前 12 位}[-dirty]
```

- **补丁号自己往上加**：从最近的一个 `vX.Y.Z` 标签开始，往后每多一个提交，补丁号加一。`v0.0.1` 之后的第三个提交就是 `v0.0.4-main-<提交>`。补丁号从来不用手改。
- **打了标签的提交就是那个版本**：在一个 `vX.Y.Z` 标签所在的提交上、没有未提交的改动时，版本就是 `v0.0.1` 本身，不带分支和提交。
- **还没有任何标签时**是 `v0.0.0-<分支>-<提交>`，表示还没有版本线可数，这种版本不会发布。浅克隆看不到标签，也会得到它，所以要发布的构建都用完整历史检出（`fetch-depth: 0`）。
- **改次版本或主版本**：在想要的提交上打一个新的 `vX.Y.0` 标签并推上去，之后的提交从它往上数。
- 分支名里版本号放不下的字符换成 `-`；有未提交的改动时加 `-dirty`。
- 版本由 [`scripts/version.ps1`](../scripts/version.ps1) 从 git 算出。[`scripts/build-single-exe.ps1`](../scripts/build-single-exe.ps1) 在动任何文件之前调用它，经 CMake 的 `NEMOTERM_VERSION` 生成 `nemoterm-version.h`。它出现在两处：「关于」窗口，以及 `nemoterm.exe` 文件属性里的产品版本（VERSIONINFO）。不经这个脚本的 CMake 构建（例如组件测试）是 `v0.0.0-unversioned`。
- 文件属性里的标记和 GitHub 上的一致：只有 `vX.Y.0` 标签本身是正式版；其他标签（如 `v0.0.1`）和带分支的版本标为预发布（VS_FF_PRERELEASE）；有未提交改动或没给版本的构建标为私有构建。`v0.0.1` 的 exe 是在这条规则之前编的，文件属性里没有预发布标记。

## 两种标签

- `vX.Y.Z`：基准标签，**只由项目所有者手动推**。它决定版本线。
- `vX.Y.Z-分支-提交`：预发布的标记，由发布流程自动创建，**永远不会**成为基准（算版本时排除带 `-` 的标签）。

## 发布

[`.github/workflows/release.yml`](../.github/workflows/release.yml) 在每次 push 的 Test and build 跑完后运行：

- **main 上每个编出了 exe 的提交**都发布成一个 GitHub 预发布，例如 `v0.0.5-main-0123456789ab`，标签由流程创建。
- **推一个 `vX.Y.Z` 标签**，等这个标签自己的 Test and build 编出 exe 后发布这个版本：补丁号是 0 的（如 `v0.1.0`）是正式发布，会成为 Latest；其他的（如起点 `v0.0.1`）也是预发布。
- **发布的是 CI 编出的那三个 exe**：x64、x86、arm64 各一个，从那次运行的 `source-host` 和 `source-host-arch` 产物下载，不重新编译。x86 在 x64 机器上编，arm64 在 Arm 机器上编，这样编译时的单元检查能在本机架构上跑。发布前对每个 exe 核对四件事：是从这个提交编出来的；散列和 CI 记录的一致；文件里的产品版本就是这个版本；是对应架构的 Windows GUI 程序，这样 Scoop 生成的 `nemoterm` 和 `nt` 两个 shim 也是 GUI 的，不会多开控制台窗口。
- **完整测试不是发布门槛**：测试套件有已知失败项，见[已知问题](KNOWN_ISSUES.md)，而且只测 x64 的 exe。发布只要求三个 exe 都编出来，也就是都通过 `build-single-exe.ps1` 自带的单元检查。发布说明里链接那次运行，并写明它的结果。
- **arm64 版暂时没有 WSL「Linux PTY」选项**：这个选项用的转接程序只有 x86-64 的 Linux 版，而 Windows on Arm 上的 WSL 发行版是 aarch64 的，所以 arm64 版不内嵌它，设置里也不显示这个选项；WSL 照常经 ConPTY 运行。
- 资产是 `nemoterm-<版本>-windows-{amd64,386,arm64}.zip`（各含 `nemoterm.exe`、`LICENSE`、`LICENCE-PuTTY.txt`）和 `SHA256SUMS`。`v0.0.1` 只有 amd64。
- 自动发布漏掉时，手动运行 Release，填那次 Test and build 的运行 ID。
- 发布后通知 [package.anzupop.com](https://package.anzupop.com)（需要 `PACKAGES_DISPATCH_TOKEN` 密钥），再由它转告 [Scoop bucket](https://github.com/xiongnemo/windows-binaries-scoop-bucket)：预发布进 `nemoterm-nightly`。没有这个密钥也照常发布，bucket 每小时的 Excavator 会自己找到。

正式发布前先确认这个提交在 main 上编出了 exe，再打标签：

```sh
git tag v0.1.0 <提交> && git push origin v0.1.0
```
