# v2 实施与验收状态

主规格：[ARCHITECTURE_V2](ARCHITECTURE_V2.md)。分支：`codex/backend-v2`。实际起点 `43253fe9719b1f96e41d40948b6a805211dc8adc`；未重置、未覆盖无关改动、未推送。

**M0～M6 的可独立完成工程、集成、验收执行与文档工作已完成。工程行为检查通过；对话质量与性能有未达项，正式内容/ESP32 硬件条件待提供。** 不将实现完成表述为全部产品验收通过。

## 实现与里程碑

| 阶段 / 规格 | 落实位置 | 验证与状态 |
| --- | --- | --- |
| M0 基线 | 根 scripts / 既有 .venv / Git | Python 3.10.20；基线 Ruff/格式、60 passed / 3 deselected；保留原有未跟踪文稿和历史图 |
| M1 §4–5、§11 | cognition/models.py、memory/models.py、store/migrate.py、store/migrations/002.sql | 八项主契约、独立策略字段；空库/v1/v2、backup、幂等、事务故障、写锁通过 |
| M2 §7–8 | cognition/scheduler.py、budget.py、policy.py | 合并/跨用户公平/排队上限/超时/真实占用槽位、产物分离、DeltaGuard/CAS 通过 |
| M3 §6、§5.4 | cognition/agents.py、orchestrator.py、7 个角色提示词、FakeLLM、Core | routine、独立 Brief、确切版本 Critic、最多一次修订及复核；fake 与真实 API 均执行 |
| M4 §9–10 | memory/service.py、cognition/interaction.py、store/cognition.py | 四类记忆、中文检索、边界范围、迟到更正、supersedes、明确/模糊反馈区分通过 |
| M5 §12–13 | adapters/xiaozhi/output.py、runtime.py、CLI、dashboard | 有界下一句预取、取消与固定接管；实际 WebSocket/Opus/ASR、看板和 40 个语音样本完成 |
| M6 §16–17 | tools/v2_acceptance.py、scripts/bench_v2_voice.py、scripts/check_v2_wheel.py、docs | 96 项离线通过；12 段完整真实回放两轮，追加定点修复；最终 wheel 安装和迁移通过；四张源码架构图完成 |

实现提交：`deb7c58`（契约/迁移/纵向链路）、`cfba835`（完整集成和故障验证）、`e3ef674`（Planner 数组契约与具体诊断）。架构图固定于 `e3ef674820ee25c4873b4a9658a2a980060aa922`；其后文档提交不改变该实现。

## V2-01～V2-24 工程验收

公共检查命令：`./scripts/run.ps1 test`，Ruff/格式通过，**96 passed / 3 online deselected**。本地完整输出：`artifacts/v2/offline-release.txt`。下表中的文件均位于 `companion/tests/`；ID 前缀对应测试名，可用 `pytest -k v2_XX` 定点执行（附加原测试不一定带前缀）。

