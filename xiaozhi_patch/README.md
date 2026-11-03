# 小智接入包

固定上游：[xiaozhi-esp32-server / 92337881](https://github.com/xinnan-tech/xiaozhi-esp32-server/tree/92337881a7b6553614b47e137a774d02bf40512f)。

`companion.patch` 包含六处逻辑接入：LLM provider、Memory provider、ASR 标签、输入登记、abort 通知、wake 来源。新增 abort / wake 两处仍在等待范围确认；依据设计文档 §10.3，确认后才应用上游变更。

## 检查与安装

准备固定提交的上游工作副本后，先执行只读检查：

```powershell
.venv/Scripts/python.exe xiaozhi_patch/apply.py C:/path/to/xiaozhi-esp32-server
```

负责人确认范围后，增加 `--apply` 原子应用统一补丁。工具会检查上游 HEAD 和补丁可应用性，不会覆盖不兼容的本地修改。

```powershell
.venv/Scripts/python.exe xiaozhi_patch/apply.py C:/path/to/xiaozhi-esp32-server --apply
```

在小智使用的 Python 3.10 环境安装本项目，例如 `python -m pip install -e C:/path/to/3800_final_project/companion`。同时按小智文档安装 FFmpeg、Opus、VAD 和 ASR 依赖。将 `config.example.yaml` 的对应键合并到小智的 `data/.config.yaml`，LLM 和 Memory 必须使用相同的绝对 `project_root`。

在 companion 项目根目录执行 `scripts/run.ps1 audio`，预生成固定音频。缺少缓存时 provider 启动即报错。小智保留 SenseVoiceSmall / FunASR 的 raw_emotion 与 Cry 来源，不把缺失标签推断为正常情绪；运行时将其归一成 TurnSignals。

`enable_greeting: true` 保证真实唤醒进入核心。`enable_stop_tts_notify: false` 避免停止提示音插入练习停顿。`close_connection_no_voice_time: 120` 对齐超时要求。普通动态语音由 Companion 的 Aihubmix TTS 生成，仍保留小智已有 TTS 配置以满足连接初始化。

## 验证范围

已验证：固定源文件的补丁可应用性；模拟播放入口下，模型 / TTS 阻塞时独立取消、暂停中打断、不播放旧代次音频和不接受旧完成回调。

待验证：完整上游依赖环境启动，SenseVoice 实际标签，ESP32 / 网关协议，至少 30 个普通首响样本，学业压力与危机真机剧本，取消到实际停声时间、固定模板首响和练习真实静音。当前没有设备实测数据。

接入提供的 started / completed 是服务端节奏发送估计。真机首响和停止需录音或设备时间戳，不能由这些回调直接推定。
