# 小智课程后端接入与联调

适用：本仓库固定的 xiaozhi-esp32-server `92337881a7b6553614b47e137a774d02bf40512f`，协议 hello version 1。保持原六处 Companion hook；本次另加 `access.patch` 做连接鉴权与日志脱敏。原来仅发送 device-id 的客户端必须增加 Bearer 凭据。没有新增设备 ACK 或能力协商消息。

## 准备与启动

在仓库根目录使用 PowerShell。先按根 README 建立 `.venv`，安装 Git、FFmpeg，确保 `.env` 含 `AIHUBMIXKEY`。

```powershell
./scripts/setup_xiaozhi.ps1
# 已安装的部署副本可单独升级；保留定制值并在更改前备份
.venv/Scripts/python.exe -m companion.tools.upgrade_config data/xiaozhi-config
.venv/Scripts/python.exe -m companion.tools.prepare_audio --env-file .env --config-dir data/xiaozhi-config --output data/fixed_audio --bind-config
.venv/Scripts/python.exe -m companion.tools.provision_device --device-id course-board-01 --user-key course-person-01 --output data/course-board-01.json
./scripts/run_xiaozhi.ps1
```

首次安装下载固定 SenseVoiceSmall 权重，生成版本绑定的固定音频；命中音频缓存不重复请求。等待日志出现 `server listening` 后连接。模型均经 Aihubmix，密钥留在服务器；设备只接收自己对应的私有凭据文件。Ctrl+C 停止服务。观察台：`./scripts/run.ps1 dashboard --db data/xiaozhi.db`。

固定音频使用真实 WAV 时长加脚本停顿进行 ≤90 秒校验。修改话术、声音或 TTS 模型后必须重新准备；陈旧 hash 或缺资源会在启动时失败。运行配置在 `data/xiaozhi-config`，源配置在 wheel 内；两者应通过升级工具同步，避免直接覆盖定制文件。

## 地址、鉴权与身份

默认地址 `ws://127.0.0.1:8000/xiaozhi/v1/`；HTTP 8003 是上游辅助端口，不承载本项目的公网控制面。LAN 演示时修改 `vendor/xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml` 中 `server.ip` 和 `server.websocket` 为实际网卡及 LAN 地址，防火墙只允许课程网络访问 8000。公开 Pages 是静态说明，不连接此服务。公网部署需要另行配置 TLS/访问策略，不能直接开放当前明文 WS。

握手 HTTP 请求头：

```text
device-id: course-board-01
Authorization: Bearer <该设备私有凭据文件中的 token>
```

服务器从 `data/device-access.json` 找到设备、核对 token，再绑定服务端 `user_key`。客户端传入其他 user-key 不会改变映射。每次连接新建 `session_id`；同一已认证身份可跨会话读取有来源且适用的记忆。不同设备可由服务端明确映射给同一课程用户，默认示例各自隔离。不要在终端、截图、Git 或 Pages 中公开凭据。

轮换：对同一设备执行上面的 provision 命令并加 `--rotate`，安全传递新凭据。禁用：将 registry 中该项的 `enabled` 改为 false。两者影响新连接；已连接的设备应断开或重启服务以立即撤销。缺凭据、未知设备、错误 token、禁用设备均返回 `{"type":"error","code":"AUTH_FAILED"}` 并关闭，WebSocket code 1008。鉴权失败不自动重试旧 token。

## 消息与音频

连接后先发 hello，等待服务器 hello（含本连接 session_id），再输入。当前上游 provider 异步初始化；模拟器收到 hello 后等 3 秒。设备首次接入也应保留这个初始化间隔，hello 本身不表示 ASR 已加载。

```json
{"type":"hello","version":1,"transport":"websocket","audio_params":{"format":"opus","sample_rate":16000,"channels":1,"frame_duration":60}}
```

文字输入及真实唤醒使用既有 `listen/detect` 路径：

```json
{"type":"listen","state":"detect","text":"今天有点累，想说说。"}
{"type":"listen","state":"detect","text":"你好小智"}
```

只有上游识别为真实唤醒的来源才标记 wake，普通用户消息不会伪装成唤醒。首次介绍与后续问候各走固定文本/音频；真实 wake 可触发合适的跟进。

手动音频输入顺序：

```json
{"type":"listen","state":"start","mode":"manual"}
```

发送 WebSocket binary Opus 帧：16 kHz、单声道、60 ms，解码后每帧 960 samples；保持实际采集节奏。发完后：

```json
{"type":"listen","state":"stop"}
```

