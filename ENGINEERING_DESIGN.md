# OpenBound Engineering Design

状态：独立 OpenBound 源码候选。实际 remote、CI 与安装状态见 [current-state](docs/current-state.md)。

## 1. 当前决定与唯一所有权

本仓库是 OpenBound 的 canonical source。实现来源与比较基线见 [PROVENANCE](PROVENANCE.md)。源码、安装、Host discovery 与实际交付分别验证。

当前分发单元是一个 Skill：`skills/openbound/`。其中根指令、七份平面 references 和三个 Python 工具构成一个完整产品。它没有常驻服务、数据库、动态模块注册中心、独立四路分类器或强制 intake 表。A/B/C/D 是验收场景，可以在同一任务中组合。

完整安装与更新见 [installation](docs/installation.md)；当前安装、激活与远端状态见 [current-state](docs/current-state.md)。

| 能力 | 当前所有者 | 工程决定 |
| --- | --- | --- |
| 从私人材料到完整公共成果 | OpenBound | 负责选择对象/承诺、转换、必要设施、验证、交付及继续维护 |
| 候选秘密与暴露线索检查 | 候选检查器 | 保留现有规则与 Git 对象遍历，修复覆盖、身份和执行边界；不维护第二个扫描器 |
| 文档权威、读者路径、公共投影的编辑方法 | OpenBound，按需使用已有文档工具 | 保留已有有效材料，不将额外工具设为运行依赖 |
| 意图、源码、产物、运行证据之间的矛盾 | OpenBound 的定向工程调查 | 按证据层次解决当前矛盾，字节相同不能单独证明结论仍有效 |
| 实施、调查、评审、验证等工程方法 | 当前 Agent，可复用已有工程方法 | 同一任务委托与证据继续有效；方法调用不重新授权或接管目标 |
| 外部写入及运行隔离 | 当前 Agent Host 与用户授权 | 包内工具没有远端发布入口，也不假装提供 OS 沙箱 |

## 2. 产品行为与完成条件

任务首先确定两项关系：**公共对象**以及**公共承诺**。源代码、参考实现、方法文稿、实验记录、研究 Blueprint 都可以是完整公共对象；可安装、可复现、维护时限、接收贡献、同步频率是独立承诺。未实现的研究作品可以有完整交付，软件仓库也可以明确不持续维护。

| 场景 | 实际执行 | 完成条件 |
| --- | --- | --- |
| A 完整项目直接公开 | 保留成熟代码/测试/许可证/文档；只修真实的路径、配置、依赖、历史和交付问题；从候选运行既有检查和公开使用路径 | 完整候选及适当设施确实存在；已有行为保留；具体暴露范围已观察或明确未覆盖；授权内交付完成 |
| B 私人系统局部提取 | 选择原组件；隔离私人依赖；必要时加入新接口、假服务、文档与测试；记录被保留的原逻辑与新增解释 | 新根目录能独立执行所承诺的路径；不靠私人父仓库、凭据或导入缓存；来源和限制清楚；关键机制及反例未被示例抹平 |
| C 方法/实验/构想表达 | 实质性重写、组织论证、制作必要图示或合成见证；区分作者观察、原证据、新解释和假说 | 可独立阅读的完整作品；问题、机制、依据、反例和下一种可证伪观察都清楚；没有虚构成熟度；不强迫产生软件项目设施 |
| D 公开作品继续演化 | 从既有关系决定谁拥有代码、文档和变更；建立新候选；保留公共贡献；必要时复审变化的公开边界 | 私人源和上一公共版得到保护；变更与冲突有去处；可重复执行不覆盖编辑；允许结束投影并独立维护 |

公共准备可以结束在“完整本地可审查候选”，也可以在授权足够时继续到真实发布。报告必须点明实际状态，不能用扫描成功代替作品、用本地测试代替托管 CI、用创建仓库代替公开可见或可运行。

成熟项目的默认路径位于根 Skill 正文：确定范围 → 必要修整 → 候选验证 → 完成已授权交付。专题只在阻碍当前动作的事实出现时加载。已有完整文件允许原样交付，已有许可不自动更换，社区文档/图/CI 不组成固定文件清单。

## 3. 加载、切换与返回机制

根 `SKILL.md` 负责完整目标、默认成熟路径、七项证据到方法映射、上下文连续性和完成声明。Host 首先发现 `name/description`；加载根正文后，Agent 通过正常文件读取加载所需 reference。这里没有假设 Host 能解释自定义递归 manifest。

