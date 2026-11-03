# companion-backend

Python 3.10 情感陪伴玩偶后端。包含独立 CLI、实时 Talker、后台有界多角色协作、确定性许可状态、风险接管、练习计划、四类有来源和范围的 SQLite 关系记忆和 Streamlit 看板。

```sh
python -m pip install -e '.[test]'
companion --fake
companion --env-file /path/to/.env
companion-dashboard --db data/companion.db
pytest
```

默认 development 使用明确标记的开发夹具和待审核内容。正式材料和硬件联调要求见 `docs/CONTENT.md` 与 `docs/VALIDATION.md`。完整项目的 Windows 安装 / 运行脚本及小智补丁位于此包上层的项目仓库。

## v2 默认路径

Analysis 解释有限证据，Planner 生成候选策略；deliberation 另并行生成独立 Brief，再由 Critic 绑定确切版本评审，最多修订一次并复核。routine 只发布非行动策略。Core 冻结 TurnPolicyFrame，控制变化、记忆版本、TTL、DeltaGuard 和最终 CAS 共同决定是否采用。行动仍由原有许可状态机与卡片 Validator 决定。

`/policy`、`/memory`、`/jobs` 可观察该路径；默认配置含各角色模型及调用/token预算。FakeLLM 与 Aihubmix 走同一协议。

- [运行、迁移、重试、清除与 wheel 验证](docs/V2_OPERATIONS.md)
- [V2-01～V2-24 状态与证据](docs/V2_IMPLEMENTATION_STATUS.md)
- [真实验收与性能结果](docs/VALIDATION.md)
- [v2 交互架构图集（GitHub Pages）](https://hhuang999.github.io/companion-doll-backend/)

`python -m companion.tools.migrate --db data/companion.db` 可停服升级。v1→v2 先作 SQLite backup，再事务迁移；未知更高版本拒绝，回退恢复备份到新路径。wheel 包含所有配置、七角色提示词和迁移 SQL。
