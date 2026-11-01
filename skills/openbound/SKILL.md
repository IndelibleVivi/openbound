---
name: openbound
description: "Turn private software, components, methods, experiments, and research ideas into useful public work; prepare complete public candidates, carry authorized publication through delivery, and maintain private/public relationships. Use for public release preparation, extraction from private systems, publication of unfinished work, or changes crossing a private/public boundary. Ordinary development or a public README edit without such a boundary stays in the normal workflow."
---

# OpenBound

把私人作品发展为公众能够理解、信任、使用或继续发展的作品。承担用户所要求的完整结果：判断形式，完成转换，验证候选，完成已获授权的交付，并准确报告到达的状态。

OpenBound 是完整公开任务的唯一负责人，接替 Public Repo Craft 的入口。复用成熟方法；不要启动另一个 Public Repo Craft intake，也不要把 Repo Docs Curator、Repo Truth Audit 或 Servotab 当作必经阶段。

## 从当前任务直接推进

从对话与现有项目恢复：要公开什么、给谁、承诺什么、源与目标在哪里、哪些动作已经获准。已有答案继续有效。先读实际入口、配置、文档、测试、构建和交付行为，不以 README 的自述代替实现。

只为会改变工作且无法从现有证据推断的缺口提问。普通任务不要求填写表格、选择四条路径、创建计划文件或重新解释作者动机。重大未知不妨碍先完成其余已授权工作。

区分两个决定：**公共对象**是什么，**公共承诺**是什么。完整源码可以承诺不维护；Blueprint 可以承诺解释机制而不承诺可运行；公开展示不自动承诺开源、重现私有实验或接收贡献。保留已确定的许可证与产品选择。

## 成熟项目：默认直接完成

项目已有可用代码、测试和文档时，执行下面的完整路径。仅在出现具体证据时打开下方专题。

1. **锁定候选范围。** 读取当前修改、源版本、待公开文件与历史策略。决定就地修整还是隔离候选；不把私人父仓库、账户配置或 Git 历史顺手带过去。保存必要的回滚点，保护用户未提交工作。
2. **检查真实公开面。** 检查所选文件、配置、身份、路径、例子、二进制、生成物，以及实际准备交付的 index、ref、历史或附件。使用 `scripts/inspect_public_candidate.py`；根据任务读取 `references/privacy-and-history.md`，解释未覆盖表面，不把扫描无发现解释为安全证明。
3. **完成必要修整。** 在授权范围内修复配置、私有依赖、示例、文档链接和发布入口。保留已经正确的代码、README、许可证、测试和 CI。确有缺口才补相应设施；不要为整齐而重写架构、补齐所有社区文件或创建新的公共审查台账。
4. **在候选根目录验证。** 运行项目自身有意义的检查与公开使用路径；依赖、路径与凭据按公共读者的环境验证。必要时构建实际安装包或渲染文档。验证输入必须指向交付候选，不能仅引用私人源的成功结果。
5. **收敛并交付。** 将检查与验证绑定最终候选身份。处理新改动导致的失效证据。完成已获授权的提交、远端或发布动作；遇到新权限边界时，先把其余工作做成可审查成果，再请求所缺授权。返回候选位置、实际变化、验证结果、未覆盖范围和交付状态。

工作正常时不增加旁支任务。已有内容完善且无需变化，允许交付“已验证、无文件改动”的候选。

## 按证据选择展开

在某个动作真正受下列不确定性影响之前，读取对应文件。先读需要的一个；不是依次遍历。可以同时使用多个方法，但保持同一个目标与候选。

| 观察到的证据或将执行的动作 | 读取 |
|---|---|
| 组件离开私人父系统、输出来自选择/生成、源与公共副本关系不明、私人依赖阻碍独立使用 | [selection-and-extraction.md](references/selection-and-extraction.md) |
| 对象是方法、实验或构想；需要重写、合成示例；转换可能改变机制或研究结论 | [expression-and-evidence.md](references/expression-and-evidence.md) |
| 读者路径不清、缺少必要公开设施、图能解释结构、现有文档与实际使用脱节 | [reader-and-facilities.md](references/reader-and-facilities.md) |
| 将暴露历史、标签、LFS、生成物、媒体；出现敏感线索、组合披露或处理过程的外发风险 | [privacy-and-history.md](references/privacy-and-history.md) |
| 将提交、创建远端、push、改 visibility、发 Release、发布包或部署；权利/来源不明 | [delivery.md](references/delivery.md) |
| 既有公共作品有新版本、双向改动、外部贡献、投影漂移、停止同步或独立维护 | [maintenance.md](references/maintenance.md) |
| 需要脚本接口、持续转换记录、检查缓存、任务恢复或故障后继续 | [continuation-and-tools.md](references/continuation-and-tools.md) |

专题结束时回到被它阻塞的动作；不重新 intake。读完一个专题不意味着必须读它提到的每个其他专题。若新事实改变公共对象、源选择或承诺，调整受影响部分并继续，不强行完成旧路径。

## 保留一份有效上下文

在当前对话/任务中保留：目标和读者、已决定的公共承诺、源与目标关系、已获授权的动作、候选身份、有效证据、剩余问题、下一步动作。只持久化恢复或长期维护确实需要的内容，放在公共输出之外；默认无需新的公共 manifest。

切换方法时传递上述事实及触发证据。新文件内容、选择器、生成器、规则、历史范围或验证环境变化，只使其依赖的证据失效。不同候选身份不能共用“已检查”的结论。重新扫描受影响的表面；不能确定影响范围时才扩大检查。

模型负责意义、读者、形式、威胁范围、权利判断、设施取舍与创作。程序负责确定性选择、原子输出、内容身份、观察范围、规则命中、验证记录与漂移检测。程序不判断作品值得发表，也不授予权限；方法文件不构成隔离沙箱。

## 使用已有能力

需要文档权威、读者路径或公共投影设计时，可调用 Repo Docs Curator 的相应方法。需要解决意图、实际实现、构建产物与运行结果之间的矛盾时，可调用 Repo Truth Audit 的相应方法。需要具体工程行动的风险控制或调查方法时，可调用 Servotab 的相应方法。只传必要材料，不导出私人全量上下文；同一证据不因换方法而重读或重复运行。

这些 Skill 不可用时继续按本 Skill 完成工作。专业方法只能缩小已存在的不确定性，不接管目标，不新增用户未要求的审计，也不重新要求已有授权。

## 结果的证据边界

区分源事实、作者观察、Agent 新增解释、假说与候选上的验证。保留反例、失败条件和限制；让合成数据验证关键机制，不能用它证明真实环境中的效果。

区分本地候选、提交、远端状态、公开可见、托管 CI、Release/包、部署与实际运行。完成一个状态不证明下一个。只有确实观察到的状态才能使用完成措辞；未经执行的命令明确标记待运行。

最终报告应简明但足以继续工作：具体成果与位置；保留/改变的重要选择；在何种候选上运行了什么、结果如何；尚未覆盖或失败的内容及其影响；实际交付状态；如受阻，准确的下一动作。不要把扫描报告、计划、建议清单或“准备好了”代替用户要求的完整作品。
