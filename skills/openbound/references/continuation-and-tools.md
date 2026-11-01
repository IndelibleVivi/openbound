# 脚本接口、证据复用与恢复

在运行包内工具、需要重复投影或任务跨会话恢复时读取。相对命令均从本 Skill 根目录运行；将路径参数换成实际路径。回执保存在候选之外，不作为公共作品的一部分。

## 确定性边界

三个工具承担不同事实：`project_candidate.py` 证明按某个明确选择规则构造了什么；`inspect_public_candidate.py` 记录实际观察范围与规则命中；`verify_public_work.py` 记录在某候选上运行的检查与见证。它们都不判定发表价值、法律权利、语义安全或用户授权。

输入和输出路径的每一级 ancestor 必须是实体目录，不能包含 symlink。macOS 的 `/tmp`、`/var` 等别名先解析为实际路径；本仓库的 `tools/validate.py` 已为测试选择实体临时目录，不需要放宽产品 guard。

工具默认不执行远端写入。验证命令可能执行项目代码；`--execute-reviewed` 只防止意外执行，不是许可或沙箱。只在当前授权及宿主隔离足够的条件下执行已检查命令。

## 显式投影

先用 inventory 查看可选文件；选择规则由 Agent/作者决定。

```bash
python3 scripts/project_candidate.py inventory --source /private/source
python3 scripts/project_candidate.py materialize \
  --source /private/source --plan /private/openbound-plan.json \
  --target /work/public-candidate --receipt /private/projection-receipt.json
python3 scripts/project_candidate.py verify \
  --target /work/public-candidate --receipt /private/projection-receipt.json \
  --source /private/source --plan /private/openbound-plan.json
```

最小计划是机器执行配置，不是完整 intake：

```json
{
  "schema": "openbound-projection/1",
  "files": [
    {"source": "src/tool.py", "target": "src/tool.py"},
    {"source": "README.md", "target": "README.md"},
    {"source": "config.example.json", "target": "config.example.json",
     "replacements": [
       {"old": "/private/example-root", "new": "./data", "expected_count": 1}
     ]}
  ]
}
```

计划可能含私人路径和待替换原文，保持私有。预期替换次数不符应失败；检查真实差异后修正规则，不能调宽计数只求通过。成熟项目通常应选择所有必要成熟内容；这个缩小示例不是要求只导出三个文件。

首次输出必须是新目录；重放使用其原回执。陌生文件或用户改动导致漂移时停止覆盖，审查差异；不要删回执后强制重跑。失败不应损坏原源与上次有效候选。

## 选定公开面的检查

```bash
python3 scripts/inspect_public_candidate.py \
  --repo /work/public-candidate --candidate both --json \
  --fail-on-findings --fail-on-incomplete
python3 scripts/inspect_public_candidate.py \
  --repo /work/public-candidate --candidate none \
  --candidate-ref HEAD --history-ref HEAD --json \
  --fail-on-findings --fail-on-incomplete
```

第一条用于实际有 Git 的工作树/index；第二条用于即将交付的精确 ref 和其历史。`--candidate-ref` 检查所选树、提交 metadata，以及显式所选 annotated tag 链；`--history-ref` 再检查本地可达历史的内容与 commit metadata。其他 refs、忽略文件和 Release 附件不会因此被覆盖。不能因为脚本支持历史检查就为所有任务额外检查私人历史。

非 Git 作品由 `verify_public_work.py` 在临时副本初始化空模板 Git index 并显式加入文件（包括被 ignore 的候选内容）后调用检查器；回执绑定原候选身份并注明 adapter，原候选不被修改。该路径拒绝 history/ref 选择。有普通 `.git` 目录的候选按真实仓库检查；wrapper 拒绝 `.git` 文件间接指向外部 worktree，避免误扫描私人父仓库。需要高级 worktree 检查时明确范围并直接使用 scanner。

`--fail-on-findings` 让命中阻止自动继续；命中仍需人工判断。`--fail-on-incomplete` 阻止覆盖不足被当作成功。退出码为 0 正常生成报告、1 命中且要求失败、2 参数/对象/执行错误、3 覆盖不足且要求失败；3 优先于 1。退出码本身不能描述暴露范围，始终读取结构化报告中的 subject、rules、coverage、claims 与限制。

