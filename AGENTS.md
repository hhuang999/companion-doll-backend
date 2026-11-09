# Companion 后端接手说明

## 当前项目

这是 Python 3.10 后端，服务于情感陪伴玩偶课程原型。当前主路径为 v2 Cognition，内容包为 `course-1.0`：六类支持策略、三段短练习和固定危机文本。公开网站为 `docs/` 下的静态研究说明和交互展示，不提供在线聊天 API。

接手先读 [工程入口](ENGINEERING.md)、[本轮 review 与验证](companion/docs/ENGINEERING_REVIEW.md)，按任务查阅 [架构规格](companion/docs/ARCHITECTURE_V2.md)、[运行手册](companion/docs/V2_OPERATIONS.md) 和 [小智交接](companion/docs/XIAOZHI_HANDOFF.md)。根 README 与网站保留研究报告入口；它们引用的历史性能测量有独立日期和范围。

`companion/docs/autonomous-upgrade/` 中的 TASK、START、CONTEXT 是已经完成的升级任务资料，不是待执行清单。当前状态见该目录的 IMPLEMENTATION_STATUS。`companion/docs/history/` 为旧设计参考。

## 目录与职责

- `companion/companion/core/`：会话、确定性控制、许可、风险接管和输出。
- `companion/companion/cognition/`：角色协议、调度、预算、评审和版本化计划发布。
- `companion/companion/content/`、`config/`：策略过滤、内容准入、固定音频和配置。
- `companion/companion/memory/`、`store/`：有来源和范围的记忆、SQLite 事务及迁移。
- `companion/companion/adapters/`：CLI、离线剧本及小智语音适配器。
- `companion/tests/`：离线行为回归和显式标记的在线测试。
- `scripts/`、`xiaozhi_patch/`：运行、检查、打包及固定上游接入。
- `data/`、`artifacts/`、`vendor/`：本机运行数据、检查产物和上游环境，均不提交。

## 已验证命令

在仓库根目录用 PowerShell 执行：

```powershell
./scripts/setup.ps1
./scripts/run.ps1 fake --db data/development.db
./scripts/run.ps1 test
./scripts/run.ps1 dashboard --db data/development.db
```

优先使用 `.venv/Scripts/python.exe`；依赖由 `companion/pyproject.toml` 与 `companion/requirements.lock` 管理。锁文件基于 Windows / Python 3.10。运行库在 `.python/`，小智有独立 `vendor/xiaozhi-venv`，无需切换全局 Conda 环境。

`scripts/check.py` 统一执行 Ruff、格式检查和离线 pytest。默认排除 `online`、`hardware`；在线验收会使用外部模型额度。打包与隔离 wheel 检查见 V2_OPERATIONS。

## 需要保持的工程约定

- Core 是会话状态和行动执行的权威；模型产物经 schema、来源、许可和最终版本检查后采用。
- 危机检测、实时表达与后台协作使用独立资源；取消以 generation 和实际任务占用为依据。
- 同一数据库只允许一个活动 Core；离线清除、结束任务重试与迁移遵循 writer lease。看板独立只读连接，唯一写操作是风险处理标记。
- 数据库 schema 当前为 v2；保留 v1→v2 事务迁移及一致备份。持久化契约与迁移不是可随意删除的旧代码。
- 内容或角色提示词变化会影响准入摘要；按 CONTENT 更新对应证据，音频按实测资源单独绑定。
- 小智上游固定于 `92337881a7b6553614b47e137a774d02bf40512f`。provider 源码维护在 `xiaozhi_patch/files/`，补丁检查和应用由 `xiaozhi_patch/apply.py` 完成。
- API key、设备凭据、数据库和实际音频保存在忽略路径；可提交的验证汇总只使用合成数据。

网站内容导出读取指定 Git 提交，命令为 `scripts/build_project_site.py --revision HEAD`；源码修改先提交再导出。公开架构图固定到各自的实现提交，按 `docs/README.md` 重建。当前任务无需重新开展既有研究或重做视觉设计。
