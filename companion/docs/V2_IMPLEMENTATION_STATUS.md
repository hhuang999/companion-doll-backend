# v2 实施与验收状态

主规格：`ARCHITECTURE_V2.md`（2.0-design.1）。本地任务分支：`codex/backend-v2`。
实际起点：`43253fe9719b1f96e41d40948b6a805211dc8adc`；不重置基线，不推送远端。

## 当前进度

M0 完成。M1–M4 已打通默认纵向链路并完成首轮新增回归，正在补齐并发/边界验收；M5 语音预取、CLI 和看板已接入，待专项验证；M6 真实探针开始。尚未最终验收，历史 v1 结果不能作为 v2 通过证据。

| 里程碑 | 模块/规格 | 状态与证据 |
| --- | --- | --- |
| M0 | 入口、环境、工作区 | `.venv/Scripts/python.exe`，Python 3.10.20；`./scripts/run.ps1 test`：Ruff/格式通过，60 passed / 3 deselected；已有未跟踪规格、历史图文件保留 |
| M1 | §4–5、§11 契约/迁移/事件 | `cognition/models.py`、`memory/models.py`、`store/migrate.py`、`migrations/002.sql`；空库/旧库/重复/故障回滚/写锁测试通过 |
| M2 | §7–8 调度/预算/有效性/CAS | `cognition/scheduler.py,budget.py,policy.py`；周期触发、合并、DeltaGuard/CAS、过期与部分提交首轮通过；公平/上限补测中 |
| M3 | §6、§5.4 三角色/Brief/修订/默认主路径 | `cognition/agents.py,orchestrator.py`、7 个角色提示词、FakeLLM、Core 默认接入；独立 Brief/一次修订/未复核拒绝通过；真实探针运行中 |
| M4 | §9–10 记忆/边界/反馈 | `memory/service.py`、`cognition/interaction.py`；中文检索/范围/更正/来源/效果区分通过，反馈与异常场景补测中 |
| M5 | §12–13 语音/指标/CLI/看板/小智 | 有界下一句预取、独立 TTS 线程池及取消；`/policy /memory /jobs` 和看板协作/记忆视图已实现，待专项验证 |
| M6 | §16 验收/真实接口/wheel/文档/图 | 12 段固定合成对话已写入 `config/v2_scenarios.yaml`；真实探针 `artifacts/v2/live-probe1/` 运行中 |

首轮新增回归：`./scripts/run.ps1 test`，**81 passed / 3 deselected**，Ruff/格式通过；记录 `artifacts/v2/m1-m4-test2.txt`。旧过期测试从 reasoner_runs/superseded 更新为 cognitive_jobs/cancelled：v2 明确控制会主动取消旧任务，结束恢复断言保持。

## 工程验收矩阵

以下各项尚未完成 v2 验收；实施后填写测试名、命令、结果和证据路径。

| ID | 检查 | 状态 |
| --- | --- | --- |
| V2-01 | 前台与阻塞后台隔离 | 待验证 |
| V2-02 | 事件触发/任务合并 | 待验证 |
| V2-03 | 拒绝/纠正立即生效 | 待验证 |
| V2-04 | 独立 Brief/绑定版本/一次修订 | 待验证 |
| V2-05 | 未复核不发布行动 | 待验证 |
| V2-06 | deadline/调用/token 预算 | 待验证 |
| V2-07 | schema/来源/身份校验 | 待验证 |
| V2-08 | 普通新输入按产物处理 | 待验证 |
| V2-09 | DeltaGuard 后最终 CAS | 待验证 |
| V2-10 | 控制变化/到期/TTL | 待验证 |
| V2-11 | 记忆依赖/迟到更正 | 待验证 |
| V2-12 | 独立记忆部分提交 | 待验证 |
| V2-13 | 许可与 started | 待验证 |
| V2-14 | 独立/迟到 high | 待验证 |
| V2-15 | 播放证据与效果区分 | 待验证 |
| V2-16 | 时间/话题/长期边界/例外 | 待验证 |
| V2-17 | 反馈归因 | 待验证 |
| V2-18 | 中文检索/结构化压缩 | 待验证 |
| V2-19 | 迁移/幂等/失败回滚 | 待验证 |
| V2-20 | 结束恢复与重试 | 待验证 |
| V2-21 | 在途清除屏障 | 待验证 |
| V2-22 | 预取/打断/危机 | 待验证 |
| V2-23 | 看板/CLI/小智 | 待验证 |
| V2-24 | wheel 安装与迁移资源 | 待验证 |

## 真实接口与性能

待执行：各角色/主流程探针、12 段预先固定合成多轮回放、30 个普通动态语音样本、本机 WebSocket/Opus/ASR、看板实际运行。保留失败、超时和 usage，900 ms / 1.8 s / 8 s 目标不变。原始数据仅存忽略的 `artifacts/v2/`。

## 外部条件

正式 S03–S19、审核危机文本及练习仍依赖用户提供；当前只使用 development 夹具/draft。ESP32 尚无本次连接证据，设备实际首响/停声不得用服务端事件替代。上述条件不阻止完成其他工程工作。

## 继续执行入口

读取本文件、`git status --short`、最近提交及 `ARCHITECTURE_V2.md`，继续当前里程碑。已有 `.env` 仅经 dotenv 使用，不输出或提交。下一步：检查 live-probe1 的 role/usage/失败记录，完成公平调度、反馈、原子输入失败、预取竞态测试；再执行固定质量回放、30 音频样本、实际小智/看板/wheel，以及最终文档/架构更新。
