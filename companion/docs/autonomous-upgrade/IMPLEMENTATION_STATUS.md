# 后端当前状态与交接

更新时间：2026-11-09（Asia/Singapore）。研究驱动升级、工程集成和既有 GitHub Pages 发布均已完成；当前为维护阶段。新接手者从根 AGENTS.md、ENGINEERING.md 与 [工程 review](../ENGINEERING_REVIEW.md) 开始。

## 当前实现

- Python 3.10 模块化后端，默认 development 运行 v2 Cognition。
- Talker 负责实时表达；Analysis、Planner、独立 Brief、Critic、Delta、Memory、End 以有限协议协作，Core 负责许可、版本检查和执行。
- course-1.0 包含六类支持策略、三段短练习与固定危机文本；配置与内容来源随包分发。
- SQLite schema v2，保留一致备份、事务迁移、结束恢复与有来源/范围的关系记忆。
- 小智接入固定上游版本，使用服务端设备身份、独立数据库、固定音频与可取消动态语音。
- 研究说明、交互展示和当前架构图均已合并到 main；开发与文档分支的有效改动已整合。

## 验证与使用

本轮工程验证及修复见 [ENGINEERING_REVIEW](../ENGINEERING_REVIEW.md)。运行、迁移、重试、清除和 wheel 检查见 [V2_OPERATIONS](../V2_OPERATIONS.md)。内容准入见 [CONTENT](../CONTENT.md)，设备接入见 [XIAOZHI_HANDOFF](../XIAOZHI_HANDOFF.md)。

2026-11-04 的真实模型合成回放和动态语音数据保留在 [VALIDATION](../VALIDATION.md)、[QUALITY_REVIEW](QUALITY_REVIEW.md) 与 [VALIDATION_SUMMARY](VALIDATION_SUMMARY.json)。本轮离线工程检查与这些既有测量分别报告。

当前限制：文本首句与常规后台时延尚未稳定达到原参考目标，真实模型仍可能超时；ESP32 扬声器首响、实际停声、麦克风与物理交互需要设备实测。当前可用范围为合成案例或成年成员课程演示。

## GitHub 与 Pages 发布验收

既有研究升级已于 2026-11-04 集成 main，Pages 从 main:/docs 发布。[既有发布工作流](https://github.com/hhuang999/companion-doll-backend/actions/runs/41696251499)与线上检查记录见 VALIDATION。

[研究报告](https://hhuang999.github.io/companion-doll-backend/)、[交互展示](https://hhuang999.github.io/companion-doll-backend/showcase.html)与[当前架构图](https://hhuang999.github.io/companion-doll-backend/architecture-course/overview.html)保留既有入口。本轮远端同步状态见工程 review。

## 资料分工

- TASK、START、CONTEXT：已经执行完成的升级要求和起点资料。
- STRATEGY_DESIGN、research/EVIDENCE_REVIEW：策略设计与来源核查。
- QUALITY_REVIEW、VALIDATION_SUMMARY：既有真实合成回放的质量结论与汇总。
- DEMO：课程演示操作。
- 根 AGENTS.md、ENGINEERING.md、ENGINEERING_REVIEW：当前接手、运行与工程验证。

后续维护以当前代码和工程说明为准，不重复执行已完成的升级任务；新增功能与修复在独立任务分支完成验证后整合。
