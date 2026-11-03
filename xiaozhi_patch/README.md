# 小智接入包

固定上游：[xiaozhi-esp32-server / 92337881](https://github.com/xinnan-tech/xiaozhi-esp32-server/tree/92337881a7b6553614b47e137a774d02bf40512f)。六处接入已获负责人批准，并应用到本地 `vendor/xiaozhi-esp32-server`：LLM provider、Memory provider、ASR 标签、输入登记、abort 通知、wake 来源。

新增 `access.patch` 在连接认证和日志处补充独立凭据检查，原六处核心 hook 保留。应用工具同时核验两份补丁且幂等。

## 本机启动

在项目根目录打开 PowerShell：

```powershell
./scripts/run_xiaozhi.ps1
# 另一个终端查看该服务的数据
./scripts/run.ps1 dashboard --db data/xiaozhi.db
```

WebSocket 地址为 `ws://127.0.0.1:8000/xiaozhi/v1/`，HTTP 端口为 8003。首次导入 FunASR 可能需要数分钟，出现 `server listening on 127.0.0.1:8000` 后再连接。服务以 Ctrl+C 停止。

接入真实设备时，在 `vendor/xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml` 中将 `server.ip` 改为设备可访问的网卡地址，并将 `server.websocket` 改为对应 LAN 地址。设备每次连接发送稳定的 `device-id` 和独立 Bearer token；服务端 registry 决定 user_key，连接生成独立 session_id。完整凭据、协议和测量清单见 [小智交接](../companion/docs/XIAOZHI_HANDOFF.md)。当前默认仅监听本机。

## 可重复安装

先完成根目录 README 中的 Python 3.10 / uv 安装，确保 FFmpeg 在 PATH、`.env` 有 `AIHUBMIXKEY`，再运行：

```powershell
./scripts/setup_xiaozhi.ps1
```

安装器检查固定 Git 提交、幂等应用补丁，建立独立 `vendor/xiaozhi-venv`，按 Windows Python 3.10 锁文件安装依赖，生成本地配置，下载校验 SenseVoice 权重，并准备固定音频。首次音频生成调用 Aihubmix；已有缓存会复用。Windows 的 Opus 来自锁定 PyAV wheel，启动器复制到项目内 `vendor/native` 并仅修改当前进程 PATH。

ASR 使用 [FunAudioLLM/SenseVoiceSmall](https://huggingface.co/FunAudioLLM/SenseVoiceSmall/tree/3847d57b6bdf2dd8875cb1508d2af43d80a16bf7)，下载版本与 model.pt 的 SHA-256 写在 `configure.py`。权重约 936 MB；模型、依赖和音频均不进入 Git。

独立检查已有上游副本：

```powershell
.venv/Scripts/python.exe xiaozhi_patch/apply.py C:/path/to/xiaozhi-esp32-server
.venv/Scripts/python.exe xiaozhi_patch/apply.py C:/path/to/xiaozhi-esp32-server --apply
```

工具检查 HEAD 必须为固定提交；已完整应用时直接成功退出，不会覆盖不兼容的改动。完整补丁提交在本项目 Git 中，vendor 保持固定上游 HEAD。修改 vendor 的四个现有接入文件后可用 `scripts/build_xiaozhi_patch.py` 重建；两个新增 provider 的源文件保存在 `xiaozhi_patch/files`。

## 配置与行为

核心配置独立复制到 `data/xiaozhi-config`，数据库为 `data/xiaozhi.db`，与文字入口分开。安装器通过 upgrade_config 三方合并默认值、保留定制并备份；修改内容后重新准备并绑定音频。LLM 与 Memory 的 project_root、config_dir 必须一致。

v2 升级仍使用这六处接入：Core 默认启用后台角色协作、范围记忆和有界下一句音频预取。已有配置需同步新增角色提示词、Talker / stages 与 `settings.cognition`，保留独立数据库路径和自定义内容；具体命令、迁移和测量语义见 [v2 运行手册](../companion/docs/V2_OPERATIONS.md)。旧 v2 的40个本机语音样本是历史记录；本轮结果及未达项见 [v2 验证报告](../companion/docs/VALIDATION.md)，不将服务端 completed 当作设备 ACK。

`Intent: nointent` 避免旧工具路由介入。开启 greeting、关闭唤醒缓存，使真实唤醒进入 Companion；关闭停止提示音，保留练习静音。空闲结束时间为 120 秒。上游 prompt 使用仅含 base_prompt 的模板，避免额外位置 / 天气查询；实际模型提示由 Companion 管理。

SenseVoice 原始情绪和 Cry 事件进入 TurnSignals；缺失标签保留未知。只有 Cry 没有文字时，使用 `[检测到哭声，无可识别文字]` 作为事件说明通过上游空文本门槛，不将它视为识别出的用户原话。动态语音由 Aihubmix TTS 合成，固定介绍、问候、收尾、危机与练习音频从缓存读取，统一交给小智 Opus 编码和节奏发送器。

## 联调验证

启动服务器后运行以下合成数据探针，会调用付费模型：

```powershell
vendor/xiaozhi-venv/Scripts/python.exe scripts/probe_xiaozhi.py
```

探针检查 hello、首次唤醒、普通回复、危机缓存音频、abort 后无旧音频、同一设备重连、官方中文样本的真实 Opus → SenseVoice → 回复链路，以及数据库开场标记、风险记录和结束分析。报告位于 `artifacts/xiaozhi-integration.json`；版本化证据与限制见 [验证报告](../companion/docs/VALIDATION.md)。

这些测试使用本机协议客户端。started / completed 是服务端节奏发送估计；ESP32 / 网关真机首响、实际停声、练习静音和真实哭声音频仍需设备实测。课程准入按新版内容来源、自动核查、真实回放与资源回执执行，详见 CONTENT；硬件检查交给小智同学。