七个 references 各自是可直接执行的完整方法。目录不继续嵌套；同一个专题可以被成熟项目、提取、表达和维护重复使用。真正的选择是“当前哪一项不确定性阻止下一动作”，而不是先把整个任务塞入一个类别。

实际控制规则可以写成：

```text
恢复已有目标、授权、候选、决定与有效证据
选择当前可以推进的动作
若出现具体阻碍：
    保存这个动作及阻碍的最小上下文
    读取与阻碍匹配的一份 reference
    执行局部方法，修改作品或补足证据
    使受影响的证据失效；保留仍适用的事实
    返回原动作；必要时修订公共对象或承诺
完成已授权的完整目标并报告实际状态
```

这个动作栈是 Agent 的任务上下文，不要求生成文件。普通一次性任务只需对话和既有 Git 状态；长任务或持续投影才保存私有 continuation note。它只记目标/承诺、源目标关系、授权来源、候选身份、有效回执、剩余问题和下一动作。它不是授权 token，也不因被写入文件而成为用户决定。

**不重复 intake。** 任务已经确定的读者、许可证、历史策略、权限继续有效。切换到隐私方法不会再次询问作品用途；切换到表达方法不会重新规划已经完成的设施。重复运行 `materialize` 在源/计划/候选均相同时返回 `no_change`；重复 `check` 在有效回执匹配时返回 `reused`。`status` 做身份核对，不重跑模式扫描或可执行检查。

判断“哪些证据受影响”归模型；确定输入是否变化归程序。当前工具采取保守的整候选身份，没有实现细粒度增量扫描缓存。这样避免伪造选择器依赖图。真实大仓库压力证明有价值后，可为稳定表面增加增量缓存；在此之前，方法切换本身不会触发重扫，候选实质改变会。

## 4. 实际文件与接口

| 文件 | 责任 |
| --- | --- |
| `skills/openbound/SKILL.md` | 单一完整任务入口和默认行为 |
| `skills/openbound/references/*.md` | 选择/提取、表达、读者与设施、隐私历史、交付、维护、恢复与工具的完整正文 |
| `skills/openbound/scripts/project_candidate.py` | 显式选择、精确替换、隔离输出、回执和恢复 |
| `skills/openbound/scripts/inspect_public_candidate.py` | Git 候选信号检查；精确补丁同时交付 |
| `skills/openbound/scripts/verify_public_work.py` | 经审查命令、临时副本、机制见证、检查范围、身份与证据复用 |
| `tools/fixture_factory.py` / `tools/run_scenarios.py` | 四种合成输入与可复现的完整本地场景 |
| `tests/` | 原扫描测试、修复回归、投影/恢复、验证/边界和端到端检查 |
| `evals/` | 独立 Agent 任务、隐藏评审标准、负面任务和 Host 激活验收 |
| `docs/validation.md` | 可共享的观察摘要与限制；原始日志和位置绑定回执保持 Git 外私有 |
| `tools/validate.py` / `tools/package.py` | 单一验证入口、异地安装单元 smoke 与 tracked-only source archive |

所有运行时 Python 代码使用标准库，要求 Python 3.10+ 与 Git。已运行宿主、精确测试数及其他平台状态记录在 [docs/validation.md](docs/validation.md)。工具脚本可以直接执行，不要求安装 OpenBound 自身的 Python 包或常驻后台。

## 5. 投影数据与转换语义

最小计划是 `openbound-projection/1`：

```json
{
  "schema": "openbound-projection/1",
  "files": [
    {"source": "src/tool.py", "target": "src/tool.py"},
    {"source": "README.md", "target": "README.md", "replacements": [
      {"old": "cd /private/work/tool", "new": "cd tool", "expected_count": 1}
    ]}
  ]
}
```

选择必须明确。`inventory` 只为 Git tracked 路径提出待审清单，使用当前工作树字节；它不自动纳入 untracked 文件，不筛掉已 tracked 的秘密，也不将 tracked 等同于公开许可。没有 Git 的材料可以直接编写显式计划。

`materialize` 读取所选源文件两次以检测普通漂移，在目标同级构建临时目录，再用无覆盖原子 rename 发布新候选。源、目标、回执必须分离；不执行源代码、hooks、Git 初始化或网络操作。文件普通权限保留；拒绝链接、特殊文件、危险控制路径、路径穿越、大小写/规范化冲突及特殊权限位。ACL、xattr、所有者与时间戳不在承诺中。

