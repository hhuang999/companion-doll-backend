# companion-backend

Python 3.10 情感陪伴玩偶后端。包含独立 CLI、实时 Talker、后台有界多角色协作、确定性许可状态、风险接管、练习计划、四类有来源和范围的 SQLite 关系记忆和 Streamlit 看板。

当前维护与验证见 [工程 review](docs/ENGINEERING_REVIEW.md)。完整仓库的接手入口为根 AGENTS.md 与 [ENGINEERING.md](../ENGINEERING.md)；以下升级材料中的原始任务已经完成。

```sh
python -m pip install -e '.[test]'
companion --fake
companion --env-file /path/to/.env
companion-dashboard --db data/companion.db
pytest
```

默认 development 使用 course-1.0 六类支持、三段短练习与固定危机支持文本。仅合成案例或成年成员课程演示；demo 准入另核验来源、逐项回放、摘要和音频。当前状态见 `docs/autonomous-upgrade/IMPLEMENTATION_STATUS.md`；内容与实测见 `docs/CONTENT.md`、`docs/VALIDATION.md`。完整项目的 Windows 安装 / 运行脚本及小智补丁位于此包上层的项目仓库。

## v2 默认路径

Analysis 解释有限证据，Planner 生成候选策略；deliberation 另并行生成独立 Brief，再由 Critic 绑定确切版本评审，最多修订一次并复核。routine 只发布非行动策略。Core 冻结 TurnPolicyFrame，控制变化、记忆版本、TTL、DeltaGuard 和最终 CAS 共同决定是否采用。行动仍由原有许可状态机与卡片 Validator 决定。

`/policy`、`/memory`、`/jobs` 可观察该路径；默认配置含各角色模型及调用/token预算。FakeLLM 与 Aihubmix 走同一协议。

- [运行、迁移、重试、清除与 wheel 验证](docs/V2_OPERATIONS.md)
- [V2-01～V2-24 状态与证据](docs/V2_IMPLEMENTATION_STATUS.md)
- [真实验收与性能结果](docs/VALIDATION.md)
- [小智协议、凭据与联调交接](docs/XIAOZHI_HANDOFF.md)
- [研究与策略设计](docs/autonomous-upgrade/STRATEGY_DESIGN.md)
- [项目研究与系统设计说明（在线阅读）](https://hhuang999.github.io/companion-doll-backend/)
- [项目展示与交互架构（辅助入口）](https://hhuang999.github.io/companion-doll-backend/showcase.html)
- [完整安装与运行说明](../ENGINEERING.md)

`python -m companion.tools.migrate --db data/companion.db` 可停服升级。v1→v2 先作 SQLite backup，再事务迁移；未知更高版本拒绝，回退恢复备份到新路径。wheel 包含所有配置、七角色提示词和迁移 SQL。
