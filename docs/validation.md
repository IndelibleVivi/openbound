# 验证状态与证据边界

## 当前公共候选的本机观察

2026-11-01，在本公共候选根目录运行 `python3 -B tools/validate.py`：结构与本地
链接、116 项 unittest（0 failures/errors/skips）、异地复制后的三个 CLI 均通过。
环境为 macOS、Python 3.13.3、Git 2.49.0；`skill-validate skills/openbound` 通过。

测试覆盖 Darwin 无覆盖原子 rename、投影恢复/漂移、scanner metadata/shallow/LFS、
验证证据失效和源码归档边界。归档测试核对 tracked-only 选择、私人/未跟踪文件排除、
源不改写、manifest 字节、文件权限、双语入口保留及拒绝覆盖/链接。

统一入口为测试选择实体临时目录，兼容 macOS 的临时路径别名；产品 no-follow guard
保持不变。原始日志、位置绑定回执与私人运行材料不提交到本仓库。

## 四种确定性场景

| 场景 | 能够支持的结论 |
| --- | --- |
| A 成熟项目 | 原行为、测试、许可与 CI 保留；只替换必要路径；候选实际运行；源不变；no_change/reused |
| B 组件提取 | 新根 callback seam 能运行；37/8 分页区别仍在；会抹掉区别的 5 条输入被见证拒绝 |
| C Blueprint | 受控文稿保留作者报告、合成示例、假说、反例与证伪计划；零执行检查返回 null |
| D 持续维护 | 公共文档保留；私人/旧公开源不变；新文件使旧投影拒绝、验证 stale |

`tools/run_scenarios.py` 按程序构造这些结果；C 的文字断言只证明 fixture 一致性。
这些测试不证明 Agent 创作质量、真实读者理解或现实研究效果。

## 原工程包报告的历史结果

原工程包报告：Linux / Python 3.12.14 / Git 2.51.1 上 115 项测试通过，四次独立
source-directed Agent 任务产出候选，C 经一次 Agent 盲读修订；审查后修复了
Git 转根、外部程序身份失效、大回执读取与 FIFO 阻塞。这些是历史报告，不是本公共候选的新观察；原始私人输出不纳入本仓库。

本轮重新运行的本地工具测试与包作者报告分别记录。没有将历史 Agent 自述当作
本轮的新盲测，也未重复开展 live model evaluation。

## 未验证

命名 Host 的隐式 discovery/activation、旧 PRC installed 注册迁移、真实目标读者、
真实私人业务仓库的完整公开、LFS payload/二进制语义、任意累积披露、敌对文件系统
并发和所有第三方权利均未因此得到验证。verification runner 不是 OS/网络沙箱；
freshness 不涵盖所有动态包、硬件或远端服务。原生 Excalidraw Host 交互导入未验证。

远端 push、托管 CI、公开可见、Release、包发布和部署分别观察并报告，不从源码或
本机成功外推。Agent 行为和 Host 验收协议在 [evals/ACCEPTANCE.md](../evals/ACCEPTANCE.md)。
