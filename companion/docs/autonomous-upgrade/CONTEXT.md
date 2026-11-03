# 执行上下文与阅读入口

> 整理日期：2026-11-04，Asia/Singapore。仅整理任务资料并只读核对工程；没有在本次资料整理中重新执行后端测试。最新授权与完成标准见 [TASK.md](TASK.md)。

## 阅读顺序

1. [TASK.md](TASK.md)：负责人最新目标、完整自主权限、验收和发布范围。
2. [研究链 v3 原始副本](research/研究链-v3.md)：项目研究故事、证据链接、策略候选和早期设计。
3. 本文件：当前工程入口、已有成果、需调整的历史约束。
4. [根 README](../../../README.md)、[包 README](../../README.md)、[v2 主规格](../ARCHITECTURE_V2.md)、[v2 状态](../V2_IMPLEMENTATION_STATUS.md)、[验证报告](../VALIDATION.md)、[决定](../DECISIONS.md)、[内容说明](../CONTENT.md)、[运行与迁移](../V2_OPERATIONS.md)。
5. 针对工作读取代码、测试、配置、[小智接入包](../../../xiaozhi_patch/README.md)与 [Pages 资料](../../../docs/README.md)。

## 研究附件来源

- 原路径：`E:\download\研究链.md`。
- 文档标题：《情感陪伴玩偶 · 研究链 v3》；文内日期为 Nov 2, 2026。
- 本包保存字节一致的副本，原文件保留。
- 原文件 SHA-256：`35bc34b9164647ae1c90ab8b6067f09787e55d324c26c13e0ae91dab0646fefe`。
- 附件第 5 节和第 11 节给出策略框架，但引用的“A 线策略全文”标签页没有包含在本导出文件中；图像嵌入位置也只有占位文字。不要声称已经读到缺失内容。
- 附件是待核查的原始研究材料。改进、勘误与新增研究应另行记录，保留副本的可追溯性；公开站点引用经核实的结论，区别研究事实和产品设计。

## 负责人已经决定

| 项目 | 决定 |
| --- | --- |
| 目标情境 | 中国大陆高中生日常压力支持 |
| 实际验收对象 | 课程团队、合成案例或成年成员扮演；不招募真实高中生 |
| 执行方式 | Codex 自主搜集、判断、设计、实现、测试、优化和发布 |
| 内容范围 | 全面策略研究与选择，具体 Agent 应用，后端完整闭环；数量不受 S03–S19 限制 |
| 课程内容准入 | 允许基于真实来源、自动内容核查和工程验证自主启用；不冒充人工/临床审核 |
| 核心交付 | 完整闭环、稳定性、对话质量；性能尽量优化并报告真实结果 |
| API 预算 | 使用已有 API，不设置累计费用上限；保留运行时资源预算与用量记录 |
| 真机分工 | 小智同学负责设备接入/硬件测试；本任务负责后端与完善接口、模拟验收、交接包 |
| GitHub / Pages | 包含同步、集成和部署；Pages 可整体重写，讲清研究、项目和架构 |
| 其他服务 | 没有授权购买新增服务、订阅或付费论文 |

## 工程快照：开始执行时重新检查

- 工作区：`D:\HHB\HKUST(GZ)_Library_code\AIAA3800_HCI\3800_final_project`。
- 核对时分支：`codex/backend-v2`。
- 核对时 HEAD：`3cb20bc8b47ef15924ca1a3c6557951a5680cd0c`，标题为 Align overview diagram notes with public v2 deployment。
- 仓库 remote：<https://github.com/hhuang999/companion-doll-backend.git>。
- 已有 Pages：<https://hhuang999.github.io/companion-doll-backend/>。
- 核对时已跟踪文件无未提交改动；已有大量历史 `.archify/` 未跟踪产物和两份历史文稿，保留。当前任务包是本次新增资料，不要将其他未跟踪文件全量加入提交。
- 发布文档记录 Pages 使用 `main` 的 `/docs`；正式执行前核实实际远端配置。当前发布文件已是 v2，但 `docs/README.md` 仍残留旧 v1 图集维护说明，需要在站点升级时统一。

上述是本地快照，不表示本轮核对了线上部署状态。后续以实际代码、远端和运行证据为准，不重置到该提交。

## 已有能力和代码入口

Python 模块化单体，包源码在 `companion/companion/`，不是 `src/`。