字面替换按顺序执行，每条在当前文本上要求精确计数，UTF-8 解码失败则拒绝替换。二进制可原样复制，但后续文本扫描不会因此证明其内容安全。通用代码重构、文档创作和接口设计仍由 Agent 在隔离工作区完成；工具不以全局字符串替换冒充语义改写。

需要新增文件时，Agent 建立一个私人 editorial workspace：复制选中的原始文件，保留原文件身份，再加入新写的公共内容；工具投影这个工作区。回执的 source 指向实际工作区，不能伪称绑定未经复制核对的原始仓库。B/C/D 场景脚本实际演示了此路径。原材料和新增材料之间的关系只在影响来源/证据判断时持久化。

投影回执版本 `openbound-projection-receipt/1` 包含计划哈希、源/目标位置哈希、所选源文件的路径/字节/权限，以及完整候选文件/空目录/根权限身份。它明确 `atomic_snapshot: false`；两次读取不能替代文件系统事务。应从静止 checkout 或已固定的工作副本处理材料。

### 恢复与漂移

| 已观察状态 | 行为 |
| --- | --- |
| 无旧回执、无目标 | 构建新候选；写 prepared 回执；无覆盖 rename；核验最终位置；回执转 complete |
| prepared，目标不存在，源/计划仍匹配 | 重建原选择并继续；返回 resumed |
| prepared，目标已经完全匹配 | 说明可能在 rename 后丢失确认；核验并转 complete，返回 recovered |
| complete，源/计划/候选一致 | 返回 no_change，不改写内容或回执 |
| 目标陌生、源/规则改变、候选新增/改动/缺失 | 拒绝覆盖；保存原成果；审查差异，使用新候选与新回执 |
| complete 但目标已被删除 | 拒绝静默重建；调查删除原因 |

回执使用合作进程锁，空锁文件留在私人状态目录以避免 unlink 产生锁 inode 竞态。不可为了重试删除回执、清空候选或放宽替换计数。工具仅清理自己创建且身份仍匹配的临时目录。

**Git 初始化是新的身份阶段。** 投影回执覆盖完整文件树，所以在候选内新增 `.git` 会使该回执失效。先验证投影，再按授权初始化/提交，然后用实际 Git 候选及最终 commit/tag 形成新证据。不得忽略新 `.git` 后继续声称旧回执覆盖整个目录。

## 6. 检查覆盖：三项缺陷的准确修复

继承原脚本的规则与对象读取，实现补丁见 `patches/inspector-baseline.patch`。它可应用到固定 baseline；`provenance/baseline/inspect_public_candidate.py` 是 byte-exact 原文件，三个回归测试会实际对照旧行为。

| 失效模式 | 当前行为 | 不作出的推论 |
| --- | --- | --- |
| 秘密只在 commit message | `--candidate-ref` 读取目标 commit 原始 metadata；`--history-ref` 读取全部所选本地可达 commit metadata；明确选中的 annotated tag 链也读取 | 默认工作树/index 检查没有自动检查全部 Git 历史 |
| shallow clone 可见部分干净 | 指定历史时报告 `history.shallow_boundary` 与未观察 ancestry；`--fail-on-incomplete` 返回 3 | 浅克隆并不一概阻止仅公开当前树；不自动 fetch |
| LFS pointer 看起来像普通文本 | 绑定 oid/size、报告 payload 未观察及覆盖缺口；本地 LFS cache 也不自动被当作已检验 payload | 指针 hash 不是对实际对象内容的检查，不能据此交付大型对象 |

Metadata 读取复用批量 `cat-file`，不会为每个 commit 启动新进程。保留多路径同 blob、merge 路径、稀疏工作树/index 回退等原实现能力。缺失对象、非 UTF-8 metadata、binary/large、grafted ancestry、未合并 index、submodule 等不能默默变成完整覆盖。

报告新增 `report_format: openbound-inspection/2`。原数值 `schema_version: 2` 保持兼容，所以消费者必须使用新字符串格式标识区分协议。核心字段：

```text
subject.id / subject.surfaces        实际选定路径/内容身份、resolved object 和 metadata 身份
rules.version / rules.sha256        规则版及完整引擎源码摘要
coverage.facets[].status             observed / unobserved / not_selected
coverage.limitations                 选定范围的缺口
claims.selected_text_surfaces_exhausted
claims.no_rule_matches_on_observed_surfaces
claims.publication_ready = false
```

