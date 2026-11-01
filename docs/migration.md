# PRC → OpenBound：源码、安装与激活

OpenBound 的 canonical source 是 `IndelibleVivi/openbound`，安装单元为 `skills/openbound/`。旧 Public Repo Craft 用户可按下述步骤迁移；无需迁移旧 Git 历史，也不建立自动同步关系。实际发布与激活状态见 [current-state](current-state.md)。

## 取得完整安装单元

从已审查的 checkout 读取 `skills/openbound/`。完整 payload 包括 `SKILL.md`、
`agents/openai.yaml`、七份 references 与三个 scripts，不能只复制入口文件。
先执行仓库的 `python3 -B tools/validate.py` 与
`skill-validate skills/openbound`。

从已审查的公开版本安装，`OPENBOUND_REF` 应替换为实际确认的 commit 或 tag。

```bash
OPENBOUND_REPOSITORY=IndelibleVivi/openbound
OPENBOUND_REF=REPLACE_WITH_REVIEWED_COMMIT
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo "$OPENBOUND_REPOSITORY" \
  --path skills/openbound \
  --name openbound \
  --ref "$OPENBOUND_REF" \
  --method download
```

这是待执行的操作说明，不是安装回执。若目标已经存在，先比较来源和修改，
按已授权的安装流程更新；不要删除未知目录或绕过 installer 的拒绝。
离线复制也必须保留完整路径集与文件字节，安装后再核对，验证三个 CLI 能在不同
cwd 调用。普通执行需要 Python 3.10+、Git 与 POSIX。

## 迁移旧入口

只有获得主机安装/注册迁移授权后才操作 installed state。迁移前观察旧 PRC 的
实际注册方式、payload 和本机修改，保留可恢复副本。一次接管应完成：

1. 安装已验证的完整 OpenBound payload，核对路径、字节与 CLI。
2. 从 Host 的活动 discovery 中退役旧 PRC，或按 Host 支持的方式停止其隐式调用。
   备份放 discovery 目录之外，不能让旧工作流继续作为第二个完整成果 owner。
3. 刷新 Host discovery，在新会话中观察正向与负向请求。

正向请求是“把这个完整私人项目准备公开”，不点名 Skill，观察实际是否选中
OpenBound、读取了什么并完成候选。负向请求是“不涉及私人边界的公开 README
链接修复”，不应强制启动完整公开流程。显式 `$openbound` 试用只证明显式使用。

不能通过源码中的 `allow_implicit_invocation: true` 推断 Host 已加载它。尚未安装
或没有实际 Host 观察时，如实记录未验证；不阻止已授权的源码工作交付。

## 恢复

安装失败先检查实际目标与旧入口状态，不重跑不明结果的覆盖操作。需要回退时
恢复原来已经核对的完整 payload 和注册，刷新 discovery 并观察真实路由。
源码 commit、push、安装与激活不互相替代，远端 visibility、Release 和部署
仍需各自的明确授权。
