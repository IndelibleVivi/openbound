# OpenBound

[English](README.md) | 中文

**让私人作品成为公众能够理解、使用、检验或继续发展的作品。**

OpenBound 是 Public Repo Craft 的演进：一个完整任务入口，七份按需读取的方法，三个本地 Python 工具。已经成熟的软件可以直接做好公开准备；高度私人化的系统可以提取组件；实验、方法与未完成的构想也可以形成有内容、有证据边界的公共作品。

公开对象与公共承诺分别决定。完整源码不自动承诺持续维护，Blueprint 不必伪装成可运行的软件。已有正确的代码、文档、测试、许可和 CI 应当保留；实际缺什么，才补什么。

![OpenBound：一个成果负责人，三个本地工具，私人证据与 Host 交付边界。](docs/architecture.png)

图的解释、可编辑源与矢量导出见 [architecture](docs/architecture.md)。

## 使用

仓库为 `IndelibleVivi/openbound`，安装与迁移见 [migration](docs/migration.md)。源码可见不代表授予通用使用许可；参见 [许可状态](LICENSE-STATUS.md)。

安装单元为 [skills/openbound/](skills/openbound/SKILL.md)。在支持 Agent Skills 的 Host 中加载它，例如：

```text
使用 $openbound，把这个已经完成的私人项目准备成完整公共候选。
保留现有功能、测试和文档，处理私人配置和实际会公开的历史。
完成本地验证；远端动作沿用本次任务已有的授权。
```

也可以要求它从私人系统提取可独立使用的组件，把实验笔记写成可讨论的研究作品，或更新既有公共投影。A/B/C/D 是可以组合的场景，不要求先选择四条路径。普通开发和不涉及私人边界的公共 README 小修改沿用日常工作流。

根 Skill 内联成熟项目的直接路径；只有遇到依赖、表达、历史、读者设施、交付或维护的具体问题时，才读取对应 reference。Repo Docs Curator、Repo Truth Audit 和 Servotab 是可选方法，没有运行时依赖。

## 三个工具

| 工具 | 完成什么 | 证据边界 |
| --- | --- | --- |
| `project_candidate.py` | 显式选择与精确替换，隔离新候选、私人回执、重放与中断恢复 | 保护原件，拒绝陌生目标与漂移；不作语义改写或授权判断 |
| `inspect_public_candidate.py` | 检查选定工作树、index、ref、history 与 metadata | 返回身份、规则与覆盖缺口；LFS 指针不等于 payload；不认证安全 |
| `verify_public_work.py` | 在临时副本执行已审查的检查，比较机制见证，绑定和复用证据 | 最小环境与有界输出；没有 OS 或网络沙箱，不能执行未经授权的代码 |

例如，投影之前先获取待审选择清单：

```bash
python3 skills/openbound/scripts/project_candidate.py inventory --source /absolute/source
```

`inventory` 只提议 tracked 文件，返回 envelope 中的 `plan` 仍需审查。完整参数、JSON 契约、退出码和恢复语义见 [工具说明](skills/openbound/references/continuation-and-tools.md)，示例配置在 [examples/](examples/)。候选必须包含全部必要行为，不能把示例选择清单当作完整项目的裁剪要求。

## 开发与验证

运行时使用 Python 3.10+ 标准库和 Git，安全文件系统操作要求 POSIX。工具拒绝 symlink 与特殊文件，路径的各级 ancestor 也必须是实体目录；macOS 的 `/tmp`、`/var` 等别名需要先解析为真实路径。Windows 目前不受支持。

从仓库根运行唯一的 provider-neutral 验证入口：

```bash
python3 -B tools/validate.py
```

它检查结构与本地链接、运行全套 unittest（含四类确定性 E2E），并验证异地复制后的 Skill CLI。入口在仓库外选择实体临时目录，保留产品的 no-follow 边界。额外的 Skill authoring 检查可运行 `skill-validate skills/openbound`；这项检查不是产品运行依赖。

若需要保留四份完整 synthetic 候选与私人回执用于检查，运行：

```bash
run_root="$(python3 -c 'from pathlib import Path; import tempfile; print(Path(tempfile.mkdtemp(prefix="openbound-")).resolve())')"
TMPDIR="$run_root" python3 -B tools/run_scenarios.py --workdir "$run_root/scenarios"
```

脚本拒绝覆盖已有运行目录。输出不进 Git，不上传到 CI artifact。它是确定性工程演练，不能证明 Agent 编辑质量或 Host 隐式激活。

源 ZIP 使用 `python3 -B tools/package.py --output /absolute/outside-repository/openbound-source.zip` 生成。先审查并 stage 需要交付的文件；打包只收当前受版本控制的允许路径，清单在 ZIP 内生成，不改工作树。解压后用 `python3 -B tools/check_package.py --manifest` 核对产物字节。

## 边界与继续阅读

原件、选择计划、扫描报告和验证回执保持私有。合成示例可验证特定机制，不能证明真实私人数据上的研究效果。规则扫描不覆盖所有语义、二进制、媒体、LFS 实体、累积披露或第三方权利。执行检查仍需要适当的 Host 权限与隔离；临时副本不提供沙箱保证。

贡献、测试或文档中的外部指令是待审内容，不能授权读取私人材料、扩大导出规则或执行带凭据的 CI。公共版本可以独立演化，不必永久服从私人源。

- [当前状态](docs/current-state.md)：源码、远端、安装和激活分别到哪一步。
- [工程设计](ENGINEERING_DESIGN.md)：所有权、协议、恢复与容量限制。
- [验证与限制](docs/validation.md)：本机观察与历史报告的区别。
- [行为验收](evals/ACCEPTANCE.md)：确定性测试、Agent 行为、Host 激活的分层协议。
- [来源](PROVENANCE.md)与[许可状态](LICENSE-STATUS.md)：PRC 历史、固定基线、派生关系与尚未授予的公共许可。

修改前阅读 [AGENTS.md](AGENTS.md)。