输出包含 `stt` 转写、`llm` 表情、`tts` 的 `start` / `sentence_start`（text）/ `stop`，以及 binary Opus 音频。一轮可能有多句、多个 stop；**单句 stop 不能被当作整轮已结束**。现有协议没有 turn-complete ACK；测试工具通过本地 Store 终态加线路静默判断本轮排空，设备按音频播放队列管理即可。不要将没有发送的 text 字段或 generation 字段当作已经支持的线上协议。

```json
{"type":"abort","reason":"wake_word_detected"}
```

abort 使 Core 递增内部 generation、撤销旧输出、取消旧合成/预取并清空发送队列，服务器发送 stop。设备收到 stop 也要立即清空自身解码和播放缓冲。反复 abort 可安全重复；已经发到设备的帧无法由服务器撤回。固定危机接管绕过动态模型和普通音频排队，仍通过同一 generation 闸门。练习中用户拒绝、打断或停止都会结束当前计划。

## 状态、重试与恢复

服务端对话状态为探索、安慰、行动、安静、危机等，另有独立生命周期和播放计划。行动许可只允许当前被确认的行动；泛化同意不能直接启动一个尚未说明的具体练习。短练习先邀请，再接受明确同意；每次行动聚焦一张卡。断开连接触发结束任务，持久化总结/记忆失败可在重启时恢复重试。

| 条件 | 设备/联调处理 | 服务端语义 |
| --- | --- | --- |
| hello 15 秒无响应 | 关闭，检查地址/服务日志后重连 | 不假定已建立会话 |
| 网络断开/1006 | 1、2、4 秒退避，最多3次；失败交给操作者 | 新 session，同一认证 user；不恢复旧音频 |
| AUTH_FAILED /1008 | 停止重试，重新配置凭据 | 不进入用户会话 |
| 普通回复较慢 | 保持可打断；联调工具75秒记录超时 | Talker/风险/后台各有有界deadline；失败可观察 |
| 用户打断 | 清本地缓冲并发 abort | 旧 generation 的结果不得重新输出 |
| 输入重复/乱序 | 单连接按采集顺序发；断线后不自动重放旧输入 | 当前线上协议没有客户端输入幂等ID/乱序重排保证 |
| 空闲120秒 | 按服务停止/断线处理；有新意愿再连接 | 保存结束任务 |

不要通过增加无限重试遮住服务失败。当前 provider 可能返回 429、网络超时或模型结构错误，日志/agent_runs 保存结果；设备协议不保证逐类模型错误码。需要人工排障时提供时间、合成场景、连接是否成功及非敏感日志，不提供 token。

用户数据清除使用服务端 `companion-purge` 工具（先 `--help` 查看必需参数），不会通过任意设备消息触发。清除屏障先取消该用户在途工作，再删数据；同学不得自行添加未认证的 purge 消息。

## 联调与验收

服务启动后，以下命令使用自动创建的独立合成身份，会调用真实模型：

```powershell
vendor/xiaozhi-venv/Scripts/python.exe scripts/probe_xiaozhi.py
vendor/xiaozhi-venv/Scripts/python.exe scripts/bench_v2_voice.py --count 30 --output artifacts/course-voice
./scripts/run.ps1 test
```

probe 检查 hello、介绍、普通回复、固定危机原文、abort 后无旧音频、重连、官方中文 Opus→SenseVoice→回复、结束任务。报告默认 `artifacts/xiaozhi-integration.json`，每次运行应另存版本副本。bench 测普通动态语音，不能用缓存问候替代。原始 DB、凭据及音频保留在忽略目录。

硬件同学逐项记录：稳定认证、重复连接、麦克风实际语音、普通首响、连续句衔接、说话中打断、危机固定接管、练习静音和停止、断网重连、长时间空闲。用合成案例或成年成员扮演，不联系真实未成年人，不拨打援助服务。报告填写板型号、固件版本、网络、输入时刻、首个扬声器声响、最后旧音频时刻及失败次数；设备标识留本地。

测量分工：后端记录文本首句、TTS 提交/完成、Opus 编码、首包发送与本机接收、后台角色耗时/Token；设备记录真实首响和停声。`started/completed` 是服务器节奏发送估计，当前没有设备播放 ACK。900 ms 文本首句、1.8 s 真机首响、8 s 常规后台是参考目标；具体本轮结果见验证报告，硬件数字必须由实测填写。

常见排障：连接拒绝先查监听网卡/防火墙；1008查 registry 与设备凭据是否对应；无ASR查SenseVoice权重/16k单声道帧与初始化；无声查FFmpeg/PyAV Opus及输出队列；启动内容错误查部署配置升级、音频hash和准入回执；不要关闭校验来绕过错误。