`scan_complete` 是选定文本范围已处理的兼容别名，不表示安全。`not_selected` 与 `unobserved` 区分任务没选的表面和任务选了但未读到的区域。规则有限、身份/权利/组合披露需要判断，`publication_ready` 始终 false。

默认 `both` 检查工作树/index。提交或打 tag 后，最终检查必须明确 `--candidate-ref`；保留 ancestry 时还需 `--history-ref`。其他 refs、被忽略文件、远端附件、GitHub PR 页面和派生资料不自动包含。新建公共历史可以合法地排除私人旧历史，但仍须检查新提交 metadata 与实际将推送的 refs。

扫描过程关闭 lazy fetch、Git 协议、配置环境注入、replace refs，以及 filters/fsmonitor/hooks/signature verifier 等可能执行外部程序的路径。错误与明显秘密标签不回显原内容。报告仍是私人材料：相对路径与上下文也可能敏感。

## 7. 可执行验证、机制见证与证据身份

验证契约 `openbound-verification/1` 选择真实入口。每个检查包含 id、argv、超时、预期退出码，可额外要求 stdout JSON 等于指定结果；不经过 shell。每个命令从新的临时候选副本执行，使用不继承凭据的最小环境，输出仅记录哈希、字节数、退出/断言状态。stdout/stderr 超限或超时都失败，不把完整输出写入报告。

可选见证把两个已通过的 JSON 检查以 `equal_json` / `different_json` 关系联系起来。B 场景实际比较正确分页结果 37 与错误的一页读取 8；把样例缩小为 5 条时，两种实现都得到 5，见证失败。这是有判别力的机制测试。它只证明这次受控结果的关系；“保留了什么机制”由 Agent 根据原材料作出有依据的解释。对 Blueprint 使用零执行检查时，`all_requested_checks_passed` 为 null，不能用空集合真值伪造实测成功。

回执绑定原候选所有文件/目录/普通权限、契约原字节、两个引擎源码、实际 Python/Git、直接可执行文件、绝对文件实参及可选 `dependencies` 外部文件。`status` 比较这些身份；候选或所声明输入改变使旧证据过期，原回执不被覆盖。`check` 发现完全匹配的回执可复用；过期则选择新回执路径并进行新的必要检查。

`fresh` 的明确范围是这些被绑定的输入。动态安装包、隐含脚本依赖、硬件、外部服务及完整 OS 环境不被自动证明相同。关键动态依赖由作者选择检查并记录适当环境身份；发生实质环境变化后重新运行。文件哈希和 unsigned receipt 不提供防恶意伪造能力。

非 Git 候选使用临时副本初始化空模板 Git index，并 force add 所有候选文件，再调用原检查器。这包含被 ignore 的实际候选内容，且不更改原候选。它没有原始 Git 历史；要求 history/ref 时明确拒绝。真实 Git 候选在自身范围检查。原候选与执行副本的实际 worktree/gitdir 都必须匹配；`.git` 文件、共享 commondir、alternates 或转根布局在 wrapper 中拒绝，避免把别处的干净结果绑定到这个候选。

`--execute-reviewed` 是防意外执行开关，不能授予权限。命令可以执行主机允许的任意动作；这套 runner 没有 OS 或网络沙箱。外部贡献、未知构建脚本和不可信仓库必须在适当的宿主沙箱中执行。正常作者自己的受审命令不需附加一次权限仪式。

## 8. 公开设施、表达与视觉

Agent 根据真实读者路径补必要设施。小 CLI 可能只需要已有 README/测试/许可和简短贡献说明；提取组件需要接口及独立性证明；Blueprint 需要论证和证据边界，可能完全不需要 CI。长期多人项目才可能需要独立 CONTRIBUTING、政策或发布自动化。已有充分内容保留原样。

图像的触发条件是它能解释文字不容易承载的关系，例如控制/数据路径、信任边界、源与公共版本所有权、假说与实测的差别。为事实图保存可编辑源，标出拟议/已实现边界，实际渲染并检查布局与可读性，配等价文字说明。图源、SVG comments、字体/附件及远端渲染服务都属于公开/处理表面。

本包提供一张当前实现的所有权和证据流图，见 [docs/architecture.md](docs/architecture.md)。它解释三个工具与 Host 边界；它不会被自动添加到每个用户项目。

