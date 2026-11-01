# 验证状态与证据边界

观察日期：2026-11-01。以下区分本仓库上的新验证、既有公共交付证据和补充工程材料中的历史报告。报告的运行结果不等于本次独立执行；源码、安装、发现、激活和完整任务结果分别成立。

## 当前源码的独立验证

整合从公共 main `78e3e62966f126450ffc0ff35fa6f7e95e1bda1c` 开始，保留既有 117 项测试，采用补充材料中的 48 项测试，另加 2 项审查回归。实际环境为 macOS、Python 3.13.3、Git 2.49.0。

```sh
python3 -B tools/validate.py
skill-validate skills/openbound
git diff --check
```

完整 source gate 的 **167 项 unittest 全部通过**，无 failures/errors/skips；结构、本地链接、异地完整 Skill 的三个 CLI 检查通过，Skill authoring validator 通过。验证日志和位置绑定回执留在仓库外。

新增检查覆盖：

- scanner/verifier 在 Git 查询或路径解析前拒绝 symlink 根目录与祖先，包括 ref-only、`check`、`status`、契约与回执路径；原有 metadata、shallow history、LFS 反例保留。
- 可选 `execution_path` 仅接受已审查的绝对目录，不继承 ambient PATH 或凭据；直接程序、有效路径与既有依赖绑定回执。
- 六种安装 profile、相同完整 payload、幂等安装、差异保留、目录权限漂移、重复位置诊断，以及两种安装布局中的实际投影、扫描、验证操作。布局不等于正在运行的 Host。
- 可选 metadata 的两种边界：custom source 可省略它；从 canonical source 安装后删除它会报 drift。
- A/B/C/D/N9 任务准备、输入与 semantic index 保护、观察身份、固定检查、恢复身份、不可覆盖的旧证据；不以 keyword score 判断 Blueprint 质量。
- Git TRACE2 在新增 fixture 的旧实现中观察到两次 detached maintenance 启动。修复仅对 fixture 命令关闭自动 maintenance/GC，回归确认不再启动这些子进程；不修改用户 Git 配置或放宽快照断言。

`tools/host_trials.py` 的测试不调用模型，不安装 Host。`assess` 默认只读；A/D 的固定执行检查仍须显式开启并审查候选代码，运行器不提供 OS 或网络沙箱。

## 公共交付与托管检查

独立公共仓库已通过匿名 metadata/README 读取。既有下载测试确认 canonical Skill 的 12 文件与当时源码逐字节一致；这不证明当前版本已在某个日用 Host 中安装或激活。

基线 `78e3e62` 的 [托管运行 41276820309](https://github.com/IndelibleVivi/openbound/actions/runs/41276820309) 在 Linux/Python 3.10 与 macOS/Python 3.13 通过。它是历史证据，不覆盖后续改动。现有 [Actions](https://github.com/IndelibleVivi/openbound/actions/workflows/ci.yml) 继续调用同一个 `tools/validate.py`；每次结果以实际 commit 和运行记录为准。CI 不启动付费模型任务，也不自动发布产物。

## 补充材料中的历史 Host 报告

补充工程材料报告 Linux/Python 3.12.14 上的 165 项 source/archive gate，以及下列观察。本次没有重新安装这些 CLI、修改 trust 或启动模型，因此这些是有归属的历史报告，不能替代当前候选的行为验收。原始 traces 不公开，也不进入本仓库。

| 报告中的条件 | 报告结果 | 可采用的结论上限 |
| --- | --- | --- |
| OpenCode 1.19.5，项目 `.agents/skills` | 发现精确名称和路径，解析后的正文与当时安装的正文一致 | 那一份 payload 在该版本的原生发现；不证明 v2、激活或成果质量 |
| Gemini CLI 0.66.0，不受信任的项目 `.agents/skills` | inventory 退出 0，但没有 OpenBound | 退出码不能代替精确发现；该条件下未发现 |
| Gemini CLI 0.66.0，隔离用户 `.agents/skills` | 精确名称和路径，Enabled；未覆盖项目信任设置 | 那一份 payload 在该用户 scope 的原生发现 |
| 两个 source-directed Agent 会话，A 与 C | 产生合成成熟 CLI 候选和中文 Blueprint；未采集完整独立事件流与可比较成本 | 明确读取正文后的作品报告；不是命名 Host 的自然触发试验 |
| OpenCode 的 A 隐式任务尝试 | 服务报告免费用量限制；无模型输出、工具动作或候选 | 服务可用性阻塞；不能判 Skill 行为失败或授权边界通过 |

A/C 使用的正文早于最终续行说明修订，且早期记录没有后来新增的 semantic-index baseline。评估器对缺失基线报告 `not_observed`，不事后制造证据。其他 Host 的安装/调用表来自官方文档核对，不能称作六个 Host 已通过。

本次独立审查读取了提供的 A/C 作品，并仅重跑确定性部分：A 的 9 项 unittest 通过，C 的 6 个合成见证输出与所附结果 JSON 一致。A 的 wheel/sdist 构建、独立安装和历史自定义回执属于材料报告，本次没有重跑；C 未复现私人原实验，也没有证明持久化、并发、性能、新颖性或目标读者理解。示例和私人评审材料不作为本仓库的新增发行内容。

## 确定性场景与行为验收

| 场景 | 确定性检查支持的有限结论 |
| --- | --- |
| A 成熟项目 | 保留所选成熟设施与许可，候选实际运行，源不变，no_change/reused 状态可核验 |
| B 组件提取 | 独立 callback seam 可运行，37/8 的分页区别仍在，会抹掉区别的输入被见证拒绝 |
| C Blueprint | fixture 保留报告/合成/假说/反例/证伪区分；零执行检查返回 null |
| D 持续维护 | 公共修订可保留，私人/旧公开源不变，新增文件使旧投影拒绝、旧验证 stale |

`tools/run_scenarios.py` 按程序构造这些结果；C 的文字断言只验证 fixture 一致性。[Host 试验工具](../evals/host-trials.md) 提供任务、对照、负向触发和续行准备；[验收协议](../evals/ACCEPTANCE.md) 保留独立功能与语义审阅。准备工具、文件断言、单次作品都不能自动接受模型行为；`behavior_acceptance` 保持 `not_automatically_decided`，缺失指标为 `null`。

本次整合未启动新的模型评测、全局安装或 Host trust/settings 变更。命名 Host 的完整显式/隐式激活、方法使用、授权事件、恢复和净收益仍待另外授权的真实运行；无 Skill 对照与可比较成本数据尚不足以支持收益主张。

其他未验证范围：真实私人业务仓库完整公开、任意二进制/LFS 语义、累积披露、第三方权利、敌对文件系统并发、原生 Windows、原生 Excalidraw Host 交互导入。Freshness 不覆盖全部动态包、硬件或远端服务。源文件快照不能证明没有外部副作用。

远端 push、公开可见、托管 CI、Release、包发布、部署与实际运行继续分别观察和报告。
