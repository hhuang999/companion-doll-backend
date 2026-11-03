# 情感陪伴玩偶后端

依据《情感陪伴玩偶 · 后端技术设计文档 v1.1》实现的 Python 3.10 后端。独立文字入口、Talker / Reasoner、状态与许可管理、风险接管、练习播放计划、SQLite 记忆、观察看板和小智接入包均已实现。

当前默认运行 `development`：S16 是开发夹具，危机文本是明确标注的测试占位内容，三段练习是待审核草稿。正式 17 张行动卡、审核话术和真机验收仍待补齐；`demo` 模式会检查这些条件。最新证据与未达项见 [验证报告](companion/docs/VALIDATION.md)。

## 立即运行

在本目录打开 PowerShell。当前工作区已安装 `.venv`，可以直接运行：

```powershell
# 离线文字对话，不调用 API
./scripts/run.ps1 fake

# 使用项目 .env 中的 AIHUBMIXKEY
./scripts/run.ps1 live

# 在另一个终端打开观察台，地址 http://127.0.0.1:8501
./scripts/run.ps1 dashboard
```

命令行支持 `/state` 查看状态、`/wait` 等待后台分析、`/cry 今天很难过` 模拟哭声、`/emotion SAD 今天很累` 传递情绪、`/end` 模拟无语音结束、`/quit` 退出。输入“怎么办”会先请求许可；明确同意且有合格卡片后才进入行动。异步分析尚未完成时保留同意并等待卡片。

文字入口中的练习默认按虚拟时间输出，使用 `--realtime` 观察停顿；音频播放由小智适配器负责。

```powershell
./scripts/run.ps1 fake --realtime
./scripts/run.ps1 fake --scenario companion/tests/scenarios/08_permission.yaml
```

## 安装到新环境

需要 Python 3.10 和 uv。Windows 已有 uv 时：

```powershell
./scripts/setup.ps1
# 也可明确指定已有 Python 3.10
./scripts/setup.ps1 -Python C:/path/to/python.exe
```

跨平台的等价安装方式：

```sh
uv venv --python 3.10 .venv
uv pip install --python .venv/bin/python -r companion/requirements.lock
uv pip install --python .venv/bin/python --no-deps -e companion
```

Windows 上解释器路径为 `.venv/Scripts/python.exe`。锁文件对应此次 Python 3.10 Windows 验证环境；其他平台请先验证本机依赖。`.env.example` 只有空变量名；将自己的 key 写入 `.env`。进程环境优先于 `.env`。源码、配置和日志不会写入 key。

## 验证

```powershell
# Ruff、格式检查和全部离线 pytest；不访问网络
./scripts/run.ps1 test

# 真实模型与语音检查、120 条风险回归，会消耗 API 额度
.venv/Scripts/python.exe -m pytest companion/tests -m online --basetemp artifacts/pytest-online-manual

# 至少 30 个成功的普通模型回复；失败和备用句另报
.venv/Scripts/python.exe -m companion.tools.bench --env-file .env --count 30 --output artifacts/latency.json

# 生成并测量固定练习和危机测试音频，小智启动前执行
./scripts/run.ps1 audio
```

默认 `pytest` 排除 online 与 hardware。在线测试使用合成文本，不读取实际用户对话。14 个基础剧本在 `companion/tests/scenarios/`；其中 `fixture` 步骤只允许 FakeLLM，五类压力剧本验证流程而不验证研究适用性。时序、取消、过期与恢复由单独的单元测试控制。

## 配置与数据

默认配置位于 `companion/companion/config/`。可复制整个目录后通过 `--config-dir` 指定自己的版本。

| 文件 | 用途 |
| --- | --- |
| `settings.yaml` | 模型、预算、线程池、数据库、时区、TTS |
| `persona.yaml` / `stages.yaml` | 身份介绍、开场、收尾、各阶段及提议模板 |
| `rules.yaml` / `risk_lexicon.yaml` | 确定性规则、输出护栏、第一层风险检测 |
| `cards/*.yaml` | 行动卡及来源、约束、状态 |
| `crisis.yaml` | 固定危机话术和审核信息 |
| `exercises/*.yaml` | 练习文本、句后停顿及可选已测量音频 |
| `prompts/*.j2` | Talker、Reasoner、风险模型提示词 |

默认数据库为工作目录下的 `data/companion.db`。CLI 可用 `--db` 指定路径；小智适配器按 `project_root` 解析。固定音频位于 `data/fixed_audio/`；动态语音只在内存和短暂 WAV 文件中处理，转换后删除。数据库、运行音频、`.env`、测试产物和本地解释器均已忽略提交。

启动时会恢复未完成会话，将其转为结束分析任务；旧会话不恢复为活动对话。`failed` 的结束分析保留错误记录，检查原因并停服后可显式重试：`python -m companion.tools.retry_end <session_id> --env-file .env --db data/companion.db`。一个数据库由一个后端进程持有；看板通过独立连接读取。

清除一个用户的数据前停止该用户的对话：

```powershell
.venv/Scripts/python.exe -m companion.tools.purge cli-local --db data/companion.db
```

运行中的服务使用 `CompanionCore.purge_user(user_key)`，它会先取消并等待后台任务。数据库包含原话、记忆和风险记录，备份与清理应覆盖 SQLite 主文件及关联 WAL 文件；正常停服后再备份。

## 接入小智

接入包在 [xiaozhi_patch](xiaozhi_patch/README.md)，锁定上游提交 `92337881a7b6553614b47e137a774d02bf40512f`。补丁检查通过，两个新增钩子的范围确认仍待回复；当前没有修改上游工作副本。

小智适配器通过统一 OutputPort 发送普通语音、固定危机音频与练习计划，具有独立取消入口。服务端的队列排空估计与设备实际播放完成分开记录，设备首响及停止时刻仍须真机采集。

## 代码入口

- `companion/companion/core/api.py`：输入、风险回调、输出、播放回执和会话结束。
- `companion/companion/core/state_machine.py`：阶段、同意对象与行动次数。
- `companion/companion/core/reasoner.py` / `validator.py`：后台任务合并、发布前验证。
- `companion/companion/store/`：SQLite 事务、快照、记忆、跟进与恢复。
- `companion/companion/adapters/`：文字、剧本与小智适配器。
- `companion/companion/dashboard/`：本地观察看板。

实现取舍见 [DECISIONS.md](companion/docs/DECISIONS.md)，正式材料接入步骤见 [内容准备](companion/docs/CONTENT.md)。