## 9. 权限与数据流

| 动作 | 本地/外部状态 | 判定与完成证据 |
| --- | --- | --- |
| 读源、隔离编辑、生成候选 | 本地可逆 | 当前任务授权；候选及源保护证明 |
| 执行测试/构建 | 可有任意代码副作用 | 命令审查及适当宿主边界；实际退出/断言和产物身份 |
| 本地 Git 初始化/提交/tag | 本地持久变化 | 当前任务是否包含此动作；新对象身份与 metadata 检查 |
| 创建远端、push | 外部写入 | 明确目标与已存在授权；实际远端 refs |
| visibility change | 扩大访问边界 | 精确仓库与授权；观察实际可见状态 |
| Release、包发布 | 新公开表面 | 精确 assets/包内容/版本；实际发布状态 |
| 部署 | 运行与外发副作用 | 精确目标与权限；运行版本及具体验收 |

委托给子 Agent、加载深层 reference、receipt 中写了 allowed 都不会扩大权限。源码开发、push、安装、visibility、Release 与部署分别依照当前任务已有授权；实际到达的状态只在 current-state 记录。

处理材料时，网络搜索、外部模型、远端图表渲染、包构建、日志和截图都可能是出口。优先只传所需片段；不要把私人原文当搜索查询，不把全量上下文交给无关工具。历史泄漏的凭据需要按实际授权处理撤销/轮换；改写 Git 不会撤回其他人已经获得的副本。

长期关系可以是单向投影、选择同步、双源分工或完全独立。公共贡献先作为不可信输入在公共隔离环境评审；不要把其 CI、构建脚本、配置或测试代码直接放入带私人凭据的开发环境执行。批准的逻辑变更通过局部移植进入私人分支，作者/许可/归属保持可追溯。工具不会自动双向同步或把公共树覆盖私人树。

## 10. 容量、宿主与已知限制

| 组件 | 当前明确限制 |
| --- | --- |
| Projector | 4096 文件；单文件 8 MiB、所选总量 64 MiB；计划 4 MiB、投影回执 8 MiB；POSIX 安全读取；Linux 和 Darwin 无覆盖 rename 均有本地测试观察，具体环境见验证记录；其他平台失败关闭；路径各级 ancestor 必须是实体目录 |
| Inspector | 文本规则范围；默认单 blob 2 MiB；选定历史只本地可达；LFS payload/binary/超限为缺口；POSIX 安全工作树读取；不递归解包所有格式 |
| Verification | 单候选文件 64 MiB、总量 256 MiB；单命令输出 1 MiB；契约 1 MiB、验证回执 16 MiB；单命令超时 0.1–600 秒；POSIX 执行；普通无链接文件树 |
| Host 行为 | 源码有 implicit metadata，不证明命名 Host 已激活；实际 source-directed trials 与 Host 隐式路由试验分开记录 |

这些界限让工具对没有观察的部分明确失败或标缺口；它们不是 OpenBound 产品的最大能力边界。超限项目可以选用现有 Git/发布/媒体工具完成工作，并按同样身份与证据要求记录结果。需要扩容时做有对应失败样例的工程扩展，不能把拒绝改成静默跳过。

## 11. 验收和继续演化

运行 `python3 -B tools/validate.py` 验证结构、链接、代码与异地 Skill CLI；它为测试提供实体临时目录。需要保留候选时运行 `tools/run_scenarios.py`，输出放 Git 外新目录。Agent eval 的 task 与 evaluator-only oracle 分开，新线程只得到 Skill、普通任务和源材料。阅读试验只能称 Agent 盲读，未招募真实目标读者。没有基线控制、重复样本与命名 Host 观察时，不作效率提升或激活准确率宣称。

完成阶段按有价值的整体功能定义：独立源码保留必要实现来源，本地方法与工具、统一检查、安装说明和可编辑图齐备；本仓库的公共 Git 历史从新根开始。命名 Host 的 discovery 及行为观察仍是独立 gate，不能由显式读取 source、CLI smoke 或模型自述替代。远端发布集成依赖实际授权。

仍可随真实使用修订的选择包括：是否将巨大资产的专用检查加入绑定协议、哪些反复使用的转换值得变成稳定算子、如何对长期多产物进行累积披露分析、是否需要可控的增量历史缓存，以及公共项目何时终止投影关系。这些不会阻止当前源码运行或迫使每次任务增加程序。