| 位置 | 已有职责 |
| --- | --- |
| `core/api.py`、`state_machine.py`、`validator.py` | Core、阶段、许可、输入与输出处理 |
| `cognition/` | 情境分析/Planner/Brief/Critic、预算、公平调度、版本有效性、DeltaGuard/CAS |
| `memory/` | 四类记忆、中文检索、来源、范围、更正与反馈 |
| `store/` | SQLite、迁移、事务、结束恢复与清除 |
| `core/talker.py`、`llm/` | 提示组装、分句、真实客户端和 FakeLLM |
| `adapters/` | CLI、剧本、小智输出与取消 |
| `dashboard/` | 本地观察台 |
| `config/` | 模型/时序、阶段、卡片、练习、安全话术、角色提示词 |
| `xiaozhi_patch/` | 六处已实现小智补丁、安装与配置 |
| 根 `scripts/` | 运行、安装、语音探针、wheel 验证等 |

默认 development 已使用 v2 协作路径，不应退回旧 Reasoner 消费者。后端已有独立风险、迟到 high 接管、输出闸门、明确许可、取消、有限音频预取、四类关系记忆、迁移/恢复和在途删除屏障等机制。

## 关键内容缺口与历史约束

当前只有 S16 开发夹具“从为什么到具体经过”，来源 pending；危机文本为占位，练习为 draft。`core/config.py::validate_demo()` 仍写死恰好 S03–S19 的 approved 集合，并检查危机 reviewer 等字段。

**这是本轮需要实际升级的内容准入实现，不是要求负责人再提供 17 张卡或签字的理由。** 按 TASK 的课程用途建立准确、可验证的状态与记录；同时保留真正的风险、许可、来源和资源检查。既有运行时 Critic 的 approved 不能冒充内容包审核。

旧研究链描述的阶段、单卡限制和 Talker–Reasoner 架构也不是必须恢复的约束。对每个改变给出研究/行为理由与迁移处理。

## 历史验收证据：不是本轮新结果

以下数字来自现有 V2_IMPLEMENTATION_STATUS / VALIDATION，应读取报告上下文和本地产物后使用：

- v2 离线 Ruff/格式通过；96 passed / 3 online deselected。
- 已执行 12 段多轮真实质量回放及追加定点修复；存在过度追问、无依据细节/保证、偶发标签遗漏和超时。
- 普通语音尝试 40 次，34 动态成功、6 次回退。动态文本首句 P50 2023.5 ms / P90 2579 ms；动态客户端首包 P50 5492.5 ms / P90 7297 ms。
- 常规后台 8 s 参考目标未稳定达到；真机 1.8 s 未测。
- 已完成本机小智 WebSocket/Opus/SenseVoice、看板、迁移和隔离 wheel 工程检查。
- 原始记录主要位于忽略目录 `artifacts/v2/`；可公开汇总在 `companion/docs/evidence/v2-summary.json`。

这些结果帮助定位起点，不能直接作为新策略体系通过验收的证据。本任务不以旧性能数字全部达标为唯一完成条件，仍需定位、优化、复测与披露。

## 环境与命令入口

已有 `.venv/Scripts/python.exe`，历史版本 Python 3.10.20；运行前确认。Aihubmix 通过 dotenv 的 `AIHUBMIXKEY` 加载，不能输出、提交或放入 Pages。小智有独立 vendor 环境。

```powershell
./scripts/run.ps1 fake
./scripts/run.ps1 live
./scripts/run.ps1 dashboard
./scripts/run.ps1 test
./scripts/run.ps1 audio
./scripts/run_xiaozhi.ps1
vendor/xiaozhi-venv/Scripts/python.exe scripts/probe_xiaozhi.py
```

更详细的真实回放、语音性能、wheel、迁移命令见 V2_OPERATIONS。它们是当前入口，不是要求在未理解状态前同时运行全部付费检查。

CLI 常用 `/policy`、`/memory`、`/jobs`、`/state`、`/wait`、`/end`、`/quit`。小智默认 WS 地址 `ws://127.0.0.1:8000/xiaozhi/v1/`；已有设备身份、LAN 配置及补丁语义见 xiaozhi_patch/README。

`data/xiaozhi-config` 是独立配置副本，默认不会被安装器覆盖。策略库、提示词、模型配置升级需处理这条真实运行路径。`data/xiaozhi.db` 与 CLI 数据库分开；一个数据库同时只由一个 Core 写入。

## 展示站当前资产

`docs/architecture-v2/` 有四个 Archify 视图（overview、collaboration、memory、audio）及可编辑 architecture JSON、预览和验证记录。根 `docs/index.html` 是当前入口，历史 v1 仍有入口。

本轮允许重新组织站点，展示研究问题、策略证据、Agent 采用方式、实际互动、接口和验收。现有图可复用或重做，但最终图和源码链接必须反映本轮实现；仅替换标题或增加一张图不满足本轮展示目标。
