# v2 运行、迁移与复核

默认 development 已使用 v2 协作链路。`core/reasoner.py` 和旧 `reasoner_runs` 留作 v1 兼容与历史记录，默认 Core 不再启动旧消费者。

## 开发入口

在项目根目录运行，使用已有 `.venv`：

```powershell
./scripts/run.ps1 fake --db data/development-v2.db
./scripts/run.ps1 live --db data/development-v2.db
./scripts/run.ps1 dashboard --db data/development-v2.db
./scripts/run.ps1 test
```

同一数据库一次只启动一个 Core。CLI 使用 `/policy` 查询最近轮次的冻结策略与当前发布计划，`/memory` 查询当前范围的记忆，`/jobs` 查询协作、评审与最终采用，`/wait` 等待后台空闲；`/state`、`/cry`、`/emotion`、`/end`、`/quit` 保留。

`settings.yaml` 的 `cognition` 配置角色模型、后台模型并发、队列上限、计划 TTL、1200 token 投影预算及四类任务预算。唯一认知硬时限仍为 `timing.reasoner_timeout_s=20`，排队过期另算。Talker、风险和后台使用独立执行资源；后台角色共享调用、token、一次 schema 修复预算。schema 修复也可能因剩余 token 不足而被拒绝。

所有真实模型调用通过 Aihubmix。CLI 的 `--env-file` 和根目录脚本加载 `AIHUBMIXKEY`，环境变量优先。不要将 `.env`、数据库或实际对话日志加入提交。

## 停服升级与回退

1. 结束 CLI / 小智服务，保留数据库及其 WAL；禁止直接只复制一个正在写入的 `.db`。
2. 可先显式执行迁移，也可以由正常启动自动执行相同流程：

   ```powershell
   .venv/Scripts/python.exe -m companion.tools.migrate --db data/companion.db
   .venv/Scripts/python.exe -m companion.tools.migrate --db data/xiaozhi.db
   ```

3. v1 库在独占迁移锁内通过 SQLite backup API 生成同目录 `*.v1-<UTC>.backup`；随后在一个事务中建表、导入和设置 `user_version=2`。空库顺序创建到 v2；v2 重跑不重复导入，也不再备份。更高未知版本拒绝启动。
4. 旧 profile/events 按稳定 ID 导入。不能核验来源的记录标记 `legacy_unverified`，不进入默认确认记忆投影。旧跟进、历史风险、播放计划和结束任务保留；`active_plan_id` 仍是播放计划，策略使用 `active_support_plan_id`。
5. 回退没有自动 down migration：停止全部访问，保留现状另作备份，将升级前一致备份恢复到一个**新的数据库路径**，用 v1 程序指向该路径。恢复会丢失备份之后的写入；不要将 v1 程序直接接入 v2 库。

## 结束恢复、失败与清除

启动时将旧普通 queued/running 协作标记 interrupted，旧策略失效；未正常结束的会话进入 ending。`end_tasks` 是恢复权威，固定 `final_turn_id`，认知任务只是每次执行记录。显式失败不自动无限重试：

```powershell
.venv/Scripts/python.exe -m companion.tools.retry_end SESSION_ID --env-file .env --db data/companion.db
```

先停用持有该库的服务，再执行重试。新执行保留旧失败证据；相同来源记忆/跟进幂等，更晚的更正优先。shutdown grace 到期会取消任务并停止调度、报告 TimeoutError；已发出的同步 HTTP 仍占用线程直到实际返回，不能同时重开同库写入者。服务退出后，下次启动收敛 durable 任务。

运行中使用 `core.purge_user(user_key)`：注册 purging/epoch → 取消输出和任务 → 有界等待 → 原子删除新旧表 → 移除会话。等待超时会明确失败并保留屏障，应等待请求退出后重试；不会假报删除完成。停服时可以使用：

```powershell
.venv/Scripts/python.exe -m companion.tools.purge cli-local --db data/companion.db
```

数据库清除不删除历史备份、本地验收文件或外部 API 服务中的数据；这些文件按各自用途另行管理。

## 小智与测量

```powershell
./scripts/run.ps1 audio
./scripts/run_xiaozhi.ps1
./scripts/run.ps1 dashboard --db data/xiaozhi.db
vendor/xiaozhi-venv/Scripts/python.exe scripts/probe_xiaozhi.py
vendor/xiaozhi-venv/Scripts/python.exe scripts/bench_v2_voice.py --count 30 --output artifacts/v2/voice-manual
```

小智使用锁定上游与已批准六处补丁。新机器按根 README 安装 vendor 环境、FFmpeg、SenseVoice；服务监听后再运行探针。普通语音为完整 WAV 合成、Opus 编码和节奏发送，当前句播放时最多预取下一句。每次 generation 变化取消旧输出；固定危机/练习使用启动前核验的音频，不等待普通 TTS 预取。

现有安装的 `data/xiaozhi-config` 是独立配置副本，安装器不会覆盖它。升级时检查并同步新增七角色提示词、更新的 Talker / stages 和 `settings.cognition`；保留 `storage.db_path: data/xiaozhi.db` 及用户自定义内容。当前工作区已同步本次提示词与 cognition 配置，最终启动记录为 `artifacts/v2/xiaozhi-release-startup.log`。内容文字变化后需重新准备相应固定音频。

`first_sentence_ms` 是文本成句，`tts_start_ms` / `tts_complete_ms` 是首句合成时间，`opus_first_packet_ready_ms` 是编码完成，`opus_first_packet_sent_ms` 是实际上游发送计数增长，`server_completed_ms` 是服务端节奏发送估计。自定义上游发送延迟使首包异步排队时，不能确认的 sent 字段留缺测。客户端另记录收到首包的时间。以上都不等于 ESP32 扬声器实际首响或播放 ACK。

## 固定验收与安装包

```powershell
# 完整离线协议与 12 段固定场景
.venv/Scripts/python.exe -m companion.tools.v2_acceptance quality --fake --output artifacts/v2/fake-manual
# 付费：真实 12 段多轮；保存每轮输出、策略、角色与 usage
.venv/Scripts/python.exe -m companion.tools.v2_acceptance quality --output artifacts/v2/live-manual
# 付费：保留原有 120 条风险回归、对话和 TTS 检查
.venv/Scripts/python.exe -m pytest companion/tests/test_online.py -m online --basetemp artifacts/v2/online-manual

uv build --wheel companion --out-dir artifacts/v2/wheel
uv venv --python .venv/Scripts/python.exe artifacts/v2/wheel-env-new
uv pip install --python artifacts/v2/wheel-env-new/Scripts/python.exe -r companion/requirements.lock artifacts/v2/wheel/companion_backend-0.2.0-py3-none-any.whl
$env:PYTHONIOENCODING='utf-8'
artifacts/v2/wheel-env-new/Scripts/python.exe -I scripts/check_v2_wheel.py artifacts/v2/wheel-manual
```

每次验收使用新输出目录，避免把已有数据混入本次统计。`check_v2_wheel.py` 强制从 site-packages 加载，验证配置/七角色提示词/迁移资源、fake 发布与结束、CLI、v1 备份及幂等升级。

正式内容与设备条件见 [CONTENT](CONTENT.md)；本次真实结果和未达项见 [VALIDATION](VALIDATION.md)，逐项证据索引见 [V2_IMPLEMENTATION_STATUS](V2_IMPLEMENTATION_STATUS.md)。
