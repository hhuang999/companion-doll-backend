# 真实模型与语音回归 · 2026-11-09

验证代码：`71eaf42`，即本轮后端 review、修复和整理后的 main。使用既有配置与超时预算，经 Aihubmix 调用真实模型；输入均为合成案例或上游公开音频样本。各阶段串行执行。

## 在线 pytest

```powershell
.venv/Scripts/python.exe -m pytest -c companion/pyproject.toml companion/tests/test_online.py -m online -q --tb=short --basetemp artifacts/online-regression-20261109/pytest --junitxml=artifacts/online-regression-20261109/online-tests.xml
```

**3 passed，0 skipped，59.55 秒。**

| 检查 | 实际结果 |
| --- | --- |
| 多轮对话与结束整理 | 两轮真实输入正常回应并形成许可邀请；Analysis、Brief、Planner、Critic、End 五次角色调用均 completed，两个后台任务 completed，结束任务 done，摘要已保存 |
| TTS | `gpt-4o-mini-tts` / `coral` 返回可读取 WAV，音频 4.5 秒，请求耗时 1891ms |
| 风险回归 | 固定 120 条样本，none / watch / high 各 40；120 次模型调用状态均为 ok，0 调用失败；组合高危召回、watch 召回、时限内高危召回均 100%，false-high 为 0 |

风险结果针对既有开发者标注集。模型对 none 的 40 条均返回 none；规则与模型组合将其中 12 条提升为 watch，体现现有词表的保守策略。未修改样本、标签、阈值或调用期限。

## 小智协议与真实 ASR

先运行 `scripts/run_xiaozhi.ps1`，再以独立小智环境运行：

```powershell
vendor/xiaozhi-venv/Scripts/python.exe scripts/probe_xiaozhi.py
```

探针完整通过，两个连接生成不同 session，两个结束任务均为 done。

| 链路 | 客户端首个 Opus 包 | 结果 |
| --- | ---: | --- |
| 首次唤醒介绍 | 219ms | 预备音频可解码，包含 AI 身份说明 |
| 普通动态回复 | 3297ms | 真实文字生成、TTS、Opus、WebSocket 与 PCM 解码通过 |
| 危机音频与中止 | 187ms | 固定话术命中；abort 到 stop 为 16ms，排空后未收到旧音频 |
| 同一设备重新连接 | 78ms | 新 session，使用回访问候 |
| 真实音频输入 | 4906ms | 上游公开中文音频经 Opus→SenseVoice ASR，收到转写及可解码语音回复 |

首包计时来自探针的接收等待入口；ASR 项包含发送音频结束后的处理与回复等待。它们是本机客户端收包时间。

一个结束协作记录为 partial：模型提出的 persistent 记忆缺少明确的长期依据，被 `Persistent preference/boundary needs explicit enduring evidence` 校验拒绝。该任务的摘要 accepted、结束任务 done；未放宽校验或将候选写成长期事实。

## 动态语音与关闭

```powershell
vendor/xiaozhi-venv/Scripts/python.exe scripts/bench_v2_voice.py --count 10 --output artifacts/online-regression-20261109/voice
```

**10/10 动态回复成功，0 失败、0 超时、0 回退。** 共 15 个生成句，均未命中固定音频缓存。接收的 Opus 包实际解码为 PCM；3 个后台任务、6 次角色调用均 completed，结束任务 done。

| 指标 | n | P50 | P90 |
| --- | ---: | ---: | ---: |
| 文本首句 | 10 | 1250ms | 1641ms |
| 本机客户端首包 | 10 | 4039ms | 4407ms |

本批与 2026-11-04 的 30 次测量分开报告：本次确认调用和音频链路可用，不据此断言性能与历史批次完全相同。

全部新会话结束任务完成后，中断本轮启动的测试服务，确认 8000 端口关闭且 writer lease 可重新取得。终端中断未记录应用的正常关闭提示，因此该项只证明服务退出与 OS 写锁释放；在线 pytest 的 Core 正常关闭另已执行。

## 证据与适用范围

原始结果保存在忽略目录 `artifacts/online-regression-20261109/`：在线测试 XML / 日志、独立对话数据库、风险报告、TTS 报告、协议探针、动态语音与服务日志。可提交汇总保存模型配置、配置摘要与检查结果，排除凭据、原始数据库和音频。

版本化结果见 [本轮合成验证汇总](evidence/online-regression-20261109.json)。源码、提示词、预算和风险阈值均保持被测版本；本轮只补充验证记录。

本轮检查真实 API 与本机语音协议链路；ESP32 扬声器首响、实际停声和硬件输入仍需设备测量。10 次动态语音用于功能回归，性能数值作为该批描述，不与 2026-11-04 的 30 次样本合并。