| ID | 行为 | 结果与直接证据 |
| --- | --- | --- |
| V2-01 | 阻塞后台不阻塞 Talker | 通过；test_v2_cognition.py::test_v2_01_blocked_background_does_not_block_talker |
| V2-02 | 周期/事件合并、公平与上限 | 通过；test_v2_cognition.py::test_v2_02_periodic_trigger_and_merge；test_v2_execution.py::test_v2_02_scheduler_fairness_queue_limit_and_terminal_states |
| V2-03 | 拒绝/纠正当轮生效 | 通过；test_v2_execution.py::test_v2_03_refusal_and_boundary_withdraw_offer_immediately；test_v2_atomic.py 的输入事务失败；真实 Q02/Q05/Q12 |
| V2-04 | Brief 独立、绑定版本、单次修订 | 通过；test_v2_cognition.py::test_v2_04_independent_brief_exact_version_single_revision；真实无修订评议走同一协议 |
| V2-05 | 修订未复核或版本错误不发布 | 通过；test_v2_cognition.py 的 revision_without_recheck、wrong_review_version 两项 |
| V2-06 | deadline/call/token 与失败终态 | 通过；test_v2_cognition.py 的 budget_reservations_deadline_shared_repair、provider_failure；test_v2_execution.py 的 shutdown_stops_dispatch；真实 budget/schema/timeout 记录保留 |
| V2-07 | schema/来源/身份 | 通过；test_v2_cognition.py 的 foreign_evidence_and_forged_memory；test_v2_memory.py 的 quote_and_persistent_scope；test_v2_migration.py 的 event_identity |
| V2-08 | 普通新输入按产物处理 | 通过；test_v2_cognition.py::test_v2_08_ordinary_new_input_is_guarded_and_published |
| V2-09 | Guard 后又变更，最终 CAS 拒绝 | 通过；test_v2_cognition.py::test_v2_09_delta_guard_final_cas_rejects_newer_input，屏障控制，无循环 Guard |
| V2-10 | 控制变更、到期、TTL 不续命 | 通过；test_v2_cognition.py 的 plan_expiry_does_not_refresh_on_read；原 topic/quiet/consent 回归 |
| V2-11 | 依赖记忆竞争与迟到更正 | 通过；test_v2_cognition.py 的 plan_memory_dependency_conflict_across_sessions；test_v2_memory.py 的 older_memory_cannot_override_correction_and_supersedes_preserved |
| V2-12 | 独立记忆部分提交 | 通过；test_v2_cognition.py::test_v2_12_plan_expired_independent_memory_commits_partial；test_v2_atomic.py 发布故障回滚 |
| V2-13 | 明确许可、过期与 started | 通过；test_v2_execution.py::test_v2_13_prefetch_does_not_change_consent_without_started；原 permission/exercise 场景和核心测试 |
| V2-14 | 最新/迟到 high 与繁忙后台 | 通过；test_v2_cognition.py::test_v2_14_risk_high_bypasses_busy_background；原 late_high 回归；真实 120 条合成风险及小智固定接管 |
| V2-15 | completed 不代表受益 | 通过；test_v2_memory.py::test_v2_15_execution_does_not_create_positive_memory；UI 显示 origin=server_playback |
| V2-16 | 时间/话题/长期边界与局部例外 | 通过；test_v2_memory.py::test_v2_16_scopes_expiry_reconnect_and_local_exception（可控时钟）；Q03/Q04 真模型回放 |
| V2-17 | 反馈归因与重复失效 | 通过；test_v2_execution.py 的 explicit_feedback_attribution_and_ambiguous_feedback、same_target_failures_count_distinct_user_turns；Q09 回放 |
| V2-18 | 中文相关性、用户隔离、完整投影 | 通过；test_v2_memory.py::test_v2_18_chinese_retrieval_complete_json_and_user_isolation |
| V2-19 | 迁移/幂等/回滚/未知高版本 | 通过；test_v2_migration.py 全部迁移检查；隔离 wheel 再次验证真实 SQL 资源 |
| V2-20 | 结束恢复、固定游标、重试与幂等 | 通过；test_v2_atomic.py::test_v2_20_end_followup_recovery_is_idempotent；原结束失败/retry 测试；真实结束任务及最终在线对话检查 |
| V2-21 | 清除在途屏障 | 通过；test_v2_cognition.py::test_v2_21_purge_waits_inflight_and_does_not_resurrect；原清除/旧播放回调回归 |
| V2-22 | 预取重叠、打断、固定接管 | 通过；test_v2_execution.py 两项 v2_22 屏障测试；首包跨句计数重置测试；实际 Opus 探针 |
| V2-23 | CLI / 看板 / 小智 | 通过本机工程检查；fake-final 36 轮、wheel CLI、dashboard-browser-evidence.log / dashboard-memory-final.log、xiaozhi-integration1.json；ESP32 真机未测 |
| V2-24 | wheel 安装与迁移资源 | 通过；artifacts/v2/wheel-release-check/report.json；python -I 从 site-packages 执行，配置/七角色提示词/迁移、fake 发布与 CLI 均通过 |

## 真实接口、质量与性能

详见 [VALIDATION](VALIDATION.md) 和提交的 [合成汇总](evidence/v2-summary.json)。原始记录保存在忽略目录 `artifacts/v2/`：

- `quality1/`、`quality2/`：预固定 Q01–Q12，各 36 轮；`quality3-targeted/`：Q03/Q05/Q06/Q12 定点修复；`quality4-persona/`：Q11。
- `live-final/`：6 轮，33 次角色调用全部结构成功，8 completed / 2 rejected / 1 partial；两个结束任务 done。保留业务拒绝而非伪装成功。
- `voice1/`、`voice2/`：30+10 次，34 动态成功，6 次回退；客户端首包全部保留，第一批服务端 sent 字段漏记和补测分开。
- `online-tests.log`：初轮 2 passed / 1 failed；`online-recheck.log`：25 秒旧观察窗口未空闲；`online-final.log`：对话与总结检查通过，单任务 deadline 未变。
- `wheel-release/`、`wheel-release-check/`：最终包与隔离安装；`dashboard-final.png`：合成数据界面；`diagram-final-*.log`：架构浏览器校验。

**未达：** 900 ms 文本首句（动态 n=34，P50 2023.5 ms / P90 2579 ms）；普通动态客户端首包 P50 5492.5 ms / P90 7297 ms；常规后台 8 s 未稳定达到。真机 1.8 s 无硬件证据。真实质量仍有过问、偶发标签遗漏/超时与无依据细节，详列在验证报告；不通过删除失败样本获得“全通过”。

## 外部条件与交付边界

正式 S03–S19、审核危机文本及练习、ESP32 真机仍需负责人提供。默认 development 使用明确 fixture/draft，demo 审核门槛未降低。服务端 completed 不冒充设备 ACK。

准确命令、升级/备份/恢复/清除说明见 [V2_OPERATIONS](V2_OPERATIONS.md)。[四张本地架构图](../../docs/architecture-v2/index.html) 反映最终源码，本次没有远端推送、合并或公共部署。原有无关未跟踪文稿、CODEX_UPGRADE_V2_PROMPT 和历史 .archify 证据保留。
