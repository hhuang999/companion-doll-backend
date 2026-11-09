# 后端工程 review 与交接

日期：2026-11-09，Asia/Singapore。基线：`d238742`，已包含先前的练习条件重评与网站提交固定修复。

## 范围与结论

检查当前后端的会话/许可/风险控制、后台协作、记忆来源与事务、设备鉴权与播放、配置升级、维护工具和工程入口。主要模块边界继续适用；本次集中修复维护与启动边界，清理失效实现和生成回执，未改变支持内容或持久化 schema。

## 已修复问题

| 问题 | 实际影响 | 修复与验证 |
| --- | --- | --- |
| 离线清除仅检查目标用户会话，没有取得 writer lease | 目标用户已结束会话时，运行中的服务仍可能与离线删除并发 | 删除前取得独占 lease；回归验证运行中拒绝、停服后删除成功 |
| 结束任务重试先改状态，后验证配置与获取服务写锁 | 配置缺失或已有服务占库时，命令失败但任务已从 failed 变为 pending | 先构建无自动恢复的 Core，再在同一 lease 内重置并恢复；回归检查拒绝时任务不变与正常重试完成 |
| 语音启动先构建 Core，再校验音频并创建 TTS | 无效音频或缺失 TTS 凭据仍可能启动恢复任务；部分异常不释放资源 | 音频校验与 TTS 初始化前置；Core 构建失败关闭 TTS；回归覆盖各启动失败阶段 |
| Core 恢复失败后资源未回收；客户端初始化失败未关闭 Store | 数据库写锁、连接或调度资源可能残留，阻止后续启动 | 构造阶段使用 ExitStack，恢复阶段按正常关闭顺序清理；回归验证 lease 与连接释放，并验证关闭超时时继续持锁及保留连接 |
| 覆盖运行模式时重建整个 runtime 配置 | 自定义 timezone 被重置，影响日期范围记忆与跟进 | 合并保留已验证 runtime 字段，再校验 mode；回归使用 Pacific/Auckland |
| 配置升级允许部署目录位于配置源目录内部 | 后续扫描可能把部署副本及备份再次当作源内容 | 拒绝源/目标相同及双向嵌套；参数化回归覆盖三种重叠关系 |

## 结构与生成内容

- 增加根 AGENTS.md，说明当前职责、入口、运行方式和持久化约束。
- 移除无调用方的 `core/reasoner.py`；当前调度实现为 `cognition/scheduler.py`。保留仍被持久化契约、配置升级或内容摘要使用的兼容数据与资源。
- 从版本库移出 49 个 `.archify/` 中间产物。公开 HTML、可编辑 JSON 和图源仍在 `docs/`；后续生成回执统一忽略。
- 将初始后端设计放入 `history/`，修正架构说明中的链接。
- 根目录研究链与已提交来源 SHA-256 相同；重复稿和已完成升级 Prompt 留在忽略的 `artifacts/local-notes/`。旧图表回执和移出的调度器也有本地副本。
- 收敛持续状态，移除过时进程 ID、重复进度和已失效的“待发布”事项。研究报告与公开站点保持原有入口。
- 本轮结果位于 `artifacts/backend-cleanup/`，与既有模型质量/语音测量分开；本机数据库、凭据和固定音频继续留在原运行路径。

## 本轮验证

| 检查 | 结果 |
| --- | --- |
| 统一离线入口 `scripts/check.py` | Ruff、格式检查通过；179 passed / 3 online deselected |
| 相对基线的新增回归 | 14 项，覆盖维护写锁、失败状态保留、启动资源释放、关闭超时持锁、时区与配置目录重叠 |
| 项目环境依赖 | `uv pip check` 通过；editable 安装更新到当前 0.2.0 元数据 |
| 隔离 wheel | 从 site-packages 加载；配置、角色提示词、迁移 SQL 与升级基线齐全；四角色执行、策略发布、结束任务、CLI、迁移备份和幂等升级通过 |
| 当前工作区 CLI | fake 对话、policy / memory / jobs 查询与正常退出通过 |
| 本机既有设备配置 | demo 准入与 24 段固定音频的绑定、摘要、时长及暂停校验通过；未重新合成音频 |
| 交接检查 | 修改文档的 79 个本地链接有效；295 个可提交文件未发现本机 API key 或设备令牌值；wheel 中的 Core 与当前源码一致，旧调度器已移出 |

本地证据：`artifacts/backend-cleanup/offline-tests.xml`、`wheel-check/report.json`、`handoff-audit.json`；wheel 在该目录的 `wheel/` 下，隔离环境为 `wheel-env/`。统一入口为 `./scripts/run.ps1 test`，隔离 wheel 检查使用 `scripts/check_v2_wheel.py`。

上述为离线工程 review。后续已完成 [2026-11-09 真实模型与语音回归](ONLINE_VALIDATION_20261109.md)：3 项在线测试、120 条风险样本、小智协议与 ASR 探针、10 次动态语音均通过。既有完整在线质量与时延记录见 [VALIDATION](VALIDATION.md)；ESP32 实际播放仍需设备测量。

在线记录的进一步审计发现一项待修问题：End 将孤立时间片段推断成“工作时间”，候选长期记忆被拒绝，但相同推断进入了会话摘要。关键词式长期范围判断存在误拦与漏拦；具体原话、模型结果和离线对照见在线报告。调用与语音功能检查通过，不等同于全部生成内容正确。

## 接手顺序

1. 阅读根 [AGENTS](../../AGENTS.md) 与 [ENGINEERING](../../ENGINEERING.md)。
2. 使用项目 `.venv`；新机器按 setup 安装，再以独立数据库运行 fake CLI。
3. 修改业务时按职责阅读架构、CONTENT 和 V2_OPERATIONS，并运行对应行为回归。
4. 接设备时按 XIAOZHI_HANDOFF 使用独立身份、部署配置和小智环境。

当前可用范围仍为合成案例或成年成员课程演示。已有性能差距、偶发模型超时及真机待测项见 VALIDATION；源码整理不改变这些结论。

## Git 收口

本地与远端均收敛为一个 `main` 分支。已删除 11 个本地旧分支和 7 个远端旧分支；删除前逐一核对提交已包含于主线，远端删除以预期 SHA 保护并原子执行。两个旧 worktree 保留在原位置，改为 detached HEAD 快照。

后端修复提交为 `afb5ce7`，目录与交接整理为 `6f11bed`；最终恢复失败/关闭超时补测与本记录随主线普通快进同步。分支清理前的引用记录位于 `artifacts/backend-cleanup/branch-cleanup.json`。

构造失败时的资源释放遵循 Python [ExitStack](https://docs.python.org/3.10/library/contextlib.html#contextlib.ExitStack) 的逆序清理语义；看板沿用 SQLite 官方支持的 [只读 URI](https://www.sqlite.org/uri.html) 连接。