## 验证与机制见证

```bash
python3 scripts/verify_public_work.py check \
  --candidate /work/public-candidate --contract /private/verification.json \
  --receipt /private/verification-receipt.json --execute-reviewed
python3 scripts/verify_public_work.py status \
  --candidate /work/public-candidate --contract /private/verification.json \
  --receipt /private/verification-receipt.json
```

状态检查用于恢复和方法切换后的证据复用，不重新执行测试。工具发现候选、契约或工具身份变化时，旧结果过期；评估影响并运行必要的新验证。命令在新临时副本中运行；不能依赖父仓库、个人安装包或私人缓存提供候选缺失内容。

`fresh` 的范围是候选、契约、两个引擎源码、当前 Python、实际 Git 程序、直接执行程序、绝对文件实参及显式列出的外部文件；它不证明整个操作系统、动态安装包、远端服务或硬件环境相同。把重要的外部文件加入可选 `dependencies` 数组（绝对文件路径，保持私有），环境有其他实质变化时新建回执并重新验证。路径嵌在代码字符串或由程序动态读取的依赖需要调用者识别，工具无法静态穷举。

原候选和每个执行副本都会核验 Git 的实际 worktree/gitdir；不允许 `core.worktree` 使检查转到别处。wrapper 拒绝共享 `commondir`、alternates 和间接 worktree；如确需这些高级布局，先形成自包含候选，或明确范围直接使用检查器。不要把私人父仓库当临时 Git 元数据。

最小软件契约示例：

```json
{
  "schema": "openbound-verification/1",
  "checks": [
    {"id": "project-tests", "argv": ["{python}", "-m", "unittest", "discover", "-s", "tests"],
     "timeout_seconds": 120, "expected_exit": 0}
  ],
  "witnesses": [],
  "dependencies": [],
  "inspection": {"candidate_mode": "both"}
}
```

契约选择实际项目入口，不添加只镜像实现的无意义测试。见证可引用两个返回 JSON 的检查，通过 `equal_json` 或 `different_json` 验证所定义关系；先确认检查本身断言的是关键机制。比较结果不同只证明不同，不自动证明性能、因果或研究结论。

不把命令输出直接写进公共记录。工具只保留约束后的状态/摘要与身份；需调查失败时在授权私有环境查看必要内容，先判断是否含秘密。产物/环境副作用和网络隔离仍由宿主与实际执行命令决定。

验证 wrapper 当前限制：单候选文件 64 MiB、总字节 256 MiB；单命令捕获输出最多 1 MiB、超限失败；契约最多 1 MiB、回执最多 16 MiB，超过时不产生可复用成功回执。JSON 输入必须是普通文件，FIFO/链接会拒绝。执行需要 POSIX；macOS/其他 Python 版本需在实际宿主复核。投影器另有更保守的选择限制，参见脚本常量和 Engineering Design。

## 持久化最少恢复信息

一次性短任务优先复用对话与现有 Git 状态。长任务、持续投影或跨会话恢复时，私有保存：目标/承诺、源关系、选择规则身份、候选身份、已获授权动作、有效检查回执、未解项和下一动作。不得保存完整 secret 或全量日志来“方便恢复”。

恢复时先观察真实状态，核对候选、规则和已完成的外部对象；不要只相信旧笔记。配置、生成器、选择器、引用范围或环境变化会影响证据，即使单个文件 hash 未变。选择最小受影响工作继续；方法切换不是重新运行所有工具的理由。

## 失败与完成

对执行中断、目标漂移、缺失 LFS、浅历史或环境缺失，保留旧有效候选，记录实际到达状态和最小恢复动作。不得修改回执使失败看起来通过。

工具结果只是交付证据的一部分。Agent 仍需完成公共作品、必要设施、读者路径与已获授权的外部动作，并按照 `SKILL.md` 的结果边界报告。程序的零退出、空发现、可重放或有回执均不等于完整公开任务完成。
